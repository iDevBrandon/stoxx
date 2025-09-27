import pandas as pd
import yfinance as yf
from datetime import datetime


# 함수: 배당 데이터 가져오기 및 연도별 합계
def fetch_yearly_dividends(ticker_symbol):
    ticker = yf.Ticker(ticker_symbol)
    dividends = ticker.dividends
    if dividends.empty:
        return None

    # 연도별 합계
    yearly_dividends = dividends.groupby(dividends.index.year).sum()
    return yearly_dividends


# 함수: 배당 CAGR 계산
def calculate_dividend_cagr(yearly_dividends, years_back):
    current_year = datetime.now().year
    end_year = current_year - 1  # 항상 작년 기준
    start_year = end_year - years_back + 1

    if start_year not in yearly_dividends.index or end_year not in yearly_dividends.index:
        return None

    starting_dividend = yearly_dividends.loc[start_year]
    ending_dividend = yearly_dividends.loc[end_year]

    if starting_dividend <= 0:
        return None

    # n = 연속 연도 수 (years_back - 1)
    cagr = (ending_dividend / starting_dividend)**(1 / (years_back - 1)) - 1
    return round(cagr, 4)


# 함수: 최근 연도(작년)부터 연속 배당 성장 연수 계산
def calculate_consecutive_growth(yearly_dividends):
    current_year = datetime.now().year
    last_year = current_year - 1  # 작년부터 시작
    consecutive_growth = 0
    year = last_year

    while year in yearly_dividends and (year - 1) in yearly_dividends:
        if yearly_dividends.loc[year] > yearly_dividends.loc[year - 1]:
            consecutive_growth += 1
            year -= 1
        else:
            break
    return consecutive_growth


# 예제: 단일 티커
ticker_symbol = "NVO"
yearly_dividends = fetch_yearly_dividends(ticker_symbol)

if yearly_dividends is None:
    print(f"{ticker_symbol} 배당 데이터가 없습니다.")
else:
    print("\n연도별 배당금:")
    print(yearly_dividends)

    # CAGR 계산
    cagr_3y = calculate_dividend_cagr(yearly_dividends, 3)
    cagr_5y = calculate_dividend_cagr(yearly_dividends, 5)

    # 연속 배당 성장 연수 계산
    consecutive_growth_years = calculate_consecutive_growth(yearly_dividends)

    # 출력
    print(f"\n최근 3년 배당 CAGR: {cagr_3y*100:.2f}%" if cagr_3y else "N/A")
    print(f"최근 5년 배당 CAGR: {cagr_5y*100:.2f}%" if cagr_5y else "N/A")
    print(f"최근부터 연속 배당 성장 연수 (작년 기준): {consecutive_growth_years}년")
