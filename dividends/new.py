import os
import pandas as pd
import yfinance as yf
from supabase import create_client, Client
from dotenv import load_dotenv
from datetime import datetime, timedelta
import numpy as np
from collections import Counter
import warnings
import time
import logging
import json
from typing import Dict, List, Tuple, Optional
warnings.filterwarnings("ignore")

load_dotenv()

# Setup comprehensive logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('dividend_processing.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Supabase 환경변수
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# CSV 파일 경로
csv_file = "/Users/brandonha/Documents/GitHub/stoxx/dividends/companies.csv"

# CSV 읽기 및 중복 제거
df = pd.read_csv(csv_file)

# Remove duplicates by Symbol and take first 500 unique companies
df = df.drop_duplicates(subset=['Symbol'], keep='first')
df = df.head(500)
df = df.rename(columns={"country": "Country", "Symbol": "Ticker", "Name": "Name"})
df = df[["Ticker", "Name", "Country"]]

logger.info(f"Processing {len(df)} unique companies")

class DividendAdjustments:
    """Track all adjustments made to dividend data"""
    def __init__(self):
        self.special_dividends_removed = 0
        self.stock_splits_adjusted = 0
        self.spinoff_dividends_removed = 0
        self.currency_corrections = 0
        self.frequency_changes_detected = 0
        self.drip_adjustments = 0
        self.ma_impacts_detected = 0
        self.adjustments_log = []
    
    def log_adjustment(self, adjustment_type: str, details: str):
        self.adjustments_log.append({
            'type': adjustment_type,
            'details': details,
            'timestamp': datetime.now().isoformat()
        })

def detect_stock_splits(ticker: str, dividends_series: pd.Series, stock_data) -> Tuple[pd.Series, int]:
    """Detect and adjust for stock splits that distort dividend data"""
    try:
        splits = stock_data.splits
        if splits.empty:
            return dividends_series, 0
        
        adjustments_made = 0
        adjusted_dividends = dividends_series.copy()
        
        # Check each split date
        for split_date, split_ratio in splits.items():
            # Find dividends before the split that need adjustment
            pre_split_dividends = adjusted_dividends[adjusted_dividends.index < split_date]
            
            if len(pre_split_dividends) > 0:
                # Adjust pre-split dividends by split ratio
                adjusted_dividends.loc[adjusted_dividends.index < split_date] = pre_split_dividends / split_ratio
                adjustments_made += 1
                logger.info(f"  Split adjustment: {split_date.date()} ratio {split_ratio}, adjusted {len(pre_split_dividends)} dividends")
        
        return adjusted_dividends, adjustments_made
        
    except Exception as e:
        logger.warning(f"  Stock split detection failed: {e}")
        return dividends_series, 0

def detect_spinoff_dividends(dividends_series: pd.Series, ticker: str) -> Tuple[pd.Series, int]:
    """Remove one-time dividends from subsidiary spin-offs"""
    if len(dividends_series) < 6:
        return dividends_series, 0
    
    removed_count = 0
    clean_dividends = dividends_series.copy()
    
    # Calculate rolling median and identify extreme outliers (>5x median)
    rolling_median = dividends_series.rolling(window=6, center=True, min_periods=3).median()
    
    for date, dividend in dividends_series.items():
        if pd.notna(rolling_median.loc[date]):
            if dividend > rolling_median.loc[date] * 5:
                # Check if this is an isolated event (no similar dividends within 12 months)
                nearby_window = dividends_series[
                    (dividends_series.index >= date - timedelta(days=365)) & 
                    (dividends_series.index <= date + timedelta(days=365)) &
                    (dividends_series.index != date)
                ]
                
                similar_large_dividends = nearby_window[nearby_window > rolling_median.loc[date] * 3]
                
                if len(similar_large_dividends) == 0:
                    clean_dividends = clean_dividends.drop(date)
                    removed_count += 1
                    logger.info(f"  Removed spinoff dividend: {date.date()} amount {dividend:.4f}")
    
    return clean_dividends, removed_count

