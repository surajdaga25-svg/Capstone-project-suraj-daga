"""
Part 3 - GenAI-powered Insight Narrator (Situation / Complication / Resolution).

Run:
    python narrator/generate_narrative.py              # Gemini if a key is set, else offline
    python narrator/generate_narrative.py --offline    # force the keyless offline path
    python narrator/generate_narrative.py --check-sample   # verify narrator/sample_output.txt

Input : narrator/findings.json  (written by analysis/clean_and_eda.py - never hand-typed)
Output: narrative printed to stdout + a pass/fail line per required figure.
        When the live Gemini call succeeds, the narrative is also saved to
        narrator/sample_output.txt so the checker can be re-run on the saved text.

Free path: get a free Gemini API key from Google AI Studio (free usage tier) and
export it as GEMINI_API_KEY (GOOGLE_API_KEY also works). With NO key the script
falls back to a fully deterministic offline template - no network, no config.
"""
import argparse
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
FINDINGS_PATH = HERE / "findings.json"
SAMPLE_PATH = HERE / "sample_output.txt"

# Free-tier model; override with GEMINI_MODEL if Google retires or renames it.
MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")

# ---- Locked generation parameters (Task 3) -----------------------------------
# temperature=0.0: this is a factual business report, not creative writing. We
# want the most deterministic output possible so the same findings produce the
# same narrative and no figure gets "creatively" altered.
TEMPERATURE = 0.0
# ~250 words is roughly 350 tokens of visible text, but newer Gemini models also
# spend output tokens on hidden "thinking", so we leave generous headroom (>= 300).
MAX_OUTPUT_TOKENS = 4096
# google-genai's HttpOptions.timeout is in MILLISECONDS: 30_000 ms = 30 s (>= 10 s minimum).
TIMEOUT_MS = 30_000

SYSTEM_INSTRUCTION = (
    "You are a senior data analyst writing for Mamaearth's regional ops and finance heads. "
    "Write a business narrative of at most 250 words using the SCR structure with exactly "
    "three labeled sections, in this order: 'Situation', 'Complication', 'Resolution'. "
    "STRICT NUMBER RULE: every number in your output must come from the findings supplied "
    "in the user message and must appear with the same value - never invent, estimate, "
    "round differently, or derive new statistics. Write rupee amounts with the \u20b9 symbol, "
    "thousands separators and two decimals (e.g. \u20b91,234.50), and percentages with one "
    "decimal. Name the month in words (e.g. March). Recommend concrete actions, but do not "
    "attach numeric targets to them. No preamble before the Situation section."
)


# ---- helpers ----------------------------------------------------------------
def inr(x: float) -> str:
    return f"\u20b9{x:,.2f}"


def month_name(ym: str) -> str:
    return datetime.strptime(ym, "%Y-%m").strftime("%B")


def load_findings(path: Path = FINDINGS_PATH) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def build_user_prompt(findings: dict) -> str:
    """Interpolate every figure from the findings dict - nothing hardcoded."""
    pay = findings["return_rate_by_payment"]
    seg = findings["highest_risk_segment"]
    peak = findings["true_peak_month"]
    infl = findings["outlier_inflated_month"]
    return (
        "Write the SCR narrative from these verified findings (the only numbers you may use):\n"
        f"- Cleaned total revenue: {inr(findings['cleaned_total_revenue_inr'])}\n"
        f"- Raw (pre-cleaning) total revenue: {inr(findings['raw_total_revenue_inr'])}\n"
        f"- Gap between raw and cleaned revenue: "
        f"{inr(findings['duplicate_reconciliation_delta_inr'])}, entirely caused by "
        f"double-submitted duplicate orders removed during cleaning\n"
        f"- Return rate by payment method: COD {pay['COD']:.1f}%, "
        f"Card {pay['CARD']:.1f}%, UPI {pay['UPI']:.1f}%\n"
        f"- Highest-risk segment: {seg['payment_method']} orders in Tier-{seg['city_tier']} "
        f"cities at {seg['return_rate_pct']:.1f}% return rate\n"
        f"- True peak revenue month (outliers excluded): {month_name(peak['month'])} "
        f"({peak['month']}) at {inr(peak['revenue_inr'])}\n"
        f"- {month_name(infl['month'])} ({infl['month']}) looked like the best month at "
        f"{inr(infl['apparent_revenue_inr'])}, but that was inflated by two bulk orders; "
        f"corrected revenue is {inr(infl['corrected_revenue_inr'])}\n"
        "Situation = overall revenue picture; Complication = where returns and misleading "
        "numbers hurt; Resolution = what ops and finance should do next."
    )


