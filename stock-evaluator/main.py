import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
from ta.momentum import RSIIndicator

# -----------------------------
# Configuration
# -----------------------------
TICKERS = [
    "NVO","INTU","COST",
    "APH","KLAC","PH","CTAS","ZTS","MSCI","FIX","DPZ","AVGO",
    "MSFT","AAPL","CSCO","LRCX","LIN","PEP","QCOM","AMGN","TXN",
    "ADI","HON","CMCSA","ADP","SBUX","MDLZ","CSX","ROP","FAST",
    "XEL","PAYX","MCHP","CDW",
    "RY","NVS","MUFG","SONY","SAP","SMFG","SNY","BN","RELX",
    "INFY","CNI","DEO"
]

RSI_WINDOW = 14
LOOKBACK_DAYS_CALENDAR = 90

# -----------------------------
# Functions
# -----------------------------
def fetch_stock_data(ticker):
    """Downloads stock data using yfinance."""
    try:
        # auto_adjust=False to match Google Finance raw closing prices
        df = yf.download(ticker, period="1y", interval="1d", progress=False, auto_adjust=False)
        if df.empty: return None
        return df
    except Exception as e:
        print(f"Error fetching {ticker}: {e}")
        return None

def calculate_rsi(prices, window=RSI_WINDOW):
    """Calculates the Relative Strength Index (RSI)."""
    if isinstance(prices, pd.DataFrame):
        prices = prices.iloc[:, 0]
    prices_series = prices.squeeze().dropna()
    rsi_indicator = RSIIndicator(prices_series, window=window, fillna=True)
    return rsi_indicator.rsi().iloc[-1]

def get_sparkline_metrics(df):
    """
    Replicates Google Sheets Sparkline logic:
    Compares current price to the price from 90 calendar days ago.
    """
    prices = df["Close"].squeeze().dropna()
    end_price = prices.iloc[-1]
    end_date = prices.index[-1]
    target_start_date = end_date - timedelta(days=LOOKBACK_DAYS_CALENDAR)
    
    try:
        # Find the nearest previous trading day if 90 days ago was a weekend
        idx = prices.index.get_indexer([target_start_date], method='pad')[0]
        if idx == -1: idx = 0
        start_price = prices.iloc[idx]
    except:
        start_price = prices.iloc[0]

    color = "RED" if end_price < start_price else "GREEN"
    return float(start_price), float(end_price), color

def calculate_score(rsi, color):
    """
    Maintains 30/70 RSI thresholds but adds weight for proximity 
    to trigger Strong Buy/Sell signals.
    """
    score = 50
    trend = "DOWN" if color == "RED" else "UP"
    
    # 1. RSI-based Weighting
    if rsi <= 30:
        score += 30  # Confirmed Oversold
    elif rsi <= 35:
        score += 20  # Entering Oversold (Targets: CDW, SONY, etc.)
    elif rsi <= 40:
        score += 10  # Mildly Oversold
        
    if rsi >= 70:
        score -= 30  # Confirmed Overbought
    elif rsi >= 65:
        score -= 20  # Entering Overbought (Targets: RY, etc.)
    elif rsi >= 60:
        score -= 10  # Mildly Overbought
    
    # 2. Trend + RSI Combo Bonus
    # If trend is DOWN (RED) and RSI < 40, add +10 for rebound potential
    if trend == "DOWN" and rsi < 40:
        score += 10 
    # If trend is UP (GREEN) and RSI > 60, sub -10 for correction risk
    elif trend == "UP" and rsi > 60:
        score -= 10
    
    return max(0, min(100, score))

def generate_signal(score):
    """Classifies the final investment signal based on the calculated score."""
    if score >= 80:
        return "STRONG BUY"
    elif score >= 70:
        return "BUY"
    elif score <= 20:
        return "STRONG SELL"
    elif score <= 30:
        return "SELL"
    else:
        return "HOLD"

def evaluate_stock(ticker):
    """Main wrapper to fetch data and process indicators for a ticker."""
    df = fetch_stock_data(ticker)
    if df is None or len(df) < RSI_WINDOW: return None

    rsi = calculate_rsi(df["Close"])
    start_p, end_p, color = get_sparkline_metrics(df)
    score = calculate_score(rsi, color)
    signal = generate_signal(score)

    return {
        "Ticker": ticker,
        "Price": round(end_p, 2),
        "RSI": round(rsi, 1),
        "Trend": "DOWN" if color == "RED" else "UP",
        "Color": color,
        "Score": score,
        "Signal": signal
    }

# -----------------------------
# Main Execution
# -----------------------------
if __name__ == "__main__":
    print(f"Analyzing {len(TICKERS)} stocks with weighted 30/70 RSI logic...\n")
    
    results = [evaluate_stock(t) for t in TICKERS]
    final_df = pd.DataFrame([r for r in results if r is not None])
    
    # Sort by Score descending (Highest potential first)
    df_sorted = final_df.sort_values(by="Score", ascending=False)
    
    print("="*80)
    print(f"{'Ticker':<10} {'Price':<10} {'RSI':<8} {'Color':<8} {'Score':<8} {'Signal':<15}")
    print("-" * 80)
    for _, row in df_sorted.iterrows():
        print(f"{row['Ticker']:<10} {row['Price']:<10.2f} {row['RSI']:<8.1f} {row['Color']:<8} {row['Score']:<8} {row['Signal']:<15}")

    # Final Summary Table
    print("\n" + "="*80)
    print("=== FINAL SUMMARY ===")
    print("="*80)
    counts = final_df['Signal'].value_counts()
    for sig in ["STRONG BUY", "BUY", "HOLD", "SELL", "STRONG SELL"]:
        print(f"{sig:<15}: {counts.get(sig, 0)} stocks")
    print("="*80)