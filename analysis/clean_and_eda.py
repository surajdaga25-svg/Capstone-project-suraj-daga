"""
Part 2 - Python/Pandas data wrangling & EDA (independent of the SQL database).

Run:  python analysis/clean_and_eda.py

Reads data/orders.csv, data/customers.csv, data/products.csv directly, cleans
orders in code (never by editing the CSVs), prints every intermediate result,
and finishes by writing narrator/findings.json (Part 3, Task 1) from the
computed numbers - nothing in that file is hand-typed.

Layout of this file:
  * compute_pipeline()  - pure computation, no printing, returns a results dict.
                          visualize.py imports it so charts always match the EDA.
  * main()              - prints every step the acceptance criteria reference,
                          then exports findings.json.
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
FINDINGS_PATH = ROOT / "narrator" / "findings.json"

# Everything except order_id: the 5 double-submit rows differ only by order_id.
NATURAL_KEY = [
    "customer_id", "product_id", "order_date", "quantity",
    "discount_pct", "payment_method", "rating", "returned",
]


def band(r: float) -> str:
    """Taught correlation-strength bands on |r|."""
    a = abs(r)
    if a < 0.2:
        return "negligible"
    if a < 0.4:
        return "weak"
    if a < 0.7:
        return "moderate"
    return "strong"


def add_order_value(df: pd.DataFrame) -> pd.DataFrame:
    """order_value = quantity * price * (1 - discount_pct/100)."""
    out = df.copy()
    out["order_value"] = out["quantity"] * out["price"] * (1 - out["discount_pct"].fillna(0) / 100)
    return out


def compute_pipeline() -> dict:
    R = {}  # results

    # ---- Task 1: load -------------------------------------------------------
    orders_raw = pd.read_csv(DATA_DIR / "orders.csv")
    customers = pd.read_csv(DATA_DIR / "customers.csv")
    products = pd.read_csv(DATA_DIR / "products.csv")
    R.update(orders_raw=orders_raw, customers=customers, products=products)

    # ---- Task 2: standardize payment_method ---------------------------------
    R["pay_unique_before"] = list(orders_raw["payment_method"].unique())
    orders = orders_raw.copy()
    orders["payment_method"] = orders["payment_method"].str.strip().str.upper()
    R["pay_counts_after"] = orders["payment_method"].value_counts()

    # ---- Task 3: remove duplicates ------------------------------------------
    dup_mask = orders.duplicated(subset=NATURAL_KEY, keep="first")
    R["dup_count"] = int(dup_mask.sum())
    R["dropped_rows"] = orders[dup_mask].copy()
    R["dropped_ids"] = list(orders.loc[dup_mask, "order_id"])
    orders_clean = orders[~dup_mask].copy().reset_index(drop=True)
    R["orders_clean_shape"] = orders_clean.shape

    # ---- Task 4: impute missing values (counts on the deduplicated frame) ---
    R["disc_na"] = int(orders_clean["discount_pct"].isna().sum())
    R["rating_na"] = int(orders_clean["rating"].isna().sum())
    R["rating_median"] = float(orders_clean["rating"].median())  # NaNs skipped
    orders_clean["discount_pct"] = orders_clean["discount_pct"].fillna(0)
    orders_clean["rating"] = orders_clean["rating"].fillna(R["rating_median"])
    R["null_after"] = orders_clean[["discount_pct", "rating"]].isnull().sum().to_dict()

    # ---- Task 5: merge & reconcile against Part 1 ---------------------------
    merged = (orders_clean
              .merge(products, on="product_id", how="left")
              .merge(customers, on="customer_id", how="left"))
    merged = add_order_value(merged)
    R["merged"] = merged
    R["cleaned_total"] = round(float(merged["order_value"].sum()), 2)

    # Raw total recomputed independently in pandas (what SQL Report (a) computes):
    # all 180 rows, NULL discount treated as 0%.
    raw_merged = add_order_value(orders_raw.merge(products, on="product_id", how="left"))
    R["raw_total"] = round(float(raw_merged["order_value"].sum()), 2)
    # Independent check: order_value of the 5 dropped duplicate rows.
    dropped_val = add_order_value(R["dropped_rows"].merge(products, on="product_id", how="left"))
    R["dup_value"] = round(float(dropped_val["order_value"].sum()), 2)
    R["delta"] = round(R["raw_total"] - R["cleaned_total"], 2)

    # ---- Task 6: IQR outliers on quantity (flag, do not drop) ---------------
    q = merged["quantity"]
    q1, q3 = float(q.quantile(0.25)), float(q.quantile(0.75))
    iqr = q3 - q1
    lower, upper = q1 - 1.5 * iqr, q3 + 1.5 * iqr
    merged["is_outlier"] = (q < lower) | (q > upper)
    R.update(q1=q1, q3=q3, iqr=iqr, lower=lower, upper=upper)
    R["outliers"] = merged.loc[merged["is_outlier"],
                               ["order_id", "order_date", "quantity", "order_value"]]

    # ---- Task 7: COD return-rate hypothesis ---------------------------------
    R["pay_stats"] = merged.groupby("payment_method")["returned"].agg(["count", "mean"])
    R["pay_rate_pct"] = (R["pay_stats"]["mean"] * 100).round(1)

    # ---- Task 8: multi-level segmentation -----------------------------------
    seg = (merged.groupby(["payment_method", "city_tier"])["returned"]
                 .agg(orders="count", returns="sum", return_rate="mean").reset_index())
    seg["return_rate_pct"] = (seg["return_rate"] * 100).round(1)
    R["segments"] = seg
    R["top_segment"] = seg.loc[seg["return_rate"].idxmax()]

    # ---- Task 9: correlations ------------------------------------------------
    corr_cols = ["rating", "returned", "discount_pct", "quantity"]
    corr = merged[corr_cols].corr()
    R["corr"] = corr
    R["corr_pairs"] = [(a, b, float(corr.loc[a, b]), band(corr.loc[a, b]))
                       for i, a in enumerate(corr_cols) for b in corr_cols[i + 1:]]

    # ---- Task 10: outlier-corrected monthly revenue --------------------------
    merged["order_date"] = pd.to_datetime(merged["order_date"])
    merged["year_month"] = merged["order_date"].dt.strftime("%Y-%m")
    R["monthly_incl"] = merged.groupby("year_month")["order_value"].sum().round(2)
    R["monthly_excl"] = (merged[~merged["is_outlier"]]
                         .groupby("year_month")["order_value"].sum().round(2))
    R["merged"] = merged
    return R


def export_findings(R: dict, path: Path = FINDINGS_PATH) -> dict:
    """Write narrator/findings.json from computed values (never hand-typed)."""
    peak_corr = R["monthly_excl"].idxmax()
    infl = R["monthly_incl"].idxmax()
    pay = R["pay_rate_pct"]
    seg = R["top_segment"]
    findings = {
        "cleaned_total_revenue_inr": R["cleaned_total"],
        "raw_total_revenue_inr": R["raw_total"],
        "duplicate_reconciliation_delta_inr": R["delta"],
        "return_rate_by_payment": {k: float(pay[k]) for k in ["COD", "CARD", "UPI"]},
        "highest_risk_segment": {
            "payment_method": str(seg["payment_method"]),
            "city_tier": int(seg["city_tier"]),
            "return_rate_pct": float(seg["return_rate_pct"]),
        },
        "true_peak_month": {
            "month": str(peak_corr),
            "revenue_inr": float(R["monthly_excl"][peak_corr]),
        },
        "outlier_inflated_month": {
            "month": str(infl),
            "apparent_revenue_inr": float(R["monthly_incl"][infl]),
            "corrected_revenue_inr": float(R["monthly_excl"][infl]),
        },
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(findings, f, indent=2)
        f.write("\n")
    return findings


def hr(title: str) -> None:
    print("\n" + "=" * 78 + f"\n{title}\n" + "=" * 78)


def main() -> None:
    pd.set_option("display.width", 140)
    R = compute_pipeline()
    merged = R["merged"]

    hr("TASK 1 - Load and inspect")
    print("orders.shape    :", R["orders_raw"].shape)
    print("customers.shape :", R["customers"].shape)
    print("products.shape  :", R["products"].shape)

    hr("TASK 2 - Standardize payment_method casing")
    print("unique raw values (", len(R["pay_unique_before"]), "):", R["pay_unique_before"])
    print("after .str.strip().str.upper() value counts:")
    print(R["pay_counts_after"].to_string())

    hr("TASK 3 - Remove duplicate orders")
    print("natural key:", NATURAL_KEY)
    print("duplicates flagged:", R["dup_count"])
    print("dropped order_ids :", R["dropped_ids"])
    print("orders_clean.shape:", R["orders_clean_shape"])

    hr("TASK 4 - Impute missing values (on deduplicated frame)")
    print("discount_pct NaN rows :", R["disc_na"], "-> filled with 0 (no promo code applied)")
    print("median of non-null ratings before imputing:", R["rating_median"])
    print("rating NaN rows       :", R["rating_na"], f"-> filled with median {R['rating_median']}")
    print("nulls after imputing  :", R["null_after"])

    hr("TASK 5 - Merge and reconcile against Part 1")
    print(f"Total order_value, 175 cleaned rows : Rs {R['cleaned_total']:,.2f}")
    print(f"Raw total (180 rows, = SQL Report a): Rs {R['raw_total']:,.2f}")
    print(f"Delta (raw - cleaned)               : Rs {R['delta']:,.2f}")
    print(f"Independent check, order_value of the 5 dropped rows {R['dropped_ids']}: "
          f"Rs {R['dup_value']:,.2f}")
    assert abs(R["delta"] - R["dup_value"]) < 0.005, "delta is not fully explained by duplicates"
    print("\nRECONCILIATION NOTE:")
    print(
        f"Part 1 Report (a) computed Rs {R['raw_total']:,.2f} on the raw 180 orders, while this "
        f"pipeline totals Rs {R['cleaned_total']:,.2f} on the 175 cleaned orders - a gap of "
        f"Rs {R['delta']:,.2f}. That gap is entirely due to the {R['dup_count']} double-submitted "
        f"duplicate orders ({', '.join(R['dropped_ids'])}) removed in Task 3: summing the "
        f"order_value of exactly those {R['dup_count']} rows independently gives Rs "
        f"{R['dup_value']:,.2f}, which matches the delta to the paisa. It is NOT caused by "
        f"the discount_pct / rating imputation: Part 1 already treated a NULL discount as 0% "
        f"(COALESCE), and filling discount_pct with 0 or ratings with the median changes no "
        f"order_value, so imputation contributes Rs 0.00 to the difference."
    )

    hr("TASK 6 - IQR outlier detection on quantity")
    print(f"Q1={R['q1']}  Q3={R['q3']}  IQR={R['iqr']}  lower={R['lower']}  upper={R['upper']}")
    print(f"rows outside [{R['lower']}, {R['upper']}]: {len(R['outliers'])}")
    print(R["outliers"].to_string(index=False))
    print("Rows are kept in the dataset and flagged in column is_outlier.")

    hr("TASK 7 - Hypothesis: COD orders have a higher return rate than Card/UPI")
    print("HYPOTHESIS: Cash-on-delivery orders are returned more often than prepaid (Card/UPI) orders.")
    print(R["pay_stats"].to_string())
    print("Return rate % by payment method:", R["pay_rate_pct"].to_dict())
    cod_highest = R["pay_rate_pct"].idxmax() == "COD"
    print("HYPOTHESIS RESULT:", "CONFIRMED" if cod_highest else "NOT CONFIRMED",
          f"- COD {R['pay_rate_pct']['COD']}% vs CARD {R['pay_rate_pct']['CARD']}% "
          f"vs UPI {R['pay_rate_pct']['UPI']}%")

    hr("TASK 8 - Multi-level segmentation: payment_method x city_tier")
    print(R["segments"][["payment_method", "city_tier", "orders", "returns", "return_rate_pct"]]
          .to_string(index=False))
    s = R["top_segment"]
    print(f"\nHIGHEST-RISK SEGMENT: {s['payment_method']} + Tier-{int(s['city_tier'])} cities "
          f"at {s['return_rate_pct']}% ({int(s['returns'])} of {int(s['orders'])} orders returned)")
    seg = R["segments"]
    t1 = seg[(seg.payment_method == "COD") & (seg.city_tier == 1)].iloc[0]
    t2 = seg[(seg.payment_method == "COD") & (seg.city_tier == 2)].iloc[0]
    print(f"COD risk is NOT uniform across tiers: {int(t1['orders'])} Tier-1 COD orders at "
          f"{t1['return_rate_pct']}% vs {int(t2['orders'])} Tier-2 COD orders at "
          f"{t2['return_rate_pct']}% - the blended COD rate hides where the problem concentrates.")

    hr("TASK 9 - Correlation analysis")
    print(R["corr"].round(3).to_string())
    print("\nBands: negligible 0-0.19 | weak 0.2-0.39 | moderate 0.4-0.69 | strong 0.7-1.0")
    for a, b, r, lab in R["corr_pairs"]:
        print(f"  {a:>12} vs {b:<12} r = {r:+.3f}  -> {lab}")
    all_negl = all(lab == "negligible" for *_, lab in R["corr_pairs"])
    print("All six pairs negligible (|r| < 0.2):", all_negl)
    r_dr = R["corr"].loc["discount_pct", "returned"]
    busted = (r_dr > -0.2)  # a reducing effect would need at least a weak negative r
    print(f'HYPOTHESIS "higher discounts reduce returns": '
          f'{"BUSTED" if busted else "SUPPORTED"} (discount_pct vs returned r = {r_dr:+.3f}, '
          f'{band(r_dr)})')

    hr("TASK 10 - Outlier-corrected monthly revenue")
    print("(1) INCLUDING the two outlier orders:")
    print(R["monthly_incl"].map("{:,.2f}".format).to_string())
    print("\n(2) EXCLUDING the two outlier orders (outlier-corrected):")
    print(R["monthly_excl"].map("{:,.2f}".format).to_string())
    infl, true_peak = R["monthly_incl"].idxmax(), R["monthly_excl"].idxmax()
    o = R["outliers"].sort_values("order_id")
    parts = "; ".join(f"{r.order_id} on {pd.to_datetime(r.order_date).date()}" for r in o.itertuples())
    print(f"\nFINDING: {infl}'s apparent lead (Rs {R['monthly_incl'][infl]:,.2f}) is an artifact of "
          f"the two bulk orders landing in that month ({parts}). Excluding them, {infl} falls to "
          f"Rs {R['monthly_excl'][infl]:,.2f} and {pd.Period(true_peak).strftime('%B')} "
          f"({true_peak}, Rs {R['monthly_excl'][true_peak]:,.2f}) is the genuine peak month.")

    hr("EXPORT - narrator/findings.json (feeds Part 3)")
    findings = export_findings(R)
    print(json.dumps(findings, indent=2))
    print(f"\nWrote {FINDINGS_PATH.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