# ---- offline path (Task 4) ---------------------------------------------------
def generate_scr_narrative_offline(findings: dict) -> dict:
    """Deterministic template narrative: no network, no API key, same dict shape."""
    pay = findings["return_rate_by_payment"]
    seg = findings["highest_risk_segment"]
    peak = findings["true_peak_month"]
    infl = findings["outlier_inflated_month"]
    pm, im = month_name(peak["month"]), month_name(infl["month"])

    narrative = (
        f"Situation\n"
        f"After cleaning, Mamaearth's order book totals {inr(findings['cleaned_total_revenue_inr'])}. "
        f"The raw order feed showed {inr(findings['raw_total_revenue_inr'])}; the "
        f"{inr(findings['duplicate_reconciliation_delta_inr'])} difference is entirely "
        f"double-submitted duplicate orders, not a real revenue change.\n\n"
        f"Complication\n"
        f"Returns are concentrated, not uniform. COD orders are returned at {pay['COD']:.1f}%, "
        f"against {pay['UPI']:.1f}% for UPI and {pay['CARD']:.1f}% for Card. The highest-risk "
        f"segment is {seg['payment_method']} in Tier-{seg['city_tier']} cities, where "
        f"{seg['return_rate_pct']:.1f}% of orders come back. Separately, {im} appeared to be "
        f"the best month at {inr(infl['apparent_revenue_inr'])}, but two bulk orders inflated "
        f"it; corrected, {im} is only {inr(infl['corrected_revenue_inr'])}.\n\n"
        f"Resolution\n"
        f"{pm} is the genuine peak month at {inr(peak['revenue_inr'])}. Ops should tighten "
        f"COD handling in Tier-{seg['city_tier']} cities (order confirmation, address "
        f"verification, prepaid incentives). Finance should report revenue outlier-adjusted "
        f"so bulk orders do not distort month rankings, and should require duplicate-order "
        f"protection at order intake."
    )
    return {"status": "success", "narrative": narrative, "tokens": None}


# ---- online path (Tasks 2 & 3) ----------------------------------------------
def _api_key():
    return os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")


def generate_scr_narrative(findings: dict, fallback: bool = True) -> dict:
    """
    Generate the SCR narrative with Gemini; the caller never sees a raw exception.

    Returns {"status": "success", "narrative": str, "tokens": int}
    or      {"status": "error", "narrative": None, "message": str}  (fallback=False).

    With fallback=True (default), a missing API key or an "error" result from the
    API call hands over to generate_scr_narrative_offline(findings).
    """
    if not _api_key():
        result = {"status": "error", "narrative": None,
                  "message": "No GEMINI_API_KEY / GOOGLE_API_KEY set"}
    else:
        try:
            from google import genai            # imported lazily so the offline path
            from google.genai import types      # works even without the package installed

            client = genai.Client(api_key=_api_key())
            config = types.GenerateContentConfig(
                system_instruction=SYSTEM_INSTRUCTION,   # role + structure + number rule
                temperature=TEMPERATURE,
                max_output_tokens=MAX_OUTPUT_TOKENS,
                http_options=types.HttpOptions(timeout=TIMEOUT_MS),
                # 2.5-series models spend output tokens on hidden "thinking"; switch it
                # off so the 250-word narrative is not starved by the token cap.
                thinking_config=(types.ThinkingConfig(thinking_budget=0)
                                 if "2.5" in MODEL and "pro" not in MODEL else None),
            )
            response = client.models.generate_content(
                model=MODEL,
                contents=build_user_prompt(findings),    # built from the findings dict
                config=config,
            )
            text = (response.text or "").strip()
            finish = str(getattr(response.candidates[0], "finish_reason", "")) if response.candidates else ""
            if "MAX_TOKENS" in finish:
                raise ValueError("Gemini output was cut off at max_output_tokens; narrative incomplete")
            if not text:
                raise ValueError("Gemini returned an empty response (possibly blocked or truncated)")
            tokens = getattr(response.usage_metadata, "total_token_count", None)
            result = {"status": "success", "narrative": text, "tokens": tokens}
        except Exception as err:  # noqa: BLE001 - deliberate catch-all; see docstring
            result = {"status": "error", "narrative": None, "message": str(err)}

    if result["status"] == "error" and fallback:
        return generate_scr_narrative_offline(findings)
    return result


