"""
EPS history crawler — Alpha Vantage EARNINGS edition.

Alpha Vantage's EARNINGS endpoint returns deep reported-EPS history for both
annual and quarterly periods, and for quarters also the analyst estimate +
surprise. This script upserts it all into the `eps_history` table.

NOTE: use the primary listing symbol — e.g. GOOGL, not GOOG (some share
classes / lowercase symbols return empty).

RESUME-SKIP: each run skips tickers already in `eps_history` (via the
`eps_history_tickers` view) plus known-empty symbols (local .eps_empty.txt),
and processes only the next EPS_LIMIT *unseen* tickers. So you can run it
repeatedly — with a fresh key each time — and it walks straight through the
universe without repeating work.

KEY ROTATION: ALPHAVANTAGE_API_KEY may be a comma-separated list. When a key
hits its Alpha Vantage daily cap, the crawler rotates to the next key and
retries the same ticker — so N keys ≈ N × 25 tickers in a single run.

Env (.env locally / GitHub Actions secrets):
  ALPHAVANTAGE_API_KEY   Alpha Vantage key — one, or comma-separated list
  FINANCE_SUPABASE_URL   Supabase project URL
  FINANCE_SECRET_KEY     Supabase SECRET key (sb_secret_…) — needed for writes
  EPS_LIMIT              NEW (unseen) tickers to process this run (default 25)
  EPS_SLEEP              seconds between API calls (default 13 → under AV's
                         5-requests-per-minute limit; lower only for tiny tests)
  EPS_CSV               universe csv (default global500.csv)
  EPS_SKIP_FILE         local file of known-empty symbols (default .eps_empty.txt)

Examples:
  # one key, next 25 unseen tickers
  ALPHAVANTAGE_API_KEY=KEY1 EPS_LIMIT=25 python eps/main.py
  # five keys, next 125 unseen tickers in one run
  ALPHAVANTAGE_API_KEY=K1,K2,K3,K4,K5 EPS_LIMIT=125 python eps/main.py
  # test/refresh one specific ticker (ignores resume-skip)
  EPS_TICKERS=META python eps/main.py

  pip install -r requirements.txt   # requests, pandas, supabase, python-dotenv
  python main.py                    # run from the stoxx/ root
"""
import os
import time
from collections import Counter
from datetime import datetime, timezone

import pandas as pd
import requests
from dotenv import load_dotenv
from supabase import Client, create_client

load_dotenv()

# One key, or a comma-separated list — the crawler rotates on daily-cap.
AV_KEYS = [k.strip() for k in os.getenv("ALPHAVANTAGE_API_KEY", "demo").split(",") if k.strip()] or ["demo"]
# Supabase new-style keys (sb_publishable_… / sb_secret_…). Writes need the
# SECRET key — the publishable key is blocked by RLS from inserting.
SUPABASE_URL = os.getenv("FINANCE_SUPABASE_URL")
SUPABASE_KEY = os.getenv("FINANCE_SECRET_KEY")
if not SUPABASE_URL or not SUPABASE_KEY:
    raise SystemExit(
        "Missing Supabase creds. Set FINANCE_SUPABASE_URL and the SECRET key "
        "FINANCE_SECRET_KEY (sb_secret_…) in .env."
    )
EPS_LIMIT = int(os.getenv("EPS_LIMIT", "25"))   # NEW (unseen) tickers per run
EPS_OFFSET = int(os.getenv("EPS_OFFSET", "0"))  # skip first N pending — lets
# parallel GitHub Actions shards each take a distinct 25-ticker slice.
EPS_SLEEP = float(os.getenv("EPS_SLEEP", "13"))  # ≥12s keeps under AV's 5/min
EPS_CSV = os.getenv("EPS_CSV", "global500.csv")
# Explicit tickers to (re)fetch, comma-separated — bypasses the CSV AND the
# resume-skip, so you can test/refresh a single symbol: EPS_TICKERS=META
EPS_TICKERS = os.getenv("EPS_TICKERS", "").strip()
EPS_SKIP_FILE = os.getenv(
    "EPS_SKIP_FILE", os.path.join(os.path.dirname(__file__), ".eps_empty.txt")
)

