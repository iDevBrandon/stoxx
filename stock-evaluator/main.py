import os
from dotenv import load_dotenv
from supabase import create_client
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
from ta.momentum import RSIIndicator

load_dotenv()

# -----------------------------
# Supabase client (optional)
# -----------------------------
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
supabase = None

if SUPABASE_URL and SUPABASE_KEY:
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    print("[INFO] Supabase client initialized")
else:
    print("[INFO] Supabase not configured, running in local mode")

# -----------------------------
# Configuration
# -----------------------------
QQQ = [
  "ADBE","AMD","ABNB","ALNY","GOOGL","GOOG","AMZN","AEP","AMGN","ADI",
  "AAPL","AMAT","APP","ARM","ASML","AZN","TEAM","ADSK","ADP","AXON",
  "BKR","BKNG","AVGO","CDNS","CHTR","CTAS","CSCO","CCEP","CTSH","CMCSA",
  "CEG","CPRT","CSGP","COST","CRWD","CSX","DDOG","DXCM","FANG","DASH",
  "EA","EXC","FAST","FER","FTNT","GEHC","GILD","HON","IDXX","INSM",
  "INTC","INTU","ISRG","KDP","KLAC","KHC","LRCX","LIN","MAR","MRVL",
  "MELI","META","MCHP","MU","MSFT","MSTR","MDLZ","MPWR","MNST","NFLX",
  "NVDA","NXPI","ORLY","ODFL","PCAR","PLTR","PANW","PAYX","PYPL","PDD",
  "PEP","QCOM","REGN","ROP","ROST","STX","SHOP","SBUX","SNPS","TMUS",
  "TTWO","TSLA","TXN","TRI","VRSK","VRTX","WBD","WDC","WDAY","XEL",
  "ZS"
]


VIG = [
    "AVGO","MSFT","AAPL","JPM","LLY","V","XOM","JNJ","WMT","MA","COST","ABBV",
    "BAC","HD","PG","ORCL","CSCO","UNH","IBM","KO","CAT","MRK","GS","ABT",
    "MCD","MS","PEP","LRCX","LIN","AMGN","QCOM","NEE","INTU","APH","SPGI",
    "KLAC","ACN","TXN","BLK","DHR","UNP","LOW","MDT","ETN","ADI","SYK","HON",
    "MCK","CB","ADP","CME","CMCSA","SBUX","LMT","MMC","ICE","GD","WM","BK",
    "SHW","NOC","NKE","MDLZ","AON","MCO","ELV","EMR","PNC","COR","ECL","CMI",
    "TEL","ITW","TRV","CSX","CL","CTAS","AJG","SRE","MSI","APD","ZTS","ALL",
    "BDX","PSX","AFL","LHX","CAH","XEL","ROP","FAST","DHI","ROK","RSG","MSCI",
    "ETR","AMP","MET","GWW","PEG","TGT","NDAQ","VMC","HIG","RMD","NUE","SYY",
    "PAYX","FIX","STT","XYL","TSCO","MCHP","FITB","KR","AEE","DTE","HSY",
    "ATO","RJF","CBOE","BR","STE","CINF","DOV","AWK","VLTO","HPQ","BRO","WRB",
    "STLD","HUBB","WSM","CMS","PPG","DGX","CASY","CHD","NI","EXPD","WST",
    "HEI-A","CDW","CHRW","RBA","GPC","LNT","SNA","PNR","PFG","MKC","TPL","TSN",
    "RGLD","LII","ALB","FNF","RS","ITT","ALLE","MAS","DKS","CSL","RPM","GGG",
    "AVY","JBHT","CLX","LECO","DPZ","IEX","RNR","NDSN","HEI-A","JKHY","RGA","EVR",
    "HII","UNM","WSO","DTM","AIZ","SCI","WTRG","GL","WMS","ENSG","ORI","DCI",
    "FDS","BAH","AIT","AFG","OC","TTEK","SSB","WTFC","DOX","PRI","ATR","OSK",
    "LAD","POOL","CFR","UMBF","ZION","SEIC","AOS","SOLS","WTS","NFG","ERIE",
    "CADE","CHDN","EMN","R","IDA","TTC","INGR","SSD","AL","CBSH","FAF","THG",
    "AGCO","PB","CHE","LFUS","MKTX","MSA","GATX","RLI","THO","BF-B","TXNM",
    "UFPI","BMI","MORN","TKR","HOMB","BCPC","OZK","SIGI","BC","DLB","FFIN",
    "AGO","CNO","AVT","MWA","GHC","UCB","EXPO","FELE","INDB","IBOC","SFBS",
    "SLGN","MATX","OTTR","BRC","MZTI","CBT","KAI","CPK","FUL","MGEE","SXI",
    "CBU","GFF","AWR","AVNT","HWKN","CWT","ABM","WDFC","MGRC","MTRN","BOKF",
    "TOWN","BANF","HI","WLK","CSGS","NBTB","FRME","EFSC","DDS","HNI","KWR",
    "POWI","HMN","IOSP","NNI","SYBT","CHCO","CNS","ANDE","WOR","ALG","LMAT",
    "NHC","AGM","TCBK","WLY","HTO","LKFN","JJSF","TNC","NSP","LNN","WABC",
    "GABC","SRCE","BF-A","BFC","WS","SCL","GRC","MSEX","UTL","FMBH","APOG",
    "AMSF","TR","MBWM","IBCP","RBCAA","FCBC","ODC","NRIM","SMBC","CASS",
    "YORW","FBIZ","HY","UNTY","SCVL"
]