# ---- numeric accuracy checker (Task 5) --------------------------------------
def required_figures(findings: dict) -> list:
    """(label, needles) - the five figures every narrative must contain."""
    def num(x: float) -> str:  # 97358.30 -> "97358.3" (also matches "97358.30")
        return f"{x:.2f}".rstrip("0").rstrip(".")
    peak = findings["true_peak_month"]
    return [
        ("cleaned total revenue", [num(findings["cleaned_total_revenue_inr"])]),
        ("COD return rate", [num(findings["return_rate_by_payment"]["COD"])]),
        ("COD + Tier-2 highest-risk segment rate", [num(findings["highest_risk_segment"]["return_rate_pct"])]),
        ("duplicate reconciliation delta", [num(findings["duplicate_reconciliation_delta_inr"])]),
        ("true peak month + revenue", [month_name(peak["month"]), num(peak["revenue_inr"])]),
    ]


def check_narrative(narrative: str, findings: dict) -> bool:
    """Assert all five figures appear (commas normalized); print PASS/FAIL per figure."""
    text = narrative.replace(",", "")
    all_ok = True
    for label, needles in required_figures(findings):
        hits = []
        for n in needles:
            if n.replace(".", "").isdigit():
                # not glued to other digits; tolerate a trailing 0 (97358.3 vs 97358.30)
                pattern = rf"(?<![\d.]){re.escape(n)}0*(?!\d)"
                hits.append(re.search(pattern, text) is not None)
            else:
                hits.append(n.lower() in text.lower())
        ok = all(hits)
        all_ok &= ok
        print(f"  [{'PASS' if ok else 'FAIL'}] {label}: {' + '.join(needles)}")
    print(f"  => {'ALL 5 FIGURES PRESENT' if all_ok else 'MISSING FIGURES'}")
    return all_ok


# ---- CLI ---------------------------------------------------------------------
def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")  # Windows consoles default to cp1252; keep the rupee sign
    ap = argparse.ArgumentParser(description="Generate the SCR narrative from findings.json")
    ap.add_argument("--offline", action="store_true", help="skip Gemini, use the offline template")
    ap.add_argument("--check-sample", action="store_true",
                    help="run the numeric checker on narrator/sample_output.txt and exit")
    ap.add_argument("--findings", default=str(FINDINGS_PATH), help="path to findings.json")
    args = ap.parse_args()

    if not Path(args.findings).exists():
        print(f"Missing {args.findings}. Run `python analysis/clean_and_eda.py` first.")
        return 2
    findings = load_findings(Path(args.findings))

    if args.check_sample:
        if not SAMPLE_PATH.exists():
            print(f"{SAMPLE_PATH.name} not found - run with a GEMINI_API_KEY set to create it.")
            return 2
        print(f"Checking saved sample: {SAMPLE_PATH.name}")
        return 0 if check_narrative(SAMPLE_PATH.read_text(encoding="utf-8"), findings) else 1

    used_gemini = False
    if args.offline:
        result = generate_scr_narrative_offline(findings)
        print("Path used: OFFLINE (forced by --offline)")
    else:
        result = generate_scr_narrative(findings, fallback=False)
        if result["status"] == "success":
            used_gemini = True
            print("Path used: GEMINI")
        else:
            print(f"Path used: OFFLINE (Gemini unavailable: {result['message']})")
            result = generate_scr_narrative_offline(findings)
    if result.get("tokens") is not None:
        print(f"Tokens used: {result['tokens']}")
    print("\n" + result["narrative"] + "\n")

    print("Numeric accuracy check:")
    ok = check_narrative(result["narrative"], findings)

    if used_gemini:
        SAMPLE_PATH.write_text(result["narrative"] + "\n", encoding="utf-8")
        print(f"\nSaved live Gemini output to {SAMPLE_PATH.name} "
              f"(verify any time with --check-sample).")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
