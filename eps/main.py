"""
EPS history crawler — SEC EDGAR (XBRL) edition.

Pulls deep Basic EPS history (annual + quarterly) from the SEC's XBRL
`companyconcept` API for each ticker in global500.csv and upserts into the
`eps_history` table.

Why SEC EDGAR: free, no API key, no daily cap, official filer data going back
~15+ years (XBRL mandate, 2009+). US SEC filers only — a ticker not in SEC's
ticker→CIK map is skipped instantly with NO network call, so a global universe
naturally reduces to its US names.

Concept: us-gaap:EarningsPerShareBasic (falls back to
EarningsPerShareBasicAndDiluted). Period type is inferred from the XBRL
duration: ~365 days = annual, ~90 days = quarterly; 6-/9-month YTD figures are
skipped. (Note: SEC 10-Qs file Q1–Q3 only, so standalone Q4 quarters are not
available from this source.)

RESUME-SKIP: each run skips tickers already in eps_history (via the
eps_history_tickers view) plus known-skip symbols (local .eps_empty.txt — this
also remembers non-US tickers so they're never re-checked).

SHARDING: EPS_SHARD / EPS_SHARDS split the universe into disjoint strides for
parallel jobs (shard 0 = rows 0,4,8…). No overlap, ever.

Env (.env locally / GitHub Actions secrets):
  FINANCE_SUPABASE_URL   Supabase project URL
  FINANCE_SUPABASE_SECRET_KEY     Supabase SECRET key (sb_secret_…) — needed for writes
  EPS_LIMIT              tickers to process this run (default 500)
  EPS_SLEEP              seconds between SEC calls (default 0.5 → under 10/s)
  EPS_CSV               universe csv (default global500.csv)
  EPS_SHARD/EPS_SHARDS   stride shard index / count (default 0 / 1)
  EPS_TICKERS            explicit tickers to (re)fetch — bypasses CSV + resume
  EPS_UA                 User-Agent for SEC (SEC requires a contact address)
  EPS_SKIP_FILE          local file of skip symbols (default .eps_empty.txt)

  pip install -r requirements.txt   # requests, pandas, supabase, python-dotenv
  python main.py                    # run from the stoxx/ root
"""
import os
import time
from datetime import datetime, timezone

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
EPS_LIMIT = int(os.getenv("EPS_LIMIT", "500"))
EPS_YEARS = int(os.getenv("EPS_YEARS", "10"))   # keep only the last N years (0 = all)
EPS_SLEEP = float(os.getenv("EPS_SLEEP", "0.5"))
EPS_CSV = os.getenv("EPS_CSV", "global500.csv")
EPS_SHARD = int(os.getenv("EPS_SHARD", "0"))
EPS_SHARDS = int(os.getenv("EPS_SHARDS", "1"))
EPS_TICKERS = os.getenv("EPS_TICKERS", "").strip()
EPS_SKIP_FILE = os.getenv(
    "EPS_SKIP_FILE", os.path.join(os.path.dirname(__file__), ".eps_empty.txt")
)
# SEC requires a descriptive User-Agent with a contact address.
HEADERS = {"User-Agent": os.getenv("EPS_UA", "oxinion-finance eps-crawler (idevbrandon@gmail.com)")}

SEC_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
SEC_CONCEPT_URL = "https://data.sec.gov/api/xbrl/companyconcept/CIK{cik:010d}/us-gaap/{concept}.json"
CONCEPTS = ["EarningsPerShareBasic", "EarningsPerShareBasicAndDiluted"]

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


def fetch_cik_map() -> dict:
    """SEC ticker → CIK map (US filers only). Keys are uppercased tickers."""
    r = requests.get(SEC_TICKERS_URL, headers=HEADERS, timeout=30)
    r.raise_for_status()
    return {row["ticker"].upper(): int(row["cik_str"]) for row in r.json().values()}


def lookup_cik(cik_map: dict, ticker: str):
    """Match a CSV ticker to SEC's CIK, tolerating . vs - share-class suffixes."""
    if not isinstance(ticker, str):
        return None
    up = ticker.upper()
    for cand in (up, up.replace(".", "-"), up.replace("-", ".")):
        if cand in cik_map:
            return cik_map[cand]
    return None


def _fetch_concept(cik: int, concept: str):
    r = requests.get(SEC_CONCEPT_URL.format(cik=cik, concept=concept), headers=HEADERS, timeout=30)
    if r.status_code == 404:
        return None
    r.raise_for_status()
    return r.json()