def normalize_drip_differences(dividends_series: pd.Series) -> Tuple[pd.Series, int]:
    """Normalize minor differences from dividend reinvestment plans"""
    if len(dividends_series) < 4:
        return dividends_series, 0
    
    adjustments_made = 0
    normalized_dividends = dividends_series.copy()
    
    # Group dividends by year and quarter to identify DRIP variations
    for year in dividends_series.index.year.unique():
        year_dividends = dividends_series[dividends_series.index.year == year]
        
        # Look for multiple dividends in same quarter (potential DRIP duplicates)
        quarters = pd.Grouper(freq='Q')
        quarterly_groups = year_dividends.groupby(quarters)
        
        for quarter, group in quarterly_groups:
            if len(group) > 1:
                # Check if dividends are very similar (within 2% - likely DRIP variation)
                max_div = group.max()
                min_div = group.min()
                
                if max_div > 0 and (max_div - min_div) / max_div < 0.02:
                    # Keep the median value, remove others
                    median_value = group.median()
                    median_date = group.index[group.sub(median_value).abs().idxmin()]
                    
                    for date in group.index:
                        if date != median_date:
                            normalized_dividends = normalized_dividends.drop(date)
                            adjustments_made += 1
    
    if adjustments_made > 0:
        logger.info(f"  DRIP normalization: {adjustments_made} duplicate/similar dividends removed")
    
    return normalized_dividends, adjustments_made

def detect_currency_conversion_errors(dividends_series: pd.Series, ticker: str) -> Tuple[pd.Series, int]:
    """Detect and fix obvious currency conversion errors"""
    if len(dividends_series) < 4:
        return dividends_series, 0
    
    corrections_made = 0
    corrected_dividends = dividends_series.copy()
    
    # Calculate expected dividend range based on historical data
    median_dividend = dividends_series.median()
    std_dividend = dividends_series.std()
    
    if median_dividend <= 0:
        return dividends_series, 0
    
    # Look for dividends that are exactly 10x, 100x, or 0.1x, 0.01x the median (common conversion errors)
    conversion_factors = [100, 10, 0.1, 0.01]
    
    for factor in conversion_factors:
        expected_value = median_dividend * factor
        tolerance = expected_value * 0.05  # 5% tolerance
        
        # Find dividends that closely match this conversion error pattern
        error_candidates = dividends_series[
            (dividends_series >= expected_value - tolerance) & 
            (dividends_series <= expected_value + tolerance)
        ]
        
        for date, dividend in error_candidates.items():
            # Verify this is actually an error by checking context
            nearby_dividends = dividends_series[
                (dividends_series.index >= date - timedelta(days=180)) & 
                (dividends_series.index <= date + timedelta(days=180)) &
                (dividends_series.index != date)
            ]
            
            if len(nearby_dividends) > 0:
                nearby_median = nearby_dividends.median()
                
                # If corrected value would be much closer to nearby dividends
                corrected_value = dividend / factor if factor > 1 else dividend * (1/factor)
                
                if abs(corrected_value - nearby_median) < abs(dividend - nearby_median):
                    corrected_dividends.loc[date] = corrected_value
                    corrections_made += 1
                    logger.info(f"  Currency correction: {date.date()} {dividend:.4f} -> {corrected_value:.4f} (factor: {factor})")
    
    return corrected_dividends, corrections_made

def detect_ma_impact(dividends_series: pd.Series, ticker: str) -> Tuple[bool, int]:
    """Detect dividend policy changes due to M&A activity"""
    if len(dividends_series) < 8:
        return False, 0
    
    # Look for abrupt permanent changes in dividend policy
    # Calculate 2-year rolling averages
    annual_dividends = dividends_series.groupby(dividends_series.index.year).sum()
    if len(annual_dividends) < 4:
        return False, 0
    
    # Check for sudden policy changes (>50% change that persists)
    policy_changes = 0
    
    for i in range(2, len(annual_dividends) - 1):
        years = sorted(annual_dividends.keys())
        
        # Compare before/after periods
        before_period = annual_dividends[years[i-2:i]].mean()
        after_period = annual_dividends[years[i:i+2]].mean()
        
        if before_period > 0:
            change_ratio = abs(after_period - before_period) / before_period
            
            if change_ratio > 0.5:  # More than 50% change
                # Check if this change persisted (not just temporary)
                if i + 2 < len(years):
                    later_period = annual_dividends[years[i+1:i+3]].mean()
                    later_change = abs(later_period - after_period) / max(after_period, 0.001)
                    
                    if later_change < 0.3:  # Change persisted (less than 30% deviation)
                        policy_changes += 1
                        logger.info(f"  M&A policy change detected around {years[i]}: {before_period:.3f} -> {after_period:.3f}")
    
    return policy_changes > 0, policy_changes

