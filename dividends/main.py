"""
Dividend history crawler — Alpha Vantage edition.

Alpha Vantage's DIVIDENDS endpoint uniquely returns the full payment calendar
(ex-date, declaration, record, and PAYMENT date) that yfinance lacks. For each
company this script:
  * upserts every payment into the granular `dividend_history` table
  * recomputes a per-ticker summary (yearly totals, CAGR, growth streak) into
    the `dividends` table

Env (.env locally / GitHub Actions secrets):
  ALPHAVANTAGE_API_KEY   Alpha Vantage key (required — "demo" only works for a
                         couple of symbols)
  FINANCE_SUPABASE_URL   Supabase project URL
  FINANCE_SECRET_KEY     Supabase SECRET key (sb_secret_…) — needed for writes
  DIV_LIMIT              max tickers this run (default 500 = top-500 universe)
  DIV_SLEEP              seconds between API calls (default 1.0)

  pip install -r requirements.txt
  python main.py
"""
import os
import time
from datetime import datetime, timezone

import pandas as pd
import requests
from dotenv import load_dotenv
from supabase import Client, create_client

load_dotenv()

ALPHAVANTAGE_API_KEY = os.getenv("ALPHAVANTAGE_API_KEY", "demo")
# Supabase new-style keys (sb_publishable_… / sb_secret_…). Writes need the
# SECRET key — the publishable key is blocked by RLS from inserting.
SUPABASE_URL = os.getenv("FINANCE_SUPABASE_URL")
SUPABASE_KEY = os.getenv("FINANCE_SECRET_KEY")
if not SUPABASE_URL or not SUPABASE_KEY:
    raise SystemExit(
        "Missing Supabase creds. Set FINANCE_SUPABASE_URL and the SECRET key "
        "FINANCE_SECRET_KEY (sb_secret_…) in .env."
    )
DIV_LIMIT = int(os.getenv("DIV_LIMIT", "500"))  # top-500 universe
DIV_SLEEP = float(os.getenv("DIV_SLEEP", "1.0"))

AV_URL = "https://www.alphavantage.co/query"
CSV_FILE = os.getenv("DIV_CSV", "global500.csv")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


class RateLimited(Exception):
    pass


def clean_date(v):
    """AV uses 'None'/'' for missing dates — normalise to a real None."""
    if v is None:
        return None
    s = str(v).strip()
    return None if s.lower() in ("none", "null", "") else s


