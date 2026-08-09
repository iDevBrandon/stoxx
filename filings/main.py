"""
Filings crawler — SEC EDGAR (XBRL) edition.

For each ticker in global500.csv, pulls the latest 10-Q's core financial-
statement facts from the SEC XBRL APIs and upserts them into `filings` +
`filing_facts` (Oxinion's public dataset). Free, no key, no daily cap, official
filer data. US SEC filers only — a ticker not in SEC's ticker→CIK map is
skipped with NO network call, so a global universe naturally reduces to its US
names (SEC excludes foreign issuers).

How it works, per ticker:
  1. submissions API  → the most recent 10-Q (accession, period end, filed date)
  2. companyfacts API → the value of each mapped us-gaap concept AS REPORTED in
                        that exact filing (matched by accession + period end)
  3. upsert one `filings` row (dedupe on accession_no) and replace its
     `filing_facts` (idempotent — re-running never duplicates).

No resume-skip: unlike a time-series crawl, we WANT to re-visit every ticker so
new quarters get picked up. Upsert-on-accession makes re-runs cheap and safe.

Values are stored in native XBRL units (full USD) with unit="USD" and a
provenance citation. Concepts are matched to the current-quarter figure
(~90-day duration for income items; point-in-time for balance-sheet items).

Env (.env locally / GitHub Actions secrets):
  FINANCE_SUPABASE_URL          Supabase project URL
  FINANCE_SUPABASE_SECRET_KEY   Supabase SECRET key (sb_secret_…) — needed for writes
  FIL_LIMIT     tickers to process this run (default 500)
  FIL_SLEEP     seconds between tickers (default 0.4 → 2 SEC calls each, under 10/s)
  FIL_CSV       universe csv (default global500.csv)
  FIL_SHARD/FIL_SHARDS   stride shard index / count (default 0 / 1)
  FIL_TICKERS   explicit tickers to (re)fetch — bypasses CSV
  FIL_UA        User-Agent for SEC (SEC requires a contact address)

  pip install -r requirements.txt
  python main.py                    # run from the stoxx/ root
"""
import os
import time
from datetime import date, datetime, timezone

import pandas as pd
import requests
from dotenv import load_dotenv
from supabase import Client, create_client

load_dotenv()

SUPABASE_URL = os.getenv("FINANCE_SUPABASE_URL")
SUPABASE_KEY = os.getenv("FINANCE_SUPABASE_SECRET_KEY")
if not SUPABASE_URL or not SUPABASE_KEY:
    raise SystemExit(
        "Missing Supabase creds. Set FINANCE_SUPABASE_URL and the SECRET key "
        "FINANCE_SUPABASE_SECRET_KEY (sb_secret_…) in .env."
    )

FIL_LIMIT = int(os.getenv("FIL_LIMIT", "500"))
FIL_SLEEP = float(os.getenv("FIL_SLEEP", "0.4"))
FIL_CSV = os.getenv("FIL_CSV", "global500.csv")
FIL_SHARD = int(os.getenv("FIL_SHARD", "0"))
FIL_SHARDS = int(os.getenv("FIL_SHARDS", "1"))
FIL_UNIVERSE_LIMIT = 500
FIL_TICKERS = os.getenv("FIL_TICKERS", "").strip()
HEADERS = {"User-Agent": os.getenv("FIL_UA", "filings-crawler")}

SEC_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
SEC_SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik:010d}.json"
SEC_FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json"

# key, label, statement, kind ("instant"|"duration"), [us-gaap concept aliases]
CONCEPTS = [
    ("revenue", "Revenue", "income_statement", "duration",
        ["RevenueFromContractWithCustomerExcludingAssessedTax", "Revenues", "SalesRevenueNet"]),
    ("cost_of_revenue", "Cost of revenue", "income_statement", "duration",
        ["CostOfRevenue", "CostOfGoodsAndServicesSold"]),
    ("gross_profit", "Gross profit", "income_statement", "duration", ["GrossProfit"]),
    ("operating_income", "Operating income", "income_statement", "duration", ["OperatingIncomeLoss"]),
    ("net_income", "Net income", "income_statement", "duration", ["NetIncomeLoss"]),
    ("total_assets", "Total assets", "balance_sheet", "instant", ["Assets"]),
    ("total_liabilities", "Total liabilities", "balance_sheet", "instant", ["Liabilities"]),
    ("equity", "Shareholders equity", "balance_sheet", "instant",
        ["StockholdersEquity", "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"]),
    ("cash", "Cash & equivalents", "balance_sheet", "instant",
        ["CashAndCashEquivalentsAtCarryingValue"]),
]

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


