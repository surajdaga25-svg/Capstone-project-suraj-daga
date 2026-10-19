# Mamaearth Returns & Growth Intelligence Pipeline

A three-layer pipeline that proves, end to end, where returns are eating into Mamaearth's margins:

1. **SQL layer** - a relational store (SQLite) plus report queries over the raw order data.
2. **Python analysis layer** - a pandas pipeline that cleans the data, finds and quantifies the real patterns, draws two charts, and **exports the verified numbers**.
3. **GenAI narrator layer** - turns those verified numbers into a Situation-Complication-Resolution (SCR) narrative for regional ops and finance heads, using the Gemini API with a fully keyless offline fallback.

No layer reports a number it did not compute itself or receive from the layer before it.

## Repository structure

```
.
├── README.md
├── sql/
│   ├── schema.sql                # CREATE TABLE for customers, products, orders
│   ├── seed_data.sql             # INSERTs generated from data/*.csv (blank cells -> NULL)
│   └── reports.sql               # reports (a)-(i); exact output pasted as a comment above each query
├── data/
│   ├── customers.csv             # 45 rows  - raw source data, never edited
│   ├── products.csv              # 16 rows
│   └── orders.csv                # 180 rows (messy on purpose: casing, NULLs, 5 duplicates)
├── analysis/
│   ├── clean_and_eda.py          # Part 2: clean, merge, reconcile, EDA; writes narrator/findings.json
│   └── visualize.py              # Part 2: the two charts (reuses clean_and_eda's pipeline)
├── visualizations/
│   ├── return_rate_by_payment.png
│   └── monthly_revenue_trend.png
└── narrator/
    ├── findings.json             # written by clean_and_eda.py - never hand-typed
    ├── generate_narrative.py     # Part 3: Gemini SCR narrative + offline fallback + numeric checker
    └── sample_output.txt         # saved live-Gemini output (created by step 3 below when a key is set)
```

## How data flows between the layers

```
data/*.csv ──► sql/schema.sql + seed_data.sql ──► sql/reports.sql      (Layer 1: raw-data SQL reports)
     │
     └────────► analysis/clean_and_eda.py ──► narrator/findings.json   (Layer 2: cleaned, verified numbers)
                       │                              │
                       └► analysis/visualize.py       └► narrator/generate_narrative.py ─► SCR narrative
                          (re-runs the same pipeline,    (Layer 3: reads ONLY findings.json)
                           writes visualizations/*.png)
```

* **SQL -> Python:** Layer 2 reads the same raw CSVs directly (not the database), so Layers 1 and 2 can be run in either order. They are tied together by reconciliation: SQL Report (a) gives the raw total of **₹99,860.20**; Python's cleaned total is **₹97,358.30**; the **₹2,501.90** gap is exactly the order value of the 5 duplicate rows Python removes.
* **Python -> narrator:** the end of `clean_and_eda.py` writes `narrator/findings.json` from computed values. `generate_narrative.py` reads only that file, so the narrative can never drift from the analysis.
* **Charts:** `visualize.py` imports the pipeline from `clean_and_eda.py` and recomputes everything from the raw CSVs, so the PNGs always match the EDA output.

## Setup

Python 3.9+ is required. SQLite ships with Python, so no database server is needed.

```bash
pip install pandas numpy matplotlib google-genai
```

(`google-genai` is only needed for the live Gemini path; the offline narrator path runs without it.)

## Run order (reproduce every number by following this top to bottom)

All commands are run from the repository root.

### 1. SQL layer - load the schema + seed data and run the reports

With the `sqlite3` command-line tool:

```bash
sqlite3 mamaearth.db < sql/schema.sql
sqlite3 mamaearth.db < sql/seed_data.sql
sqlite3 mamaearth.db "SELECT COUNT(*) FROM customers; SELECT COUNT(*) FROM products; SELECT COUNT(*) FROM orders;"   # 45, 16, 180
sqlite3 -header -column mamaearth.db < sql/reports.sql
```

No `sqlite3` CLI? Python's built-in module does the same job:

```bash
python -c "import sqlite3; c=sqlite3.connect('mamaearth.db'); [c.executescript(open(f'sql/{f}.sql').read()) for f in ('schema','seed_data','reports')]"
```

Notes:
* `seed_data.sql` is plain `INSERT` statements generated from the CSVs, with blank `discount_pct` / `rating` cells written as real SQL `NULL` (no `.import` cleanup needed). To reload from scratch, delete `mamaearth.db` and run the three files again.
* `reports.sql` ends with `ALTER TABLE ... ADD COLUMN loyalty_tier`, which fails if the column already exists, so delete `mamaearth.db` and reload before running it a second time.
* The expected result of every report is pasted as a comment directly above its query.