def fetch_av_dividends(ticker: str) -> list:
    """Dividend rows from Alpha Vantage (newest first), or [] if none.
    Raises RateLimited when the key is throttled."""
    resp = requests.get(
        AV_URL,
        params={
            "function": "DIVIDENDS",
            "symbol": ticker,
            "apikey": ALPHAVANTAGE_API_KEY,
        },
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    # AV returns these keys instead of `data` when something's wrong.
    if "Information" in data or "Note" in data:
        raise RateLimited(data.get("Information") or data.get("Note"))
    if "Error Message" in data:
        return []
    return data.get("data") or []


def infer_frequency(ex_dates) -> str:
    dts = sorted(pd.to_datetime([d for d in ex_dates if clean_date(d)]).tolist())
    if len(dts) < 2:
        return "annual"
    median_gap = float(pd.Series(dts).diff().dropna().dt.days.median())
    if median_gap <= 45:
        return "monthly"
    if median_gap <= 135:
        return "quarterly"
    if median_gap <= 270:
        return "semiannual"
    return "annual"


def build_rows(ticker: str, av_rows: list, freq: str) -> list:
    amounts = [
        float(x["amount"])
        for x in av_rows
        if x.get("amount") not in (None, "", "None")
    ]
    median_amt = pd.Series(amounts).median() if amounts else 0.0

    rows = []
    now = datetime.now(timezone.utc).isoformat()
    for x in av_rows:
        amt = x.get("amount")
        ex = clean_date(x.get("ex_dividend_date"))
        if amt in (None, "", "None") or not ex:
            continue
        amt = float(amt)
        is_special = median_amt > 0 and amt > 2.5 * median_amt
        rows.append({
            "ticker": ticker,
            "ex_date": ex,
            "amount": amt,
            "pay_date": clean_date(x.get("payment_date")),
            "record_date": clean_date(x.get("record_date")),
            "declaration_date": clean_date(x.get("declaration_date")),
            "frequency": "special" if is_special else freq,
            "is_special": bool(is_special),
            "currency": "USD",
            "source": "alphavantage",
            "updated_at": now,
        })
    return rows


def summarize(ticker, name, country, rows) -> dict:
    """Yearly totals + CAGR + growth streak for the `dividends` summary table."""
    cagr3 = cagr5 = None
    streak = 0
    history = {}
    if rows:
        df = pd.DataFrame(rows)
        df["year"] = pd.to_datetime(df["ex_date"]).dt.year
        yearly = df.groupby("year")["amount"].sum()
        history = {str(int(y)): round(float(v), 4) for y, v in yearly.items()}
        complete = yearly[yearly.index < datetime.now().year]  # skip partial year

        def cagr(years):
            if len(complete) <= years or complete.iloc[-1 - years] <= 0:
                return None
            start, end = complete.iloc[-1 - years], complete.iloc[-1]
            return round((end / start) ** (1 / years) - 1, 4)

        cagr3, cagr5 = cagr(3), cagr(5)
        for i in range(len(complete) - 1, 0, -1):
            if complete.iloc[i] > complete.iloc[i - 1]:
                streak += 1
            else:
                break

    return {
        "ticker": ticker,
        "name": name,
        "country": country,
        "dividend_cagr_3yr": cagr3,
        "dividend_cagr_5yr": cagr5,
        "consecutive_growth_years": streak,
        "total_dividends_history": history,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


def main():
    df = pd.read_csv(CSV_FILE).rename(columns={"Symbol": "Ticker"})
    universe = df[["Ticker", "Name", "country"]].head(DIV_LIMIT)
    key_tail = ALPHAVANTAGE_API_KEY[-4:] if ALPHAVANTAGE_API_KEY else "----"
    print(
        f"Crawling dividends for {len(universe)} tickers via Alpha Vantage "
        f"(sleep {DIV_SLEEP}s, key ...{key_tail})\n"
    )

    ok = empty = failed = 0
    for i, row in universe.iterrows():
        ticker, name, country = row["Ticker"], row["Name"], row.get("country")
        print(f"[{i + 1}/{len(universe)}] {ticker} ({name})")
        try:
            av = fetch_av_dividends(ticker)
        except RateLimited as e:
            print(f"  ⛔ Alpha Vantage rate limit: {e}")
            print("  Stopping — resume later, or raise DIV_LIMIT with a premium key.")
            break
        except Exception as e:
            print(f"  ❌ fetch failed: {e}")
            failed += 1
            time.sleep(DIV_SLEEP)
            continue

        if not av:
            print("  ℹ️ no dividends")
            empty += 1
            time.sleep(DIV_SLEEP)
            continue

        freq = infer_frequency([r.get("ex_dividend_date") for r in av])
        rows = build_rows(ticker, av, freq)
        try:
            if rows:
                supabase.table("dividend_history").upsert(
                    rows, on_conflict="ticker,ex_date"
                ).execute()
            supabase.table("dividends").upsert(
                summarize(ticker, name, country, rows), on_conflict="ticker"
            ).execute()
            print(f"  ✅ {len(rows)} payments · {freq}")
            ok += 1
        except Exception as e:
            print(f"  ❌ upsert failed: {e}")
            failed += 1

        time.sleep(DIV_SLEEP)

    print(f"\n✅ {ok}   ℹ️ {empty} no-div   ❌ {failed} failed")


if __name__ == "__main__":
    main()