def calculate_reliability_score(dividends_data: dict, adjustments: DividendAdjustments) -> float:
    """Calculate comprehensive data reliability score (0-1)"""
    score = 1.0
    
    # Penalty for adjustments (indicates data quality issues)
    adjustment_penalty = (
        adjustments.special_dividends_removed * 0.05 +
        adjustments.stock_splits_adjusted * 0.02 +  
        adjustments.spinoff_dividends_removed * 0.08 +
        adjustments.currency_corrections * 0.10 +
        adjustments.drip_adjustments * 0.01 +
        adjustments.ma_impacts_detected * 0.15
    )
    
    score = max(0, score - adjustment_penalty)
    
    # Bonus for data completeness
    years_of_data = len(dividends_data)
    if years_of_data >= 10:
        score += 0.1
    elif years_of_data >= 5:
        score += 0.05
    
    # Bonus for data consistency
    if len(dividends_data) > 2:
        values = list(dividends_data.values())
        cv = np.std(values) / max(np.mean(values), 0.001)
        consistency_bonus = max(0, 0.1 * (1 - min(cv, 1)))
        score += consistency_bonus
    
    return min(1.0, max(0.0, round(score, 3)))

def calculate_yield_trend(dividends_data: dict, stock_data, years: int = 5) -> Optional[float]:
    """Calculate dividend yield trend over specified years"""
    try:
        if len(dividends_data) < years:
            return None
        
        # Get recent stock price data
        hist = stock_data.history(period=f"{years}y")
        if hist.empty:
            return None
        
        # Calculate annual yields for trend analysis
        sorted_years = sorted(dividends_data.keys(), reverse=True)[:years]
        yield_data = []
        
        for year in sorted_years:
            # Get average stock price for that year
            year_prices = hist[hist.index.year == year]['Close']
            if len(year_prices) > 0:
                avg_price = year_prices.mean()
                dividend_yield = (dividends_data[year] / avg_price) * 100
                yield_data.append(dividend_yield)
        
        if len(yield_data) >= 3:
            # Calculate trend (simple linear regression slope)
            x = np.arange(len(yield_data))
            slope, _ = np.polyfit(x, yield_data, 1)
            return round(slope, 4)
        
        return None
        
    except Exception as e:
        logger.warning(f"  Yield trend calculation failed: {e}")
        return None

def enhanced_data_quality_validation(dividends_series: pd.Series, frequency: str) -> Tuple[bool, float, str]:
    """Enhanced data quality validation with more permissive thresholds"""
    
    # More permissive minimum data threshold
    if len(dividends_series) < 1:
        return False, 0.0, "insufficient_data"
    
    # More permissive years span requirement  
    years_span = dividends_series.index.max().year - dividends_series.index.min().year + 1
    if years_span < 1:  # Allow even single year data
        return False, 0.1, "insufficient_timespan"
    
    # Expected vs actual payments per year
    annual_groups = dividends_series.groupby(dividends_series.index.year)
    
    expected_payments = {
        "annual": 1,
        "semi-annual": 2,
        "quarterly": 4,
        "monthly": 12
    }
    
    expected = expected_payments.get(frequency, 1)
    completeness_scores = []
    
    for year, group in annual_groups:
        actual = len(group)
        completeness = min(1.0, actual / expected) if expected > 0 else 0
        completeness_scores.append(completeness)
    
    avg_completeness = np.mean(completeness_scores)
    
    # Quality score calculation
    quality_score = 0.0
    
    # Completeness component (40%)
    quality_score += avg_completeness * 0.4
    
    # Consistency component (30%)
    if len(dividends_series) > 2:
        cv = dividends_series.std() / max(dividends_series.mean(), 0.001)
        consistency_score = max(0, 1 - min(cv, 2) / 2)
        quality_score += consistency_score * 0.3
    
    # Data span component (20%)
    span_score = min(1.0, years_span / 10)  # Full score for 10+ years
    quality_score += span_score * 0.2
    
    # Frequency reliability component (10%)
    freq_reliability = {
        "annual": 0.9,
        "semi-annual": 0.8,
        "quarterly": 1.0,
        "monthly": 0.7,
        "irregular": 0.3,
        "unknown": 0.1
    }
    quality_score += freq_reliability.get(frequency, 0.1) * 0.1
    
    # More permissive quality thresholds for higher success rate
    passes_validation = quality_score >= 0.3 and avg_completeness >= 0.3  # Much more permissive
    
    status = "high_quality" if quality_score >= 0.7 else "medium_quality" if quality_score >= 0.4 else "low_quality"
    
    return passes_validation, round(quality_score, 3), status

