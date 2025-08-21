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
csv_file = "/Users/seongyeonha/Documents/GitHub/stoxx/dividends/companies.csv"
# csv_file = "dividends/companies.csv"

# CSV 읽기
df = pd.read_csv(csv_file)
# Top 10만 선택 (테스트용)
df = df.head(500)

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
            print(f"  No dividend data for {ticker}")
            return {}
        
        print(f"  Found {len(dividends)} dividend payments for {ticker}")
        
        # 연도별 합계 계산
        yearly_dividends = dividends.groupby(dividends.index.year).sum()
        
        # 딕셔너리로 변환
        result_dict = yearly_dividends.to_dict()
        print(f"  Yearly dividends: {dict(list(result_dict.items())[-5:])}")  # 최근 5년만 출력
        
        return result_dict
        
    except Exception as e:
        print(f"  Error fetching dividends for {ticker}: {e}")
        return {}

def calculate_dividend_cagr(dividends_dict, years_back):
    """
    배당 CAGR 계산
    """
    if len(dividends_dict) < years_back:
        return None
    
    # 현재 연도 자동 가져오기
    current_year = datetime.now().year
    end_year = current_year - 1  # 작년을 마지막 완료된 연도로
    start_year = end_year - years_back + 1  # N년전 시작
    
    # 해당 연도 데이터가 있는지 확인
    if start_year not in dividends_dict or end_year not in dividends_dict:
        return None
    
    starting_dividend = dividends_dict[start_year]
    ending_dividend = dividends_dict[end_year]
    
    # 시작 배당이 0이거나 음수면 계산 불가
    if starting_dividend <= 0:
        return None
    
    # CAGR 공식: (Ending Value / Beginning Value)^(1/n) - 1
    cagr = (ending_dividend / starting_dividend) ** (1/(years_back-1)) - 1
    
    return round(cagr, 4)  # 소수점 4자리까지

# 메인 처리 로직
print(f"Processing {len(df)} companies...")
print("=" * 50)

successful_updates = 0
failed_updates = 0

for index, row in df.iterrows():
    ticker = row['Ticker']
    name = row['Name']
    country = row['Country']
    
    print(f"\n[{index+1}/{len(df)}] Processing: {ticker} ({name})")
    
    # 배당 데이터 가져오기
    dividends_data = fetch_dividend_data(ticker)
    
    if not dividends_data:
        print(f"  ⚠️  No dividend data available")
        failed_updates += 1
        continue
    
    # 배당 성장률 계산
    cagr_3yr = calculate_dividend_cagr(dividends_data, 3)
    cagr_5yr = calculate_dividend_cagr(dividends_data, 5)
    cagr_10yr = calculate_dividend_cagr(dividends_data, 10)
    
    # 최근 배당 정보
    current_year = datetime.now().year
    latest_year = current_year - 1  # 작년
    latest_dividend = dividends_data.get(latest_year, 0)
    
    # 데이터 레코드 구성 (기존 스키마에 맞춤)
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
    
    # 결과 출력
    print(f"  📊 Latest dividend ({latest_year}): ${latest_dividend:.3f}")
    print(f"  📊 Total years of data: {len(dividends_data)}")
    print(f"  📈 CAGR - 3yr: {cagr_3yr*100:.1f}%" if cagr_3yr else "  📈 CAGR - 3yr: N/A")
    print(f"  📈 CAGR - 5yr: {cagr_5yr*100:.1f}%" if cagr_5yr else "  📈 CAGR - 5yr: N/A") 
    print(f"  📈 CAGR - 10yr: {cagr_10yr*100:.1f}%" if cagr_10yr else "  📈 CAGR - 10yr: N/A")
    
    # Supabase에 업데이트
    try:
        result = supabase.table("dividend_analysis").upsert(
            record, 
            on_conflict="ticker"
        ).execute()
        
        print(f"  ✅ Successfully updated {ticker}")
        successful_updates += 1
        
    except Exception as e:
        print(f"  ❌ Failed to update {ticker}: {e}")
        failed_updates += 1

print("\n" + "=" * 50)
print("🎯 PROCESSING COMPLETE!")
print(f"✅ Successful updates: {successful_updates}")
print(f"❌ Failed updates: {failed_updates}")
print(f"📊 Success rate: {successful_updates/(successful_updates+failed_updates)*100:.1f}%")

# 요약 통계
print("\n📊 DATABASE SUMMARY:")
try:
    stats = supabase.table("dividend_analysis").select("*").execute()
    total_count = len(stats.data)
    
    # CAGR 통계
    cagr_5yr_data = [row['dividend_cagr_5yr'] for row in stats.data if row['dividend_cagr_5yr'] is not None]
    
    print(f"Total companies in DB: {total_count}")
    if cagr_5yr_data:
        avg_cagr_5yr = sum(cagr_5yr_data) / len(cagr_5yr_data)
        print(f"Companies with 5yr CAGR: {len(cagr_5yr_data)}")
        print(f"Average 5yr CAGR: {avg_cagr_5yr*100:.1f}%")
        print(f"Max 5yr CAGR: {max(cagr_5yr_data)*100:.1f}%")
        print(f"Min 5yr CAGR: {min(cagr_5yr_data)*100:.1f}%")
    
except Exception as e:
    print(f"Could not generate summary: {e}")