VXUS = [
    'TSM', 'TCEHY', 'ASML', 'BABA', "AZN","RHHBY", "NSRGY", "SAP", "HSBC",
    "NVS", "RY","SHEL", "TM", "SIEGY", "SHOP", "LVMUY", "SONY", "MUFG", "CMWAY", "ALIZY","SAN", "NVO", "SBGSY", "UL", "TD", "IBDRY", "HTHIY", "EADSY", "HDB", "UBS","BBVA", "TTE", "RYCEY", "BTI", "SAFRY", "UNCRY", "ABBNY", "CFRUY", "SMFG","AAIGF", "SNY", "ENB", "DTEGY", "SFTBY", "ESLOY",  "BN", "MSBHF","RELX", "TKOMF", "BAESY", "INFY", "LDNXF", "CNI", "DEO", "DBOEY",'RACE', 'HESAY', "FJTSY", "WCN", "DSDVY", "ATD.TO", "FNV", "DOL.TO", "ASAZY", "IFC.TO", "GVDNY", "UCBJY", "SVNDY", "TTDKY", "SXYAY", "SDZNY", "NTTYY", "SMPNY", "AHT.L",  
]

CAGR = ['SMT.L', 'NET', "V","APH","KLAC","INTU","PH","CTAS","ZTS","MPWR", "MSCI", "FIX", "DPZ", "FICO", "NTDOY", "VRSN" , "LMP.L"]