AV_URL = "https://www.alphavantage.co/query"

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


class RateLimited(Exception):
    pass


def num(v):
    """AV returns strings and 'None' for missing values — parse to float|None."""
    if v is None:
        return None
    s = str(v).strip()
    if s.lower() in ("none", "null", ""):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def fetch_av_earnings(ticker: str, api_key: str) -> dict:
    """{'annualEarnings': [...], 'quarterlyEarnings': [...]} from Alpha Vantage.
    Raises RateLimited when the key is throttled."""
    resp = requests.get(
        AV_URL,
        params={
            "function": "EARNINGS",
            "symbol": ticker.upper(),
            "apikey": api_key,
        },
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    if "Information" in data or "Note" in data:
        raise RateLimited(data.get("Information") or data.get("Note"))
    return data


def clean_date(v):
    """AV date fields are 'YYYY-MM-DD' strings, or 'None'/'' when missing."""
    if v is None:
        return None
    s = str(v).strip()
    return s if s and s.lower() not in ("none", "null") else None


def clean_text(v):
    if v is None:
        return None
    s = str(v).strip()
    return s if s and s.lower() not in ("none", "null") else None


def build_rows(ticker: str, data: dict) -> list:
    """Store the Alpha Vantage EARNINGS record VERBATIM — AV's own field names.

    AV annualEarnings item:     {fiscalDateEnding, reportedEPS}
    AV quarterlyEarnings item:  {fiscalDateEnding, reportedDate, reportedEPS,
                                 estimatedEPS, surprise, surprisePercentage,
                                 reportTime}

    We keep those exact names as the column names. `period_type` (annual /
    quarterly) marks which AV array each row came from — the only added field,
    since AV returns the two arrays separately and a ticker can share the same
    fiscalDateEnding across both (e.g. IBM 2026-06-30 appears in each)."""
    now = datetime.now(timezone.utc).isoformat()
    rows = []

    # AV's annualEarnings mixes a PARTIAL mid-year stub (a recent quarter-end
    # carrying year-to-date EPS, e.g. META 2026-06-30=13.49) in with the real
    # fiscal years (2025-12-31=29.70, …). Real years share one fiscal month, so
    # keep only entries in the dominant month and drop the stub.
    annual = data.get("annualEarnings") or []
    annual_months = [
        clean_date(e.get("fiscalDateEnding"))[5:7]
        for e in annual
        if clean_date(e.get("fiscalDateEnding")) and num(e.get("reportedEPS")) is not None
    ]
    fiscal_month = Counter(annual_months).most_common(1)[0][0] if annual_months else None

    for e in annual:
        fiscalDateEnding = clean_date(e.get("fiscalDateEnding"))
        reportedEPS = num(e.get("reportedEPS"))
        if not fiscalDateEnding or reportedEPS is None:
            continue
        if fiscalDateEnding[5:7] != fiscal_month:
            continue                      # AV partial mid-year stub — skip
        rows.append({
            "ticker": ticker,
            "period_type": "annual",
            "fiscalDateEnding": fiscalDateEnding,
            "reportedEPS": reportedEPS,
            "reportedDate": None,          # AV gives these only for quarters
            "estimatedEPS": None,
            "surprise": None,
            "surprisePercentage": None,
            "reportTime": None,
            "source": "alphavantage",
            "updated_at": now,
        })

    for e in data.get("quarterlyEarnings") or []:
        fiscalDateEnding = clean_date(e.get("fiscalDateEnding"))
        reportedEPS = num(e.get("reportedEPS"))
        if not fiscalDateEnding or reportedEPS is None:  # skip not-yet-reported
            continue
        rows.append({
            "ticker": ticker,
            "period_type": "quarterly",
            "fiscalDateEnding": fiscalDateEnding,
            "reportedEPS": reportedEPS,
            "reportedDate": clean_date(e.get("reportedDate")),
            "estimatedEPS": num(e.get("estimatedEPS")),
            "surprise": num(e.get("surprise")),
            "surprisePercentage": num(e.get("surprisePercentage")),
            "reportTime": clean_text(e.get("reportTime")),
            "source": "alphavantage",
            "updated_at": now,
        })
    return rows


def fetch_done_tickers() -> set:
    """Tickers already seeded in eps_history (via the distinct-ticker view)."""
    res = supabase.table("eps_history_tickers").select("ticker").execute()
    return {r["ticker"] for r in (res.data or [])}


def load_skip_empty() -> set:
    """Symbols we've already seen return no EPS data — don't waste calls on them."""
    try:
        with open(EPS_SKIP_FILE) as f:
            return {ln.strip() for ln in f if ln.strip()}
    except FileNotFoundError:
        return set()


def mark_empty(ticker: str) -> None:
    with open(EPS_SKIP_FILE, "a") as f:
        f.write(ticker + "\n")


def main():
    if EPS_TICKERS:
        # Explicit test/refresh mode — fetch exactly these, ignore resume-skip.
        names = [t.strip().upper() for t in EPS_TICKERS.split(",") if t.strip()]
        batch = pending = pd.DataFrame({"Ticker": names, "Name": names})
        print(f"Explicit tickers (bypassing resume-skip): {', '.join(names)}\n")
    else:
        df = pd.read_csv(EPS_CSV).rename(columns={"Symbol": "Ticker"})[["Ticker", "Name"]]
        done = fetch_done_tickers()
        skip_empty = load_skip_empty()
        pending = df[~df["Ticker"].isin(done | skip_empty)].reset_index(drop=True)
        batch = pending.iloc[EPS_OFFSET:EPS_OFFSET + EPS_LIMIT]

        print(
            f"Universe {len(df)} · already seeded {len(done)} · known-empty "
            f"{len(skip_empty)} · pending {len(pending)} · offset {EPS_OFFSET}"
        )
        if batch.empty:
            print("✅ Nothing to crawl at this offset — everything here is seeded.")
            return
        print(
            f"Processing {len(batch)} this run (pending[{EPS_OFFSET}:{EPS_OFFSET + len(batch)}]) "
            f"with {len(AV_KEYS)} key(s), sleep {EPS_SLEEP}s\n"
        )

    ok = empty = failed = 0
    key_idx = 0
    rows_iter = list(batch.itertuples(index=False))
    i = 0
    while i < len(rows_iter):
        ticker, name = rows_iter[i].Ticker, rows_iter[i].Name
        key = AV_KEYS[key_idx]
        print(f"[{i + 1}/{len(rows_iter)}] {ticker} ({name})  key ...{key[-4:]}")
        try:
            data = fetch_av_earnings(ticker, key)
        except RateLimited as e:
            print(f"  ⛔ key ...{key[-4:]} rate-limited: {e}")
            key_idx += 1
            if key_idx >= len(AV_KEYS):
                print("  All keys exhausted for today — stopping. Re-run with "
                      "fresh keys to continue where this left off.")
                break
            print(f"  ↻ rotating to key ...{AV_KEYS[key_idx][-4:]}, retrying {ticker}")
            continue  # retry SAME ticker with the next key (don't advance i)
        except Exception as e:
            print(f"  ❌ fetch failed: {e}")
            failed += 1
            i += 1
            time.sleep(EPS_SLEEP)
            continue

        rows = build_rows(ticker, data)
        if not rows:
            print("  ℹ️ no EPS data (try the primary listing, e.g. GOOGL not GOOG)")
            mark_empty(ticker)  # remember so we never re-fetch it
            empty += 1
        else:
            n_a = sum(1 for r in rows if r["period_type"] == "annual")
            n_q = len(rows) - n_a
            try:
                supabase.table("eps_history").upsert(
                    rows, on_conflict="ticker,period_type,fiscalDateEnding"
                ).execute()
                print(f"  ✅ {n_a} annual · {n_q} quarterly")
                ok += 1
            except Exception as e:
                print(f"  ❌ upsert failed: {e}")
                failed += 1

        i += 1
        if i < len(rows_iter):
            time.sleep(EPS_SLEEP)

    remaining = len(pending) - ok - empty
    print(f"\n✅ {ok}   ℹ️ {empty} no-eps   ❌ {failed} failed   ·   ~{remaining} still pending")


if __name__ == "__main__":
    main()
