import os
import pandas as pd
import yfinance as yf
from supabase import create_client, Client
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

# Supabase 환경변수
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# CSV 파일 경로
csv_file = "/Users/brandonha/Documents/GitHub/stoxx/dividends/companies.csv"

# CSV 읽기
df = pd.read_csv(csv_file)

# Top 500만 선택
df = df.head(500)

# 컬럼명 정리
df = df.rename(columns={"country": "Country", "Symbol": "Ticker", "Name": "Name"})
df = df[["Ticker", "Name", "Country"]]

def fetch_dividends(ticker):
    try:
        stock = yf.Ticker(ticker)
        dividends = stock.dividends
        if dividends.empty:
            return {}
        # 연도별 합계
        yearly = dividends.groupby(dividends.index.year).sum().to_dict()
        # 올해 제외
        current_year = datetime.now().year
        if current_year in yearly:
            yearly.pop(current_year)
        return yearly
    except Exception as e:
        print(f"No dividends for {ticker}: {e}")
        return {}

def calculate_cagr(dividends, years):
    if len(dividends) < years:
        return None
    sorted_years = sorted(dividends.keys(), reverse=True)
    recent_years = sorted_years[:years]
    start = dividends[recent_years[-1]]
    end = dividends[recent_years[0]]
    if start == 0:
        return None
    return round((end / start) ** (1/years) - 1, 3)

def consecutive_growth(dividends, years=7):
    if len(dividends) < years:
        return False
    sorted_years = sorted(dividends.keys(), reverse=True)[:years]
    for i in range(len(sorted_years)-1):
        if dividends[sorted_years[i]] <= dividends[sorted_years[i+1]]:
            return False
    return True

for _, row in df.iterrows():
    ticker = row['Ticker']
    name = row['Name']
    country = row['Country']
    total_dividends_per_year = fetch_dividends(ticker)
    cagr_3yr = calculate_cagr(total_dividends_per_year, 3)
    cagr_5yr = calculate_cagr(total_dividends_per_year, 5)
    consecutive_growth_7yr = consecutive_growth(total_dividends_per_year, 7)

    record = {
        "ticker": ticker,
        "name": name,
        "country": country,
        "total_dividends_per_year": total_dividends_per_year,
        "cagr_3yr": cagr_3yr,
        "cagr_5yr": cagr_5yr,
        "consecutive_growth_7yr": consecutive_growth_7yr
    }

    # Supabase에 Upsert
    try:
        res = supabase.table("equities").upsert(record, on_conflict="ticker").execute()
        print(f"Inserted/Updated equity: {ticker} -> {record}")
    except Exception as e:
        print(f"Failed {ticker}: {e}")
