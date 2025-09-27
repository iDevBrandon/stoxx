import os
import pandas as pd
import yfinance as yf
from supabase import create_client, Client
from dotenv import load_dotenv
from datetime import datetime
import time

# 환경변수 로드
load_dotenv()

# Supabase 설정
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# CSV 파일 경로
csv_file = "dividends/companies.csv"
df = pd.read_csv(csv_file).head(500)  # 테스트용 상위 500개

# 컬럼명 정리
df = df.rename(columns={"country": "Country", "Symbol": "Ticker", "Name": "Name"})
df = df[["Ticker", "Name", "Country"]]

def fetch_dividend_data(ticker):
    """배당 데이터 가져오기 및 연도별 합계 계산"""
    try:
        # Rate limiting
        time.sleep(0.1)
        
        stock = yf.Ticker(ticker)
        dividends = stock.dividends
        
        if dividends.empty:
            return {}
        
        yearly_dividends = dividends.groupby(dividends.index.year).sum()
        return yearly_dividends.to_dict()
        
    except Exception as e:
        print(f"  Error fetching dividends for {ticker}: {e}")
        return {}

def calculate_dividend_cagr(dividends_dict, years_back):
    """배당 CAGR 계산 (올해-1 기준)"""
    current_year = datetime.now().year
    end_year = current_year - 1  # 작년
    start_year = end_year - years_back + 1
    
    if start_year not in dividends_dict or end_year not in dividends_dict:
        return None
    
    starting_dividend = dividends_dict[start_year]
    ending_dividend = dividends_dict[end_year]
    
    if starting_dividend <= 0:
        return None
    
    cagr = (ending_dividend / starting_dividend) ** (1/(years_back-1)) - 1
    return round(cagr, 4)

def calculate_consecutive_growth(dividends_dict):
    """연속 배당 성장 연수 계산 (최신년도부터 역순 확인)"""
    current_year = datetime.now().year - 1  # 작년부터 시작
    streak = 0
    year = current_year
    
    while year in dividends_dict:
        if year - 1 in dividends_dict and dividends_dict[year] > dividends_dict[year - 1]:
            streak += 1
        else:
            break
        year -= 1
    
    return streak

# 이미 처리된 ticker들 확인
try:
    existing_records = supabase.table("dividend_analysis").select("ticker").execute()
    existing_tickers = {record["ticker"] for record in existing_records.data}
    print(f"Found {len(existing_tickers)} existing records in database")
except Exception as e:
    print(f"Could not fetch existing records: {e}")
    existing_tickers = set()

# 메인 처리
successful_updates = 0
failed_updates = 0
skipped_updates = 0

for index, row in df.iterrows():
    ticker = row['Ticker']
    name = row['Name']
    country = row['Country']
    
    print(f"\n[{index+1}/{len(df)}] Processing: {ticker} ({name})")
    
    # Skip if already processed
    if ticker in existing_tickers:
        print(f"  ⏭️ Skipping {ticker} (already exists)")
        skipped_updates += 1
        continue
    
    dividends_data = fetch_dividend_data(ticker)
    
    if not dividends_data:
        print(f"  ℹ️ No dividend data for {ticker}")
        # 배당 데이터 없는 경우도 DB에 기록
        record = {
            "ticker": ticker,
            "name": name,
            "country": country,
            "dividend_cagr_3yr": None,
            "dividend_cagr_5yr": None,
            "consecutive_growth_years": 0,
            "total_dividends_history": {},
            "updated_at": datetime.now().isoformat()
        }
        try:
            supabase.table("dividend_analysis").upsert(record, on_conflict="ticker").execute()
            successful_updates += 1
        except Exception as e:
            print(f"  ❌ Failed to update {ticker}: {e}")
            failed_updates += 1
        continue
    
    # 배당 데이터가 있으면 계산
    cagr_3yr = calculate_dividend_cagr(dividends_data, 3)
    cagr_5yr = calculate_dividend_cagr(dividends_data, 5)
    consecutive_growth = calculate_consecutive_growth(dividends_data)
    
    record = {
        "ticker": ticker,
        "name": name,
        "country": country,
        "dividend_cagr_3yr": cagr_3yr,
        "dividend_cagr_5yr": cagr_5yr,
        "consecutive_growth_years": consecutive_growth,
        "total_dividends_history": dividends_data,
        "updated_at": datetime.now().isoformat()
    }
    
    try:
        supabase.table("dividend_analysis").upsert(record, on_conflict="ticker").execute()
        successful_updates += 1
    except Exception as e:
        print(f"  ❌ Failed to update {ticker}: {e}")
        failed_updates += 1

print(f"\n✅ Successful updates: {successful_updates}")
print(f"❌ Failed updates: {failed_updates}")
print(f"⏭️ Skipped updates: {skipped_updates}")
print(f"📊 Total processed: {successful_updates + failed_updates + skipped_updates}/{len(df)}")