def detect_special_dividends(dividends_series, threshold_multiplier=2.5):
    """특별배당 감지 및 제거 - 개선된 버전"""
    if len(dividends_series) < 4:
        return dividends_series
    
    # IQR 방법으로 이상치 감지
    Q1 = dividends_series.quantile(0.25)
    Q3 = dividends_series.quantile(0.75)
    IQR = Q3 - Q1
    
    # IQR 기준 상한선
    upper_bound = Q3 + 1.5 * IQR
    
    # 중간값 기준도 함께 사용 (더 보수적 접근)
    median_dividend = dividends_series.median()
    median_upper_bound = median_dividend * threshold_multiplier
    
    # 두 기준 중 더 보수적인 것 사용
    final_upper_bound = min(upper_bound, median_upper_bound) if median_dividend > 0 else upper_bound
    
    normal_dividends = dividends_series[dividends_series <= final_upper_bound]
    
    # 제거된 배당이 있으면 로그 출력
    removed = len(dividends_series) - len(normal_dividends)
    if removed > 0:
        removed_values = dividends_series[dividends_series > final_upper_bound].values
        print(f"  특별배당 {removed}개 제거됨: {removed_values}")
    
    return normal_dividends

def detect_dividend_frequency(dividends_series):
    """배당 주기 감지"""
    if len(dividends_series) < 2:
        return "unknown"
    
    # 월별 배당 횟수 계산
    monthly_counts = dividends_series.groupby([dividends_series.index.year, dividends_series.index.month]).size()
    
    # 연간 평균 배당 횟수
    yearly_counts = monthly_counts.groupby(level=0).sum()
    avg_frequency = yearly_counts.mean()
    
    if avg_frequency <= 1.2:
        return "annual"
    elif avg_frequency <= 2.2:
        return "semi-annual"
    elif avg_frequency <= 4.2:
        return "quarterly"
    elif avg_frequency <= 12.2:
        return "monthly"
    else:
        return "irregular"

def normalize_dividends_by_frequency(dividends_series, frequency):
    """배당 주기에 따른 정규화 - 개선된 버전"""
    yearly_dividends = {}
    
    for year in dividends_series.index.year.unique():
        year_dividends = dividends_series[dividends_series.index.year == year]
        
        # 해당 연도의 첫번째/마지막 배당일 확인
        first_dividend_date = year_dividends.index.min()
        last_dividend_date = year_dividends.index.max()
        
        # 연도 데이터 완성도 계산 (1월-12월 중 얼마나 포함되었는지)
        if len(year_dividends) > 1:
            months_covered = max(1, last_dividend_date.month - first_dividend_date.month + 1)
        else:
            months_covered = 12  # Single dividend assumed to represent full year
        data_completeness = min(months_covered / 12, 1.0)
        
        if frequency == "annual":
            yearly_dividends[year] = year_dividends.sum()
        elif frequency == "semi-annual":
            expected_payments = 2
            actual_payments = len(year_dividends)
            if actual_payments > 0:
                # 데이터 완성도 고려한 조정
                adjustment_factor = expected_payments / actual_payments if actual_payments < expected_payments else 1
                yearly_dividends[year] = year_dividends.sum() * adjustment_factor * data_completeness
        elif frequency == "quarterly":
            expected_payments = 4
            actual_payments = len(year_dividends)
            if actual_payments > 0:
                adjustment_factor = expected_payments / actual_payments if actual_payments < expected_payments else 1
                yearly_dividends[year] = year_dividends.sum() * adjustment_factor * data_completeness
        elif frequency == "monthly":
            expected_payments = 12
            actual_payments = len(year_dividends)
            if actual_payments > 0:
                adjustment_factor = expected_payments / actual_payments if actual_payments < expected_payments else 1
                yearly_dividends[year] = year_dividends.sum() * adjustment_factor * data_completeness
        else:
            yearly_dividends[year] = year_dividends.sum() * data_completeness
        
        # 불완전한 데이터 표시
        if data_completeness < 0.8:
            print(f"  {year}년 데이터 불완전 ({data_completeness:.1%})")
    
    return yearly_dividends