def fetch_cik_map() -> dict:
    r = requests.get(SEC_TICKERS_URL, headers=HEADERS, timeout=30)
    r.raise_for_status()
    return {row["ticker"].upper(): int(row["cik_str"]) for row in r.json().values()}


def lookup_cik(cik_map: dict, ticker: str):
    if not isinstance(ticker, str):
        return None
    up = ticker.upper()
    for cand in (up, up.replace(".", "-"), up.replace("-", ".")):
        if cand in cik_map:
            return cik_map[cand]
    return None


def latest_10q(cik: int):
    """Most recent 10-Q filing metadata from the submissions API."""
    r = requests.get(SEC_SUBMISSIONS_URL.format(cik=cik), headers=HEADERS, timeout=30)
    if r.status_code == 404:
        return None
    r.raise_for_status()
    recent = (r.json().get("filings") or {}).get("recent") or {}
    forms = recent.get("form") or []
    for i, form in enumerate(forms):
        if form == "10-Q":
            return {
                "accession": recent["accessionNumber"][i],
                "period_end": recent["reportDate"][i],
                "filed_at": recent["filingDate"][i],
                "primary": (recent.get("primaryDocument") or [""] * (i + 1))[i],
                "form": form,
            }
    return None


def _days(start: str, end: str) -> int:
    return (date.fromisoformat(end) - date.fromisoformat(start)).days


def pick_value(units_list, accession, period_end, kind):
    """The concept's value as reported in `accession` for `period_end`."""
    cands = [e for e in units_list
             if e.get("accn") == accession and e.get("end") == period_end
             and e.get("val") is not None]
    if not cands:
        return None
    if kind == "instant":
        return cands[0]["val"]
    for e in cands:                       # duration → current quarter (~90d)
        s = e.get("start")
        if s and 80 <= _days(s, period_end) <= 100:
            return e["val"]
    return None


def build_facts(cik: int, filing: dict) -> list:
    """One row per mapped concept found in the filing (value in native USD)."""
    r = requests.get(SEC_FACTS_URL.format(cik=cik), headers=HEADERS, timeout=60)
    if r.status_code == 404:
        return []
    r.raise_for_status()
    us_gaap = ((r.json().get("facts") or {}).get("us-gaap")) or {}

    acc, pend = filing["accession"], filing["period_end"]
    out = []
    for key, label, statement, kind, aliases in CONCEPTS:
        val = None
        for concept in aliases:
            node = us_gaap.get(concept)
            if not node:
                continue
            units = (node.get("units") or {}).get("USD")
            if not units:
                continue
            val = pick_value(units, acc, pend, kind)
            if val is not None:
                break
        if val is None:
            continue
        out.append({
            "key": key, "label": label, "statement": statement,
            "value": float(val), "value_text": f"${float(val):,.0f}",
            "unit": "USD",
        })
    return out


def quarter_of(period_end: str) -> int:
    return (int(period_end[5:7]) - 1) // 3 + 1


def upsert_filing(ticker: str, name: str, cik: int, filing: dict, facts: list) -> int:
    now = datetime.now(timezone.utc).isoformat()
    year = int(filing["period_end"][:4])
    q = quarter_of(filing["period_end"])
    acc_nodash = filing["accession"].replace("-", "")
    row = {
        "ticker": ticker,
        "company_name": name or None,
        "form_type": "10-Q",
        "fiscal_period": f"Q{q} {year}",
        "fiscal_year": year,
        "fiscal_quarter": q,
        "period_end": filing["period_end"],
        "filed_at": filing["filed_at"],
        "cik": f"{cik:010d}",
        "accession_no": filing["accession"],
        "source_url": (
            f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc_nodash}/{filing['primary']}"
            if filing.get("primary") else None
        ),
        "status": "ready",
        "updated_at": now,
    }
    res = supabase.table("filings").upsert(row, on_conflict="accession_no").execute()
    if res.data:
        filing_id = res.data[0]["id"]
    else:  # some PostgREST configs don't return the row on conflict-update
        sel = supabase.table("filings").select("id").eq(
            "accession_no", filing["accession"]).limit(1).execute()
        filing_id = sel.data[0]["id"]

    # Replace facts for this filing (idempotent).
    supabase.table("filing_facts").delete().eq("filing_id", filing_id).execute()
    if facts:
        fact_rows = [{
            "filing_id": filing_id,
            "ticker": ticker,
            "fiscal_period": f"Q{q} {year}",
            "statement": f["statement"],
            "key": f["key"],
            "label": f["label"],
            "value": f["value"],
            "value_text": f["value_text"],
            "unit": f["unit"],
            "period": filing["period_end"],
            "citation": f"10-Q · SEC XBRL · {filing['accession']}",
            "confidence": 1.0,
        } for f in facts]
        supabase.table("filing_facts").insert(fact_rows).execute()

    # Latest-only: we are NOT a history archive. Drop this ticker's older
    # filings (any other accession) so exactly one row per ticker remains —
    # its facts cascade-delete with it.
    supabase.table("filings").delete().eq("ticker", ticker).neq(
        "accession_no", filing["accession"]).execute()
    return len(facts)