GURU = [
    "FLUT", "ALC", "MSFT", "V", "INTU", "GE", "AMZN", "MCO", "MMC", "ICE",
    "GTLS", "APTV", "WFRD", "AXTA", "OSK", "ASH", "GPK", "NOMD", "PVH", "DOLE",
    "TDG", "MA", "HLT", "GOOGL", "FICO", "BRK-B", "WM", "CNI", "CAT", "DE",
    "ECL", "WMT", "FDX", "KOF", "UBER", "BN", "HHH", "GOOG", "QSR", "CMG",
    "SEG", "NBR", "LNC", "GTN", "QUAD", "BFH", "TDAY", "CNDT", "AXL", "JELD",
    "JXN", "IQV", "WBD", "PSX", "FCNCA", "LAD", "ABNB", "CRM", "EFX", "SCHW",
    "JOE", "EPD", "OZK", "WRB", "OXY", "ET", "BRK-A", "AAPL", "FANG", "IBKR",
    "GIL", "NRP", "GWRE", "LEN", "SGU", "IEP", "CVI", "SWX", "UAN", "SATS",
    "IFF", "CTRI", "JBLU", "AEP", "CZR", "JNJ", "REZI", "BOKF", "AMG", "SNA",
    "PHIN", "BAC", "B", "MHK", "APA", "SE", "NVDA", "META", "TTWO", "APP",
    "TSM", "RDDT", "SPGI", "CP", "FER", "DG", "KGC", "NEM", "OLN", "DLTR",
    "FIVE", "DECK", "VLO", "COF", "AMAT", "USB", "CVS", "MGM", "MKL", "VTRS",
    "KKR", "ORLY", "CSGP", "ROP", "CVNA", "HGV", "CDLX", "SWIM", "PCG", "NSC",
    "FLUT", "CASY", "LOAR", "ABG", "SGI", "CPNG", "WTW", "UHAL-B", "GRBK",
    "FLR", "CNR", "BHF", "KD", "PENN", "DHT", "TEVA", "JPM", "MS", "PNC",
    "QCOM", "MDT", "BKNG", "TSCO", "MSI", "BABA", "WHR", "KWEB", "NRG", "VST",
    "FOUR", "OKTA", "PCOR", "MNDY", "BRZE", "NCNO", "BLND", "VERX", "RTX",
    "JCI", "FISV", "MET", "BK", "PDD", "DIS", "ASML", "ORCL", "WPM", "BDX",
    "IMO", "HCA", "CHRW", "FN", "IDCC", "SNX", "RLI", "UGI", "SFBS", "REVG",
    "ARW", "SIRI", "SYF", "STLA", "ALLY", "C", "HEI-A", "AME", "MEDP", "PGR",
    "IBP", "ELV", "OMF", "SLM", "AN", "RYAAY", "MPLX", "BLDR", "FNF", "VFC",
    "YETI", "GXO", "EVH", "CGNX", "FRPT", "PTLO", "BL", "BRCC", "GM", "TOL",
    "PHM", "DHI", "AVTR", "BAX", "LEA", "GPI", "EQH", "RMNI", "SDHC", "AXP",
    "RACE", "MU", "DJCO", "CTRA", "HOLX", "AKAM", "DD", "NUE", "WST", "GSK",
    "HSY", "BMY", "BIIB", "TRMD", "EXE", "GTX", "AU", "VNOM", "TDS", "TLN",
    "STKL", "CORZ", "SYK", "LLY", "ABT", "PGR", "FERG", "BSX", "CRH", "APH",
    "GNRC", "SPHR", "MSGE", "NCLH", "CRL", "LH", "IPG-OLD", "KN", "MAT", "CG",
    "TSLA", "TRUP", "BUR", "BAYRY", "FLG", "OGN", "BP", "MRK", "SEB", "IDT",
    "NU", "UNP", "PM", "NTRA", "COOP-OLD", "VRT", "MP", "MIR", "APO", "FIHL",
    "RRX", "EWBC", "SOC", "TKO", "TMO", "MDLZ", "PEP", "PYPL", "EBAY", "JPM",
    "UNH", "GGG", "TTC", "CNX", "KHC", "IAC", "EXXRF", "ACI", "RYN", "REGN",
    "PENG", "TCBI", "AXS", "EVRG", "BEPC", "NVST", "CACI", "MOH", "LULU",
    "HCC", "AMR", "RIG", "VAL", "NE", "JHG", "SOLV", "IVZ", "WEN", "GEHC",
    "SGOV", "CROX", "DHR", "AER", "AZO", "RPRX", "ENOV", "SHOP", "AVGO",
    "ORLA", "CLF", "BB", "KW", "ATS", "TAP", "VOO", "HUM", "FMS", "WFC", "MGA",
    "DG", "VNT", "ST", "LKQ", "ABM", "OMC", "SLB", "CACC", "WIX", "HTHT",
    "YUMC", "RYCEF", "FWONK", "UMGNF", "CNSWF", "ERFSF", "QXO", "DB", "EFA",
    "SW", "WTW", "WCC", "LBTYK", "LPLA", "ADI", "TEL", "CMCSA", "JDEPY",
    "HKHHF", "PROSF", "ADP", "WAT", "MAR", "TDW", "FPH", "CBRE", "BCC",
    "LEN-B", "PLD", "ROG", "SAFRF", "RHHVF", "TTE", "IONS", "BYNN.F", "NSRGY",
    "UOVEY", "PUKPF", "MSCI", "RBLX", "RKT", "MDB", "LLYVK", "NSIT", "MCD",
    "FTV", "APD", "AON", "TMO", "IEX", "CB", "KO", "BLK", "CNQ", "FOX", "PG",
    "NWSA"
]



RSI_WINDOW = 14
LOOKBACK_DAYS_CALENDAR = 90

# -----------------------------
# Functions
# -----------------------------
def fetch_stock_data(ticker):
    try:
        df = yf.download(ticker, period="1y", interval="1d", progress=False, auto_adjust=False)
        if df.empty: return None
        return df
    except Exception as e:
        print(f"Error fetching {ticker}: {e}")
        return None

def calculate_rsi(prices, window=RSI_WINDOW):
    if isinstance(prices, pd.DataFrame):
        prices = prices.iloc[:, 0]
    prices_series = prices.squeeze().dropna()
    rsi_indicator = RSIIndicator(prices_series, window=window, fillna=True)
    return rsi_indicator.rsi().iloc[-1]