### 2. Python analysis layer - clean, analyze, chart

```bash
python analysis/clean_and_eda.py     # prints every intermediate result; Task 5/export step writes narrator/findings.json
python analysis/visualize.py         # writes visualizations/return_rate_by_payment.png and monthly_revenue_trend.png
```

`clean_and_eda.py` does all cleaning in code (the source CSVs are never edited): standardizes `payment_method` casing, drops 5 duplicate orders, imputes missing values, merges the three tables, reconciles against SQL, flags quantity outliers, tests the COD hypothesis, segments by payment x city tier, correlates the numeric fields, and builds the outlier-corrected monthly revenue. **Its final step writes `narrator/findings.json`**, which Layer 3 consumes.

### 3. GenAI narrator layer - generate the SCR narrative

```bash
# (a) No key at all -> deterministic offline narrator. Zero configuration, no network.
python narrator/generate_narrative.py

# (b) With a free Gemini API key -> live Gemini narrative
export GEMINI_API_KEY="your-key-here"          # macOS/Linux
#   setx GEMINI_API_KEY "your-key-here"        # Windows (then open a new terminal)
#   $env:GEMINI_API_KEY="your-key-here"        # Windows PowerShell, current session
python narrator/generate_narrative.py
```

* Get a **free** key from [Google AI Studio](https://aistudio.google.com/apikey) (free usage tier - never use a paid-only key). `GOOGLE_API_KEY` is also accepted.
* **No key set -> offline path.** If no key is configured, or the Gemini call returns an error (network down, quota, bad key), the script automatically falls back to `generate_scr_narrative_offline()`, an f-string template built from `findings.json`. The output says which path was used. `--offline` forces it.
* When the live call succeeds, the narrative is saved to **`narrator/sample_output.txt`**. Re-verify that saved text any time, without calling the API:
  ```bash
  python narrator/generate_narrative.py --check-sample
  ```
* The default model is `gemini-2.5-flash`; override with `GEMINI_MODEL` if Google renames or retires it.
* Generation is locked for a factual report: `temperature=0.0`, `max_output_tokens=4096`, a 30-second request timeout (the SDK takes milliseconds), and the role/structure/number-rule in a separate `system_instruction`. The call is wrapped in `try/except`, so callers always receive a structured dict and never a raw exception.

**Numeric accuracy check:** after every run the script asserts that the narrative contains all five required figures (commas normalized) and prints a PASS/FAIL line for each: cleaned total revenue (97,358.30), COD return rate (44.4), highest-risk segment rate (54.5), duplicate reconciliation delta (2,501.90), and the true peak month with its revenue (March, 20,318.90).

## Verified numbers (what each layer should print)

| Figure | Value | Where it comes from |
|---|---|---|
| Orders / customers / products loaded | 180 / 45 / 16 | SQL Task 2; `clean_and_eda.py` Task 1 |
| Raw total revenue | ₹99,860.20 (AOV ₹554.78) | `reports.sql` (a); recomputed in pandas |
| Unrated orders | 15 (180 vs 165) | `reports.sql` (b) |
| Cities with return rate > 20% | Jaipur 42.1, Lucknow 30.6, Bangalore 24.2 | `reports.sql` (d) |
| Payment values before / after cleaning | 7 -> 3 (CARD 70, UPI 55, COD 55) | `clean_and_eda.py` Task 2 |
| Duplicates dropped | 5 (O0176-O0180) -> 175 rows | `clean_and_eda.py` Task 3 |
| Imputed | 12 discounts -> 0; 15 ratings -> median 3.0 | `clean_and_eda.py` Task 4 |
| Cleaned total revenue | ₹97,358.30 | `clean_and_eda.py` Task 5 |
| Reconciliation delta | ₹2,501.90 = value of the 5 duplicate rows | `clean_and_eda.py` Task 5 |
| Quantity outliers (IQR, bounds -0.5 / 3.5) | O0011 (25), O0098 (30) | `clean_and_eda.py` Task 6 |
| Return rate by payment | COD 44.4%, UPI 18.9%, CARD 14.7% | `clean_and_eda.py` Task 7 |
| Highest-risk segment | COD + Tier-2 at 54.5% (Tier-1 COD 37.5%) | `clean_and_eda.py` Task 8 |
| Discount vs returns correlation | -0.09 (negligible) - "discounts reduce returns" is busted | `clean_and_eda.py` Task 9 |
| Peak month | Jan looks highest (₹29,582.10) but is an outlier artifact (₹11,637.10 corrected); **March ₹20,318.90** is the real peak | `clean_and_eda.py` Task 10 |
