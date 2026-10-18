"""
Part 2, Task 11 - two visualizations.

Run (after, or independently of, clean_and_eda.py):  python analysis/visualize.py

Both charts are rebuilt from the raw CSVs on every run by reusing
compute_pipeline() from clean_and_eda.py, so the plotted numbers are always
identical to the EDA output - no manual editing of intermediate files.
"""
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # headless-safe: write PNGs without needing a display
import matplotlib.pyplot as plt
import matplotlib.ticker  # noqa: F401
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from clean_and_eda import ROOT, compute_pipeline  # noqa: E402

OUT_DIR = ROOT / "visualizations"


def plot_return_rate_by_payment(R: dict) -> Path:
    rates = R["pay_rate_pct"].sort_values(ascending=False)  # descending
    ratio = rates["COD"] / rates["CARD"]
    colors = ["#c0392b" if m == "COD" else "#7f8c8d" for m in rates.index]

    fig, ax = plt.subplots(figsize=(7, 5))
    bars = ax.bar(rates.index, rates.values, color=colors, width=0.6)
    for bar, v in zip(bars, rates.values):
        ax.text(bar.get_x() + bar.get_width() / 2, v + 0.8, f"{v:.1f}%",
                ha="center", va="bottom", fontsize=11, fontweight="bold")
    ax.set_title(f"COD Returns at {rates['COD']:.1f}% \u2014 {ratio:.0f}x Card",
                 fontsize=14, fontweight="bold")
    ax.set_xlabel("Payment method (cleaned)")
    ax.set_ylabel("Return rate (%)")
    ax.set_ylim(0, rates.max() * 1.18)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()

    path = OUT_DIR / "return_rate_by_payment.png"
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


def plot_monthly_revenue_trend(R: dict) -> Path:
    s = R["monthly_excl"]  # outlier-corrected series (NOT the inflated one)
    peak = s.idxmax()
    peak_name = pd.Period(peak).strftime("%B %Y")

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.plot(s.index, s.values, marker="o", linewidth=2.2, color="#2c7fb8")
    ax.scatter([peak], [s[peak]], s=140, color="#c0392b", zorder=5)
    for x, v in s.items():
        ax.annotate(f"\u20b9{v:,.0f}", (x, v), textcoords="offset points",
                    xytext=(0, 12), ha="center", fontsize=9,
                    bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="none", alpha=0.85))
    ax.set_title(f"Outlier-Corrected Monthly Revenue Peaks in {peak_name}\n"
                 f"(\u20b9{s[peak]:,.2f})", fontsize=13, fontweight="bold")
    ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:,.0f}"))
    ax.set_xlabel("Month")
    ax.set_ylabel("Revenue (\u20b9 INR)")
    ax.set_ylim(0, s.max() * 1.18)
    ax.grid(axis="y", alpha=0.3)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()

    path = OUT_DIR / "monthly_revenue_trend.png"
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    R = compute_pipeline()
    for p in (plot_return_rate_by_payment(R), plot_monthly_revenue_trend(R)):
        print("Saved", p.relative_to(ROOT))


if __name__ == "__main__":
    main()