def fetch_splits(ticker: str) -> dict:
    """{split_date(Timestamp): ratio} from yfinance, or {} if none/unavailable.
    Splits are rare, so most tickers return {} and need no adjustment."""
    try:
        import yfinance as yf
        s = yf.Ticker(ticker).splits
        if s is None or getattr(s, "empty", True):
            return {}
        s = s[s > 0]
        return {pd.Timestamp(d).tz_localize(None): float(r) for d, r in s.items()}
    except Exception:
        return {}


def adjust_eps(raw: float, filed: str, splits: dict) -> float:
    """Restate an EPS value to today's share basis: divide by every split that
    happened AFTER the filing that reported it (splits before are already in)."""
    if not splits or not filed:
        return raw
    filed_ts = pd.Timestamp(filed)
    factor = 1.0
    for split_date, ratio in splits.items():
        if split_date > filed_ts:
            factor *= ratio
    return round(raw / factor, 4) if factor else raw


def build_rows(ticker: str, cik: int) -> list:
    """Deep Basic EPS (annual + quarterly) from SEC XBRL for one filer."""
    now = datetime.now(timezone.utc).isoformat()
    data = None
    for concept in CONCEPTS:
        data = _fetch_concept(cik, concept)
        if data and data.get("units"):
            break
    if not data or not data.get("units"):
        return []

    entries = []
    for vals in data["units"].values():          # usually "USD/shares"
        entries.extend(vals)

    # dedupe by (period_type, period_end), keeping the latest-filed value
    seen = {}
    for e in entries:
        end, start, val = e.get("end"), e.get("start"), e.get("val")
        form, filed = e.get("form", ""), e.get("filed", "")
        if not (end and start) or val is None:
            continue
        if not (form.startswith("10-K") or form.startswith("10-Q")):
            continue
        dur = (datetime.fromisoformat(end) - datetime.fromisoformat(start)).days
        if 330 <= dur <= 400:
            period_type = "annual"
        elif 80 <= dur <= 100:
            period_type = "quarterly"
        else:
            continue                              # skip 6-/9-month YTD figures
        key = (period_type, end)
        if key not in seen or filed >= seen[key]["filed"]:
            seen[key] = {"val": val, "filed": filed, "period_type": period_type, "end": end}

    # keep only the last EPS_YEARS years (string compare on YYYY-MM-DD is fine)
    if EPS_YEARS > 0:
        now_dt = datetime.now(timezone.utc)
        cutoff = f"{now_dt.year - EPS_YEARS:04d}-{now_dt.month:02d}-{now_dt.day:02d}"
        seen = {k: v for k, v in seen.items() if v["end"] >= cutoff}

    if not seen:
        return []

    splits = fetch_splits(ticker)   # {} for the vast majority (no splits)
    return [{
        "ticker": ticker,
        "period_type": v["period_type"],
        "fiscalDateEnding": v["end"],
        "basicEPS": float(v["val"]),                              # as-reported
        "adjustedBasicEPS": adjust_eps(float(v["val"]), v["filed"], splits),
        "source": "sec",
        "updated_at": now,
    } for v in seen.values()]


def build_rows_yf(ticker: str) -> list:
    """Fallback: Basic EPS (annual + quarterly) from yfinance income statements.
    Shallow (~4 annual, ~5 quarterly) but covers non-US names SEC doesn't have.
    yfinance EPS is already in current share terms, so adjusted == raw."""
    now = datetime.now(timezone.utc).isoformat()
    import yfinance as yf
    t = yf.Ticker(ticker)
    cutoff = None
    if EPS_YEARS > 0:
        y = datetime.now(timezone.utc)
        cutoff = f"{y.year - EPS_YEARS:04d}-{y.month:02d}-{y.day:02d}"

    rows = []
    for period_type, stmt in (("annual", t.income_stmt), ("quarterly", t.quarterly_income_stmt)):
        if stmt is None or getattr(stmt, "empty", True):
            continue
        eps_row = None
        for row_name in stmt.index:
            if "basic eps" in str(row_name).lower():
                eps_row = stmt.loc[row_name]
                break
        if eps_row is None:
            continue
        for period_end, value in eps_row.items():
            if value is None or pd.isna(value):
                continue
            fde = pd.Timestamp(period_end).date().isoformat()
            if cutoff and fde < cutoff:
                continue
            v = float(value)
            rows.append({
                "ticker": ticker,
                "period_type": period_type,
                "fiscalDateEnding": fde,
                "basicEPS": v,
                "adjustedBasicEPS": v,   # yfinance already current-share terms
                "source": "yfinance",
                "updated_at": now,
            })
    return rows