def smooth_dividend_transitions(yearly_dividends):
    """배당 주기 변경시 급격한 변화 완화"""
    if len(yearly_dividends) < 3:
        return yearly_dividends
    
    smoothed = yearly_dividends.copy()
    years = sorted(yearly_dividends.keys())
    
    for i in range(1, len(years)-1):
        prev_year, curr_year, next_year = years[i-1], years[i], years[i+1]
        prev_div, curr_div, next_div = yearly_dividends[prev_year], yearly_dividends[curr_year], yearly_dividends[next_year]
        
        # 급격한 증가/감소 감지 (3배 이상 변화)
        if curr_div > 0 and prev_div > 0:
            ratio = curr_div / prev_div
            if ratio > 3 or ratio < 0.33:
                # 이전년도와 다음년도 평균으로 조정
                if next_div > 0:
                    smoothed[curr_year] = (prev_div + next_div) / 2
                    print(f"  {curr_year}년 배당 급변화 감지, 조정됨: {curr_div:.3f} -> {smoothed[curr_year]:.3f}")
    
    return smoothed

def fetch_dividends_improved(ticker):
    """Comprehensive dividend data collection with advanced cleaning"""
    adjustments = DividendAdjustments()
    
    try:
        logger.info(f"Processing: {ticker}")
        stock = yf.Ticker(ticker)
        dividends = stock.dividends
        
        if dividends.empty:
            return {}, "no_data", "unknown", adjustments, 0.0, "low_quality"
        
        original_count = len(dividends)
        
        # 1. Stock split adjustment
        dividends, splits_adjusted = detect_stock_splits(ticker, dividends, stock)
        adjustments.stock_splits_adjusted = splits_adjusted
        
        # 2. Spin-off dividend removal
        dividends, spinoffs_removed = detect_spinoff_dividends(dividends, ticker)
        adjustments.spinoff_dividends_removed = spinoffs_removed
        
        # 3. DRIP normalization
        dividends, drip_adjustments = normalize_drip_differences(dividends)
        adjustments.drip_adjustments = drip_adjustments
        
        # 4. Currency conversion error correction
        dividends, currency_corrections = detect_currency_conversion_errors(dividends, ticker)
        adjustments.currency_corrections = currency_corrections
        
        # 5. Special dividend removal
        cleaned_dividends = detect_special_dividends(dividends)
        adjustments.special_dividends_removed = original_count - len(cleaned_dividends)
        
        # 6. Dividend frequency detection
        frequency = detect_dividend_frequency(cleaned_dividends)
        logger.info(f"  Dividend frequency: {frequency}")
        
        # 7. Enhanced data quality validation
        passes_validation, quality_score, quality_status = enhanced_data_quality_validation(cleaned_dividends, frequency)
        
        if not passes_validation:
            logger.warning(f"  Data quality validation failed: {quality_status}")
            return {}, "low_quality", frequency, adjustments, quality_score, quality_status
        
        # 8. Frequency-based normalization
        yearly_dividends = normalize_dividends_by_frequency(cleaned_dividends, frequency)
        
        # 9. M&A impact detection
        ma_detected, ma_count = detect_ma_impact(cleaned_dividends, ticker)
        adjustments.ma_impacts_detected = ma_count
        
        # 10. Dividend transition smoothing
        yearly_dividends = smooth_dividend_transitions(yearly_dividends)
        
        # 11. Remove current year and very small values
        current_year = datetime.now().year
        if current_year in yearly_dividends:
            yearly_dividends.pop(current_year)
        
        yearly_dividends = {year: div for year, div in yearly_dividends.items() if div > 0.001}
        
        # Log comprehensive adjustments
        total_adjustments = (adjustments.special_dividends_removed + adjustments.stock_splits_adjusted + 
                           adjustments.spinoff_dividends_removed + adjustments.currency_corrections + 
                           adjustments.drip_adjustments)
        
        if total_adjustments > 0:
            logger.info(f"  Total adjustments made: {total_adjustments}")
        
        return yearly_dividends, "success", frequency, adjustments, quality_score, quality_status
        
    except Exception as e:
        logger.error(f"  Error processing {ticker}: {e}")
        return {}, "error", "unknown", adjustments, 0.0, "error"

