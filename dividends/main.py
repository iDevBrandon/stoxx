import os
import pandas as pd
import yfinance as yf
from supabase import create_client, Client
from dotenv import load_dotenv
from datetime import datetime

# 환경변수 로드
load_dotenv()

# Supabase 설정
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# CSV 파일 경로
# csv_file = "/Users/brandonha/Documents/GitHub/stoxx/dividends/companies.csv"
csv_file = "dividends/companies.csv"

# CSV 읽기
df = pd.read_csv(csv_file)
# Top 500만 선택
df = df.head(10)

# 컬럼명 정리
df = df.rename(columns={"country": "Country", "Symbol": "Ticker", "Name": "Name"})
df = df[["Ticker", "Name", "Country"]]

def fetch_dividend_data(ticker):
    """
    배당 데이터 가져오기 및 연도별 합계 계산
    """
    try:
        stock = yf.Ticker(ticker)
        dividends = stock.dividends
        
        if dividends.empty:
            return {}
        
        # 연도별 합계 계산
        yearly_dividends = dividends.groupby(dividends.index.year).sum()
        
        # 현재 연도 제외 (아직 완료되지 않은 연도)
        current_year = datetime.now().year
        yearly_dividends = yearly_dividends[yearly_dividends.index < current_year]
        
        return yearly_dividends.to_dict()
        
    except Exception as e:
        print(f"Error fetching dividends for {ticker}: {e}")
        return {}

def calculate_dividend_cagr(dividends_dict, years):
    """
    배당 CAGR 계산 (최근 N년)
    Returns: float (소수점 형태, 예: 0.096 = 9.6%)
    """
    if len(dividends_dict) < years:
        return None
    
    # 연도별로 정렬 (최신순)
    sorted_years = sorted(dividends_dict.keys(), reverse=True)
    
    if len(sorted_years) < years:
        return None
    
    # 최근 N년 데이터 선택
    end_year = sorted_years[0]  # 가장 최근 연도
    start_year = sorted_years[years-1]  # N년 전 연도
    
    start_dividend = dividends_dict[start_year]
    end_dividend = dividends_dict[end_year]
    
    if start_dividend <= 0:
        return None
    
    # CAGR 계산: (End/Start)^(1/years) - 1
    cagr = (end_dividend / start_dividend) ** (1/years) - 1
    
    return round(cagr, 4)  # 소수점 4자리까지



# 메인 처리 로직
print(f"Processing {len(df)} companies...")

for index, row in df.iterrows():
    ticker = row['Ticker']
    name = row['Name']
    country = row['Country']
    
    print(f"Processing {index+1}/{len(df)}: {ticker}")
    
    # 배당 데이터 가져오기
    dividends_data = fetch_dividend_data(ticker)
    
    # 배당 성장률 계산
    cagr_3yr = calculate_dividend_cagr(dividends_data, 3)
    cagr_5yr = calculate_dividend_cagr(dividends_data, 5)
    cagr_10yr = calculate_dividend_cagr(dividends_data, 10)
    
    # 데이터 레코드 구성
    record = {
        "ticker": ticker,
        "name": name,
        "country": country,
        "dividend_cagr_3yr": cagr_3yr,
        "dividend_cagr_5yr": cagr_5yr, 
        "dividend_cagr_10yr": cagr_10yr,
        "total_dividends_history": dividends_data,
        "updated_at": datetime.now().isoformat()
    }
    
    # Supabase에 업데이트
    try:
        result = supabase.table("dividend_analysis").upsert(
            record, 
            on_conflict="ticker"
        ).execute()
        
        print(f"✅ {ticker}: 5yr CAGR = {cagr_5yr*100:.1f}%" if cagr_5yr else f"✅ {ticker}: No sufficient data for 5yr CAGR")
        
    except Exception as e:
        print(f"❌ Failed to update {ticker}: {e}")

print("✅ All companies processed!")

# 요약 통계
print("\n📊 Summary:")
try:
    stats = supabase.table("dividend_analysis").select("*").execute()
    total_count = len(stats.data)
    
    print(f"Total companies: {total_count}")
    
except Exception as e:
    print(f"Could not generate summary: {e}")