def fetch_done_tickers() -> set:
    res = supabase.table("eps_history_tickers").select("ticker").execute()
    return {r["ticker"] for r in (res.data or [])}


def load_skip_empty() -> set:
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
        names = [t.strip().upper() for t in EPS_TICKERS.split(",") if t.strip()]
        batch = pending = pd.DataFrame({"Ticker": names, "Name": names})
        print(f"Explicit tickers (bypassing resume-skip): {', '.join(names)}\n")
    else:
        # keep_default_na=False stops pandas from coercing real ticker strings
        # like "NA" (Nano Labs), "NULL" or "None" into a float NaN, which later
        # crashes ticker.upper(). dtype=str keeps numeric-looking tickers as text.
        df = pd.read_csv(
            EPS_CSV, dtype={"Symbol": str}, keep_default_na=False
        ).rename(columns={"Symbol": "Ticker"})[["Ticker", "Name"]]
        df["Ticker"] = df["Ticker"].str.strip()
        df = df[df["Ticker"] != ""]          # drop genuinely-empty ticker cells
        if EPS_SHARDS > 1:                       # disjoint stride for this shard
            df = df.iloc[EPS_SHARD::EPS_SHARDS]
        done = fetch_done_tickers()
        skip_empty = load_skip_empty()
        pending = df[~df["Ticker"].isin(done | skip_empty)].reset_index(drop=True)
        batch = pending.head(EPS_LIMIT)

        print(
            f"Shard {EPS_SHARD}/{EPS_SHARDS} · this shard's rows {len(df)} · "
            f"already seeded {len(done)} · pending here {len(pending)}"
        )
        if batch.empty:
            print("✅ Nothing left for this shard — its partition is fully seeded.")
            return
        print(f"Processing {len(batch)} tickers via SEC EDGAR, sleep {EPS_SLEEP}s\n")

    cik_map = fetch_cik_map()
    print(f"SEC ticker→CIK map: {len(cik_map)} US filers\n")

    ok = empty = failed = 0
    sec_n = yf_n = 0
    rows_iter = list(batch.itertuples(index=False))
    for i, r in enumerate(rows_iter):
        ticker, name = r.Ticker, r.Name
        if not isinstance(ticker, str) or not ticker.strip():
            print(f"[{i + 1}/{len(rows_iter)}] ⚠️  skipping blank/invalid ticker (name={name!r})")
            continue
        ticker = ticker.strip()
        cik = lookup_cik(cik_map, ticker)
        tag = f"CIK {cik}" if cik is not None else "non-US → yfinance"
        print(f"[{i + 1}/{len(rows_iter)}] {ticker} ({name})  {tag}")

        rows, src = [], None
        try:
            if cik is not None:                  # US filer → SEC (deep)
                rows = build_rows(ticker, cik)
                src = "sec"
            if not rows:                         # non-US, or SEC had nothing → yfinance
                rows = build_rows_yf(ticker)
                src = "yfinance"
        except Exception as e:
            print(f"  ❌ fetch failed: {e}")
            failed += 1
            time.sleep(EPS_SLEEP)
            continue

        if not rows:
            print("  ℹ️ no Basic EPS (SEC or yfinance)")
            mark_empty(ticker)
            empty += 1
        else:
            n_a = sum(1 for x in rows if x["period_type"] == "annual")
            n_q = len(rows) - n_a
            try:
                supabase.table("eps_history").upsert(
                    rows, on_conflict="ticker,period_type,fiscalDateEnding"
                ).execute()
                print(f"  ✅ {n_a} annual · {n_q} quarterly [{src}]")
                ok += 1
                if src == "sec":
                    sec_n += 1
                else:
                    yf_n += 1
            except Exception as e:
                print(f"  ❌ upsert failed: {e}")
                failed += 1

        time.sleep(EPS_SLEEP)

    print(f"\n✅ {ok} ({sec_n} sec · {yf_n} yfinance)   ℹ️ {empty} no-eps   ❌ {failed} failed")


if __name__ == "__main__":
    main()