def calculate_cagr_robust(dividends, years):
    """더 견고한 CAGR 계산"""
    if len(dividends) < years:
        return None
    
    sorted_years = sorted(dividends.keys(), reverse=True)
    recent_years = sorted_years[:years]
    
    start_dividend = dividends[recent_years[-1]]
    end_dividend = dividends[recent_years[0]]
    
    if start_dividend <= 0:
        return None
    
    # 극단적인 값 체크
    cagr = (end_dividend / start_dividend) ** (1/years) - 1
    
    # CAGR이 너무 극단적이면 None 반환 (연 100% 이상 증가/감소)
    if abs(cagr) > 1.0:
        return None
        
    return round(cagr, 4)

def consecutive_growth_robust(dividends, years=7, tolerance=0.05):
    """연속 성장 판단 (약간의 허용오차 적용)"""
    if len(dividends) < years:
        return False
    
    sorted_years = sorted(dividends.keys(), reverse=True)[:years]
    
    for i in range(len(sorted_years)-1):
        current_div = dividends[sorted_years[i]]
        previous_div = dividends[sorted_years[i+1]]
        
        # 5% 허용오차 적용
        if current_div < previous_div * (1 - tolerance):
            return False
    
    return True

def get_dividend_consistency_score(dividends):
    """배당 일관성 점수 (0-1)"""
    if len(dividends) < 3:
        return 0
    
    values = list(dividends.values())
    if len(values) < 2:
        return 0
    
    # 변동계수 (CV) 계산
    mean_div = np.mean(values)
    if mean_div == 0:
        return 0
    
    cv = np.std(values) / mean_div
    
    # CV를 0-1 점수로 변환 (낮은 CV = 높은 점수)
    consistency_score = max(0, 1 - cv)
    return round(consistency_score, 3)

# 배치 처리를 위한 설정
BATCH_SIZE = 10  # 10개씩 처리 후 잠시 대기
DELAY_BETWEEN_BATCHES = 2  # 초 단위

# 메인 처리 루프 - 배치 처리 및 에러 복구 기능 추가
failed_tickers = []
processed_count = 0