def fetch_stored_accessions() -> dict:
    """{ticker: accession_no} already in `filings` (one row per ticker), so an
    unchanged latest filing is skipped without a heavy companyfacts pull."""
    res = supabase.table("filings").select("ticker,accession_no").execute()
    return {r["ticker"]: r["accession_no"]
            for r in (res.data or []) if r.get("accession_no")}


def main():
    if FIL_TICKERS:
        names = [t.strip().upper() for t in FIL_TICKERS.split(",") if t.strip()]
        batch = pd.DataFrame({"Ticker": names, "Name": names})
        print(f"Explicit tickers: {', '.join(names)}\n")
    else:
        df = pd.read_csv(FIL_CSV, dtype={"Symbol": str}, keep_default_na=False) \
            .rename(columns={"Symbol": "Ticker"})[["Ticker", "Name"]]
        df["Ticker"] = df["Ticker"].str.strip()
        df = df[df["Ticker"] != ""]
        if FIL_UNIVERSE_LIMIT > 0:
            df = df.head(FIL_UNIVERSE_LIMIT)
        if FIL_SHARDS > 1:
            df = df.iloc[FIL_SHARD::FIL_SHARDS]
        batch = df.head(FIL_LIMIT)
        print(f"Shard {FIL_SHARD}/{FIL_SHARDS} · rows {len(batch)} · sleep {FIL_SLEEP}s\n")

    cik_map = fetch_cik_map()
    print(f"SEC ticker→CIK map: {len(cik_map)} US filers")
    stored = {} if FIL_TICKERS else fetch_stored_accessions()
    if stored:
        print(f"Already stored: {len(stored)} tickers (unchanged ones are skipped)")
    print()

    ok = empty = skipped = failed = unchanged = 0
    rows_iter = list(batch.itertuples(index=False))
    for i, r in enumerate(rows_iter):
        ticker, name = str(r.Ticker).strip(), r.Name
        if not ticker:
            continue
        cik = lookup_cik(cik_map, ticker)
        if cik is None:
            print(f"[{i + 1}/{len(rows_iter)}] {ticker}  non-US → skip")
            skipped += 1
            continue
        print(f"[{i + 1}/{len(rows_iter)}] {ticker} ({name})  CIK {cik}")
        try:
            filing = latest_10q(cik)
            if not filing:
                print("  ℹ️ no 10-Q found")
                empty += 1
                time.sleep(FIL_SLEEP)
                continue
            if not FIL_TICKERS and stored.get(ticker) == filing["accession"]:
                print(f"  ⏭️ unchanged ({filing['accession']})")
                unchanged += 1
                time.sleep(FIL_SLEEP)
                continue
            facts = build_facts(cik, filing)
            n = upsert_filing(ticker, name, cik, filing, facts)
            if n:
                print(f"  ✅ {filing['period_end']} · {n} facts")
                ok += 1
            else:
                print(f"  ℹ️ 10-Q {filing['period_end']} but no mapped facts")
                empty += 1
        except Exception as e:
            print(f"  ❌ failed: {e}")
            failed += 1
        time.sleep(FIL_SLEEP)

    print(f"\n✅ {ok} updated   ⏭️ {unchanged} unchanged   ℹ️ {empty} no-facts   "
          f"⏭️ {skipped} non-US   ❌ {failed} failed")


if __name__ == "__main__":
    main()