def get_sparkline_metrics(df):
    prices = df["Close"].squeeze().dropna()
    end_price = prices.iloc[-1]
    end_date = prices.index[-1]
    target_start_date = end_date - timedelta(days=LOOKBACK_DAYS_CALENDAR)
    try:
        idx = prices.index.get_indexer([target_start_date], method='pad')[0]
        if idx == -1: idx = 0
        start_price = prices.iloc[idx]
    except:
        start_price = prices.iloc[0]
    color = "RED" if end_price < start_price else "GREEN"
    return float(start_price), float(end_price), color

def calculate_score(rsi, color):
    score = 50
    trend = "DOWN" if color == "RED" else "UP"

    if rsi <= 30: score += 30
    elif rsi <= 35: score += 20
    elif rsi <= 40: score += 10

    if rsi >= 70: score -= 30
    elif rsi >= 65: score -= 20
    elif rsi >= 60: score -= 10

    if trend == "DOWN" and rsi < 40: score += 10
    elif trend == "UP" and rsi > 60: score -= 10

    return max(0, min(100, score))

def generate_signal(score):
    if score >= 80: return "STRONG BUY"
    elif score >= 70: return "BUY"
    elif score <= 20: return "STRONG SELL"
    elif score <= 30: return "SELL"
    else: return "HOLD"

def evaluate_stock(ticker):
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
# Main Execution (Push one by one)
# -----------------------------
if __name__ == "__main__":

    INDEX_GROUPS = {
        "QQQ": QQQ,
        "VIG": VIG,
        "VXUS": VXUS,
        "CAGR": CAGR,
        "GURU": GURU
    }

    # Collect all results first, then consolidate
    all_ticker_data = {}
    
    for index_name, tickers in INDEX_GROUPS.items():
        print(f"\nAnalyzing {index_name} ({len(tickers)} stocks)...\n")

        results = [evaluate_stock(t) for t in tickers]
        df = pd.DataFrame([r for r in results if r is not None])

        if df.empty:
            print(f"No valid data for {index_name}")
            continue

        df["Index"] = index_name
        df_sorted = df.sort_values(by="Score", ascending=False)

        # Print Table
        print("=" * 90)
        print(f"{'Index':<6} {'Ticker':<10} {'Price':<10} {'RSI':<8} {'Trend':<6} {'Score':<8} {'Signal':<15}")
        print("-" * 90)

        for _, row in df_sorted.iterrows():
            print(
                f"{row['Index']:<6} {row['Ticker']:<10} "
                f"{row['Price']:<10.2f} {row['RSI']:<8.1f} "
                f"{row['Trend']:<6} {row['Score']:<8} {row['Signal']:<15}"
            )

        # Index Summary
        print("\n--- SUMMARY ---")
        counts = df['Signal'].value_counts()
        for sig in ["STRONG BUY", "BUY", "HOLD", "SELL", "STRONG SELL"]:
            print(f"{sig:<15}: {counts.get(sig, 0)}")
        print("=" * 90)
        
        # Consolidate ticker data
        for _, row in df.iterrows():
            ticker = row['Ticker']
            if ticker in all_ticker_data:
                # Add index to existing ticker
                existing_indexes = all_ticker_data[ticker]['index_names'].split(',')
                if index_name not in existing_indexes:
                    all_ticker_data[ticker]['index_names'] = ','.join(existing_indexes + [index_name])
                # Always update the timestamp and data
                all_ticker_data[ticker].update({
                    'price': float(row['Price']),
                    'rsi': float(row['RSI']),
                    'trend': row['Trend'],
                    'score': int(row['Score']),
                    'signal': row['Signal'],
                    'updated_at': datetime.now().isoformat()
                })
            else:
                # New ticker
                all_ticker_data[ticker] = {
                    'ticker': ticker,
                    'index_names': index_name,
                    'price': float(row['Price']),
                    'rsi': float(row['RSI']),
                    'trend': row['Trend'],
                    'score': int(row['Score']),
                    'signal': row['Signal'],
                    'updated_at': datetime.now().isoformat()
                }

    # Save consolidated results to Supabase
    if supabase and all_ticker_data:
        print(f"\nSaving {len(all_ticker_data)} consolidated ticker records...")
        for ticker, data in all_ticker_data.items():
            try:
                supabase.table("signals").upsert(data, on_conflict="ticker").execute()
                print(f"[INFO] Upserted {ticker} ({data['index_names']})")
            except Exception as e:
                print(f"[ERROR] Error saving {ticker}: {e}")
    elif all_ticker_data:
        print(f"\n[INFO] Supabase not configured. {len(all_ticker_data)} records not saved.")