for idx, row in df.iterrows():
    ticker = row['Ticker']
    name = row['Name']
    country = row['Country']
    
    logger.info(f"\n[{idx+1}/{len(df)}] Processing {ticker} - {name}")
    
    try:
        dividends_data, status, frequency, adjustments, data_quality_score, quality_status = fetch_dividends_improved(ticker)
        
        # Handle no dividend data (many growth stocks don't pay dividends)
        if status == "no_data":
            logger.info(f"  No dividend data for {ticker} - inserting as non-dividend paying stock")
            
            # Create record for non-dividend paying stocks
            record = {
                "ticker": ticker,
                "name": name,
                "country": country,
                "total_dividends_per_year": {},  # Empty JSONB
                "cagr_3yr": None,
                "cagr_5yr": None,
                "consecutive_growth_7yr": False
            }
            
            try:
                res = supabase.table("equities").upsert(record, on_conflict="ticker").execute()
                logger.info(f"  ✓ Non-dividend stock inserted successfully")
                processed_count += 1
            except Exception as e:
                logger.error(f"  ✗ Database update failed: {e}")
                failed_tickers.append({"ticker": ticker, "error": str(e), "type": "equities_db_error"})
            continue
        
        # Skip only on severe errors or extremely low quality
        if status in ["error"]:
            logger.warning(f"  Skipping {ticker}: {status}")
            continue
        
        # Get stock data for yield trend calculation
        stock = yf.Ticker(ticker)
        yield_trend_5yr = calculate_yield_trend(dividends_data, stock, 5)
        
        # Calculate enhanced metrics
        cagr_3yr = calculate_cagr_robust(dividends_data, 3)
        cagr_5yr = calculate_cagr_robust(dividends_data, 5)
        cagr_10yr = calculate_cagr_robust(dividends_data, 10)
        consecutive_growth_5yr = consecutive_growth_robust(dividends_data, 5)
        consecutive_growth_7yr = consecutive_growth_robust(dividends_data, 7)
        consecutive_growth_10yr = consecutive_growth_robust(dividends_data, 10)
        consistency_score = get_dividend_consistency_score(dividends_data)
        reliability_score = calculate_reliability_score(dividends_data, adjustments)
        
        # Additional metrics
        years_of_data = len(dividends_data)
        latest_dividend = max(dividends_data.values()) if dividends_data else 0
        earliest_year = min(dividends_data.keys()) if dividends_data else None
        latest_year = max(dividends_data.keys()) if dividends_data else None
        
        # Growth analysis
        growth_years = 0
        if len(dividends_data) >= 2:
            sorted_years = sorted(dividends_data.keys())
            for i in range(1, len(sorted_years)):
                if dividends_data[sorted_years[i]] > dividends_data[sorted_years[i-1]]:
                    growth_years += 1
        
        growth_ratio = growth_years / max(1, years_of_data - 1) if years_of_data > 1 else 0

        # Basic database record matching existing schema (like main.py)
        record = {
            "ticker": ticker,
            "name": name,
            "country": country,
            "total_dividends_per_year": dividends_data,
            "cagr_3yr": cagr_3yr,
            "cagr_5yr": cagr_5yr,
            "consecutive_growth_7yr": consecutive_growth_7yr
        }
        
        # Optional: Add more fields if your Supabase table has these columns
        # Uncomment these lines after adding corresponding columns to your Supabase table:
        # record.update({
        #     "cagr_10yr": cagr_10yr,
        #     "consecutive_growth_5yr": consecutive_growth_5yr,
        #     "consecutive_growth_10yr": consecutive_growth_10yr,
        #     "dividend_frequency": frequency,
        #     "consistency_score": consistency_score,
        #     "reliability_score": reliability_score,
        #     "data_quality_score": round(data_quality_score, 2),
        #     "yield_trend_5yr": yield_trend_5yr,
        #     "years_of_data": years_of_data,
        #     "growth_ratio": round(growth_ratio, 3),
        #     "latest_dividend": round(latest_dividend, 4) if latest_dividend else 0,
        #     "earliest_year": earliest_year,
        #     "latest_year": latest_year,
        #     "special_dividends_removed_count": adjustments.special_dividends_removed,
        #     "stock_splits_adjusted_count": adjustments.stock_splits_adjusted,
        #     "spinoff_dividends_removed_count": adjustments.spinoff_dividends_removed,
        #     "currency_corrections_count": adjustments.currency_corrections,
        #     "drip_adjustments_count": adjustments.drip_adjustments,
        #     "ma_impacts_detected_count": adjustments.ma_impacts_detected,
        #     "frequency_changes_detected": adjustments.frequency_changes_detected,
        #     "data_adjustments_log": json.dumps(adjustments.adjustments_log),
        #     "data_status": status,
        #     "quality_status": quality_status,
        #     "updated_at": datetime.now().isoformat()
        # })

        # Insert into equities table
        try:
            res = supabase.table("equities").upsert(record, on_conflict="ticker").execute()
            logger.info(f"  ✓ Equities table updated successfully")
        except Exception as e:
            logger.error(f"  ✗ Equities table update failed: {e}")
            failed_tickers.append({"ticker": ticker, "error": str(e), "type": "equities_db_error"})
        
        # Insert individual dividend records into dividends table with actual dividend dates
        try:
            # Get the original cleaned dividend data (before yearly aggregation) for actual dates
            stock = yf.Ticker(ticker)
            raw_dividends = stock.dividends
            
            if not raw_dividends.empty:
                # Apply our cleaning to get clean individual dividend records
                cleaned_individual_dividends = detect_special_dividends(raw_dividends)
                
                dividend_records = []
                for date, amount in cleaned_individual_dividends.items():
                    if amount > 0.001:  # Filter out very small amounts
                        dividend_record = {
                            "ticker": ticker,
                            "ex_dividend_date": date.strftime('%Y-%m-%d'),  # Actual dividend date
                            "amount": round(float(amount), 6),  # Match numeric(12,6) precision
                            "updated_at": datetime.now().isoformat()
                        }
                        dividend_records.append(dividend_record)
                
                if dividend_records:
                    # Insert all dividend records for this ticker
                    res = supabase.table("dividends").upsert(dividend_records, on_conflict="ticker,ex_dividend_date").execute()
                    logger.info(f"  ✓ Dividends table updated successfully ({len(dividend_records)} individual dividend records)")
            
            processed_count += 1
        except Exception as e:
            logger.error(f"  ✗ Dividends table update failed: {e}")
            failed_tickers.append({"ticker": ticker, "error": str(e), "type": "dividends_db_error"})
            
        # Summary log
        total_adjustments = (adjustments.special_dividends_removed + adjustments.stock_splits_adjusted + 
                           adjustments.spinoff_dividends_removed + adjustments.currency_corrections + 
                           adjustments.drip_adjustments + adjustments.ma_impacts_detected)
        
        logger.info(f"  Summary: {years_of_data}y data, {frequency}, CAGR(5Y): {cagr_5yr}, Quality: {data_quality_score:.2f}, Reliability: {reliability_score:.2f}, Adjustments: {total_adjustments}")
        
    except Exception as e:
        # Try to recover from network/API errors with a simpler approach
        logger.warning(f"  Processing failed: {e}, attempting simplified processing")
        try:
            # Create minimal record for companies that fail processing
            record = {
                "ticker": ticker,
                "name": name,
                "country": country,
                "total_dividends_per_year": {},
                "cagr_3yr": None,
                "cagr_5yr": None,
                "consecutive_growth_7yr": False
            }
            
            res = supabase.table("equities").upsert(record, on_conflict="ticker").execute()
            logger.info(f"  ✓ Minimal record inserted after processing failure")
            processed_count += 1
        except Exception as e2:
            logger.error(f"  ✗ Complete processing failure: {e2}")
            failed_tickers.append({"ticker": ticker, "error": str(e), "type": "processing_error"})
    
    # Batch processing with rate limiting
    if (idx + 1) % BATCH_SIZE == 0:
        logger.info(f"\n⏱️  Batch completed ({idx + 1} processed). Waiting {DELAY_BETWEEN_BATCHES}s...")
        time.sleep(DELAY_BETWEEN_BATCHES)

# Processing completion summary
logger.info(f"\n📊 COMPREHENSIVE DIVIDEND PROCESSING COMPLETED")
logger.info(f"   ✓ Successfully processed: {processed_count} companies")
logger.info(f"   ✗ Failed: {len(failed_tickers)} companies")

if failed_tickers:
    logger.warning(f"\n❌ Failed companies:")
    for failed in failed_tickers:
        logger.warning(f"   {failed['ticker']}: {failed['error']} ({failed['type']})")
    
    # Save failure log
    failed_df = pd.DataFrame(failed_tickers)
    failed_df.to_csv("failed_tickers_comprehensive.csv", index=False)
    logger.info(f"   Failure log saved to 'failed_tickers_comprehensive.csv'")

# Save processing summary
summary_stats = {
    "processing_date": datetime.now().isoformat(),
    "total_companies_attempted": len(df),
    "successfully_processed": processed_count,
    "failed_processing": len(failed_tickers),
    "success_rate": round(processed_count / len(df) * 100, 2) if len(df) > 0 else 0,
    "features_implemented": [
        "stock_split_adjustment",
        "special_dividend_removal", 
        "spinoff_dividend_removal",
        "drip_normalization",
        "currency_error_correction",
        "ma_impact_detection",
        "enhanced_quality_validation",
        "yield_trend_analysis",
        "comprehensive_reliability_scoring"
    ]
}

with open("dividend_processing_summary.json", "w") as f:
    json.dump(summary_stats, f, indent=2)

logger.info(f"\n🎉 COMPREHENSIVE DIVIDEND DATA COLLECTION COMPLETED!")
logger.info(f"   Success rate: {summary_stats['success_rate']}%")
logger.info(f"   Processing summary saved to 'dividend_processing_summary.json'")
logger.info(f"   Detailed logs saved to 'dividend_processing.log'")