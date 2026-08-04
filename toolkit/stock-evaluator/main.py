import os
import requests
from bs4 import BeautifulSoup
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
FINANCE_SUPABASE_URL = os.getenv("FINANCE_SUPABASE_URL")
FINANCE_SUPABASE_SECRET_KEY = os.getenv("FINANCE_SUPABASE_SECRET_KEY")
supabase = None

if FINANCE_SUPABASE_URL and FINANCE_SUPABASE_SECRET_KEY:
    supabase = create_client(FINANCE_SUPABASE_URL, FINANCE_SUPABASE_SECRET_KEY)
    print("[INFO] Supabase client initialized")
else:
    print("[INFO] Supabase not configured, running in local mode")

# -----------------------------
# Configuration
# -----------------------------

def fetch_ioo_tickers():
    """Fetch the top 100 global companies from companiesmarketcap.com (first page)."""
    try:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }
        r = requests.get("https://companiesmarketcap.com/", headers=headers, timeout=15)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        tickers = []
        # Tickers live in: <div class="company-code"><span class="rank d-none"></span>2222.SR</div>
        for div in soup.select("div.company-code"):
            # Remove the rank span, then grab remaining text
            for span in div.select("span.rank"):
                span.decompose()
            ticker = div.get_text(strip=True)
            if ticker and ticker not in tickers:
                tickers.append(ticker)
        print(f"[INFO] Fetched {len(tickers)} IOO tickers from companiesmarketcap.com")
        return tickers
    except Exception as e:
        print(f"[WARN] Could not fetch IOO tickers: {e}")
        return []

# NOTE: IOO's ticker list is fetched lazily inside __main__ (only when
# "IOO" is actually enabled there), not at import time — a bare
# `IOO = fetch_ioo_tickers()` here used to scrape companiesmarketcap.com
# live as a side effect of just importing this module, even if the caller
# never wanted IOO for that run.

OXNO = ["INTU", "MSCI" , "CTAS", "NVO",  "HESAY", "LMP.L" ,"ZTS", "V", "KLAC", "APH", "PH","FIX", "DPZ", "QQQM"]


QQQ = [
  "NVDA", "AAPL",
  "MSFT",
  "AMZN",
  "GOOGL",
  "GOOG",
  "AVGO",
  "SPCX",
  "META",
  "TSLA",
  "MU",
  "WMT",
  "AMD",
  "ASML",
  "INTC",
  "AMAT",
  "CSCO",
  "LRCX",
  "COST",
  "PLTR",
  "NFLX",
  "KLAC",
  "ARM",
  "PANW",
  "TXN",
  "SNDK",
  "LIN",
  "CRWD",
  "TMUS",
  "MRVL",
  "STX",
  "WDC",
  "AMGN",
  "ADI",
  "QCOM",
  "PEP",
  "SHOP",
  "GILD",
  "APP",
  "BKNG",
  "ISRG",
  "FTNT",
  "VRTX",
  "SBUX",
  "PDD",
  "CDNS",
  "ADP",
  "DDOG",
  "MNST",
  "MAR",
  "MELI",
  "CEG",
  "CSX",
  "ADBE",
  "ABNB",
  "CMCSA",
  "DASH",
  "SNPS",
  "INTU",
  "MDLZ",
  "CTAS",
  "AEP",
  "NXPI",
  "ORLY",
  "HON",
  "ROST",
  "REGN",
  "WBD",
  "MPWR",
  "HONA",
  "PCAR",
  "LITE",
  "ALAB",
  "BKR",
  "TER",
  "FANG",
  "FAST",
  "EA",
  "XEL",
  "NBIS",
  "RKLB",
  "EXC",
  "ODFL",
  "MCHP",
  "CCEP",
  "FER",
  "AXON",
  "TTWO",
  "CRWV",
  "ADSK",
  "IDXX",
  "PYPL",
  "KDP",
  "TRI",
  "PAYX",
  "ALNY",
  "ROP",
  "MSTR",
  "WDAY",
  "KHC",
  "DXCM",
  "GEHC",
  "CPRT",
];


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

VOO = [
  "NVDA","AAPL","MSFT","AMZN","GOOGL","GOOG","AVGO","META","TSLA","MU",
  "BRK-B","LLY","JPM","WMT","AMD","V","JNJ","XOM","INTC","MA",
  "AMAT","CSCO","LRCX","ABBV","BAC","CAT","COST","UNH","ORCL","GE",
  "CVX","MS","KO","PG","HD","GS","PLTR","NFLX","KLAC","MRK",
  "DELL","PANW","GEV","TXN","PM","RTX","WFC","SNDK","AXP","LIN",
  "ANET","C","CRWD","IBM","TMUS","MRVL","STX","TMO","APH","WDC",
  "AMGN","ADI","MCD","QCOM","NEE","PEP","VZ","SCHW","UNP","BA",
  "WELL","DIS","TJX","GILD","ETN","GLW","BLK","DE","ABT","BX",
  "APP","T","UBER","DHR","PFE","CRM","COP","BKNG","CVS","ISRG",
  "CB","PGR","PLD","SPGI","COF","FTNT","PH","VRTX","SBUX","SYK",
  "LMT","MO","LOW","VRT","BMY","HWM","SO","NOW","TT","BNY",
  "CDNS","HOOD","MDT","NEM","PWR","EQIX","PNC","GD","DUK","ADP",
  "USB","DDOG","UPS","MNST","MAR","WM","WMB","ELV","MCK","CMI",
  "CEG","CSX","VLO","FCX","CME","MPC","JCI","ADBE","KKR","ABNB",
  "MCO","MRSH","CMCSA","ACN","DASH","MMM","SNPS","SHW","PSX","HCA",
  "CI","AMT","ITW","ICE","INTU","ECL","AON","EMR","RCL","NOC",
  "MDLZ","FDX","CTAS","HLT","CL","AEP","NSC","NXPI","KMI","EOG",
  "TRV","SLB","SPG","ORLY","HON","ROST","CRH","GM","APO","REGN",
  "WBD","MSI","TDG","MPWR","RSG","APD","URI","HONA","HPE","AJG",
  "PCAR","GWW","TFC","ALL","DLR","BSX","NKE","LITE","CIEN","D",
  "FIX","AFL","TGT","SRE","COHR","TRGP","MET","O","COR","TEL",
  "CARR","OKE","BKR","CTVA","PSA","DAL","F","TER","LHX","KEYS",
  "OXY","VST","CAH","ETR","NUE","AME","FANG","FAST","ROK","FITB",
  "EA","EW","STT","CVNA","XEL","DVN","EBAY","NDAQ","AZO","HUM",
  "EXC","FLEX","XYZ","ODFL","MCHP","CMG","GRMN","AMP","VTR","AXON",
  "MSCI","WAB","TTWO","ADSK","YUM","DHI","IBKR","IDXX","COIN","LYV",
  "BDX","AIG","PYPL","KDP","ED","PEG","PRU","ADM","SYY","UAL",
  "CBRE","PAYX","PCG","A","HIG","VMC","WEC","WAT","ON","CCL",
  "HBAN","KVUE","IRM","KR","MTB","KMB","ACGL","ROP","HSY","NTRS",
  "IQV","MLM","EME","NTAP","CCI","WDAY","JBL","CNC","STLD","RJF",
  "EXPE","CASY","VEEV","AEE","EQT","DTE","ZTS","IR","EXR","Q",
  "NRG","ATO","KHC","LVS","CFG","EL","HAL","EIX","VICI","TDY",
  "DOV","TPL","CNP","XYL","CBOE","FE","DXCM","RMD","BIIB","GEHC",
  "FICO","ES","OTIS","CINF","TPR","WTW","AVB","ARES","PPL","MRNA",
  "WRB","DG","MTD","FISV","JBHT","RF","WSM","EQR","AWK","CPRT",
  "PPG","HUBB","WST","KEY","VRSK","TROW","SYF","VRSN","PFG","FFIV",
  "DLTR","PHM","FSLR","L","CHRW","CPAY","EXPD","BRO","LUV","CMS",
  "OMC","INCY","DGX","CHD","BG","LH","VLTO","HPQ","SW","STZ",
  "DRI","NI","RL","DOW","FDXF","ROL","FIS","SNA","EXE","CTSH",
  "GPN","STE","TSN","LEN","PKG","ULTA","EVRG","SBAC","AMCR","EFX",
  "LNT","LII","GIS","IP","ESS","IFF","VTRS","LYB","FTV","AKAM",
  "CF","DD","INVH","SMCI","CDW","BBY","ZBH","NVR","BEN","WY",
  "KIM","BR","GPC","IEX","NDSN","BALL","HST","GEN","TSCO","MAS",
  "CHTR","MAA","TXT","J","ALB","DOC","DECK","EG","REG","DVA",
  "MKC","PTC","GL","TKO","AIZ","SWK","HRL","LDOS","COO","LULU",
  "PNW","GNRC","SOLV","UDR","ALGN","IVZ","ERIE","TYL","RVTY","ZBRA",
  "APTV","APA","PNR","GDDY","TRMB","AVY","MGM","ALLE","SJM","BF-B",
  "CLX","CSGP","BAX","HAS","CPT","TECH","CRL","HII","PODD","FOXA",
  "BXP","FOX","FRT","AES","JKHY","DPZ","PSKY","NWSA","WYNN","HSIC",
  "FDS","NCLH","IT","TTD","UHS","SWKS","AOS","ARE","BLDR","TAP",
  "MOS","NWS","SATS"
];


VXUS = [
    'TSM', 'TCEHY', 'ASML', 'BABA', "AZN","RHHBY", "NSRGY", "SAP", "HSBC",
    "NVS", "RY","SHEL", "TM", "SIEGY", "SHOP", "LVMUY", "SONY", "MUFG", "CMWAY", "ALIZY","SAN", "NVO", "SBGSY", "UL", "TD", "IBDRY", "HTHIY", "EADSY", "HDB", "UBS","BBVA", "TTE", "RYCEY", "BTI", "SAFRY", "UNCRY", "ABBNY", "CFRUY", "SMFG","AAIGF", "SNY", "ENB", "DTEGY", "SFTBY", "ESLOY",  "BN", "MSBHF","RELX", "TKOMF", "BAESY", "INFY", "LDNXF", "CNI", "DEO", "DBOEY",'RACE', 'HESAY', "FJTSY", "WCN", "DSDVY", "ATD.TO", "FNV", "DOL.TO", "ASAZY", "IFC.TO", "GVDNY", "UCBJY", "SVNDY", "TTDKY", "SXYAY", "SDZNY", "NTTYY", "SMPNY", "AHT.L",  
]


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

ALT = [
  "USDU","FXE","FXF","FXY","FXB","FXC","FXA",    
  "VXX",                                         
  "PDBC","GLD",                                  
  "BITO",                                        
  "REET","IGF"                                  
]



RSI_WINDOW = 14
LOOKBACK_DAYS_CALENDAR = 90

# Rows not touched by any run in this many days are considered stale and get
# pruned after a successful save (see prune_stale_signals below). This is
# time-based rather than "delete anything not in this run's ticker list" on
# purpose: if a single run has a transient failure (e.g. the IOO scrape
# comes back empty, or yfinance rate-limits a batch of tickers), a
# time-based cutoff won't wipe out otherwise-valid rows over one bad run —
# only tickers that have gone untouched across many runs (e.g. an index
# group that got disabled in ENABLED_INDEXES) get removed.
STALE_DAYS = 7

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
    chg90d = round((end_p / start_p - 1.0) * 100.0, 1) if start_p else 0.0
    score = calculate_score(rsi, color)
    signal = generate_signal(score)

    return {
        "Ticker": ticker,
        "Price": round(end_p, 2),
        "RSI": round(rsi, 1),
        "Trend": "DOWN" if color == "RED" else "UP",
        "Color": color,
        "Chg90d": chg90d,
        "Score": score,
        "Signal": signal
    }

def prune_stale_signals(days=STALE_DAYS):
    """Deletes signals rows whose updated_at is older than `days`. Runs
    after a successful save so a ticker that's dropped out of every
    currently-enabled index group (e.g. VIG/GURU/etc. after they were
    disabled in ENABLED_INDEXES) eventually gets cleaned out instead of
    sitting in the table forever with a frozen updated_at."""
    if not supabase:
        return
    cutoff = (datetime.now() - timedelta(days=days)).isoformat()
    try:
        res = (
            supabase.table("signals")
            .delete()
            .lt("updated_at", cutoff)
            .execute()
        )
        removed = len(res.data) if res.data else 0
        if removed:
            print(f"[INFO] Pruned {removed} stale signal(s) untouched for {days}+ days")
    except Exception as e:
        print(f"[ERROR] Pruning stale signals failed: {e}")

# -----------------------------
# Main Execution
# -----------------------------
if __name__ == "__main__":

    # Toggle which indexes this run covers. IOO does a live scrape of
    # companiesmarketcap.com, so it's only fetched below if it's actually
    # in this list — no more unconditional scraping at import time.
    ENABLED_INDEXES = ["IOO", "QQQ", "VOO", "OXNO"]
    # ENABLED_INDEXES += ["VIG", "VXUS", "GURU", "OXNO", "ALT"]  # wider coverage

    STATIC_INDEX_TICKERS = {
        "QQQ": QQQ,
        "VOO": VOO,
        "VIG": VIG,
        "VXUS": VXUS,
        "GURU": GURU,
        "OXNO": OXNO,
        "ALT": ALT,
    }

    INDEX_GROUPS = {}
    for name in ENABLED_INDEXES:
        if name == "IOO":
            INDEX_GROUPS["IOO"] = fetch_ioo_tickers()
        elif name in STATIC_INDEX_TICKERS:
            INDEX_GROUPS[name] = STATIC_INDEX_TICKERS[name]

    # Map each ticker to every index group it belongs to. QQQ and VOO share
    # a large overlap (AAPL, MSFT, NVDA, ...), so without this a shared
    # ticker would get fetched from yfinance once per index it appears in.
    # Evaluating each unique ticker exactly once keeps this run to
    # len(unique tickers) network calls instead of sum(len(group) for
    # group in INDEX_GROUPS.values()).
    ticker_to_indexes: dict[str, list[str]] = {}
    for index_name, tickers in INDEX_GROUPS.items():
        for t in tickers:
            ticker_to_indexes.setdefault(t, [])
            if index_name not in ticker_to_indexes[t]:
                ticker_to_indexes[t].append(index_name)

    unique_tickers = list(ticker_to_indexes.keys())
    print(
        f"\nEvaluating {len(unique_tickers)} unique tickers across "
        f"{len(INDEX_GROUPS)} index(es): {', '.join(INDEX_GROUPS.keys())}\n"
    )

    evaluated: dict[str, dict] = {}
    for t in unique_tickers:
        result = evaluate_stock(t)
        if result is not None:
            evaluated[t] = result

    # Per-index console output, sourced from the de-duplicated evaluation
    # pass above instead of re-fetching each ticker per group.
    for index_name, tickers in INDEX_GROUPS.items():
        rows = [evaluated[t] for t in tickers if t in evaluated]
        if not rows:
            print(f"No valid data for {index_name}")
            continue

        df = pd.DataFrame(rows)
        df["Index"] = index_name
        df_sorted = df.sort_values(by="Score", ascending=False)

        print(f"\n{index_name} ({len(tickers)} stocks, {len(rows)} resolved)")
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

    # Consolidate one row per unique ticker (comma-joined index_names) —
    # matches the live `signals` table's actual constraint, `unique(ticker)`
    # (confirmed against the real Supabase schema; the README's older
    # `unique(index_name, ticker)` example is stale and doesn't match what's
    # deployed).
    all_ticker_data = {
        ticker: {
            'ticker': ticker,
            'index_names': ','.join(ticker_to_indexes[ticker]),
            'price': float(result['Price']),
            'rsi': float(result['RSI']),
            'trend': result['Trend'],
            'chg90d': float(result['Chg90d']),
            'score': int(result['Score']),
            'signal': result['Signal'],
            'updated_at': datetime.now().isoformat(),
        }
        for ticker, result in evaluated.items()
    }

    # Save consolidated results to Supabase in a single batched upsert
    # instead of one HTTP round trip per ticker (previously 800+ separate
    # requests for IOO alone, and would have been 1000+ with QQQ/VOO added).
    # Still logs one line per ticker like before — that's just printing
    # from the local `rows_to_save` list, not a separate network call per
    # line, so the batching win is unaffected.
    if supabase and all_ticker_data:
        rows_to_save = list(all_ticker_data.values())
        print(f"\nSaving {len(rows_to_save)} consolidated ticker records...")
        try:
            supabase.table("signals").upsert(rows_to_save, on_conflict="ticker").execute()
            for row in rows_to_save:
                print(f"[INFO] Upserted {row['ticker']} ({row['index_names']})")
            print(f"[INFO] Upserted {len(rows_to_save)} tickers total")
        except Exception as e:
            print(f"[ERROR] Batch upsert failed: {e}")
    elif all_ticker_data:
        print(f"\n[INFO] Supabase not configured. {len(all_ticker_data)} records not saved.")

    # Clean out rows nothing has touched in a while (e.g. leftover GURU/VIG
    # data from before ENABLED_INDEXES was narrowed to IOO/QQQ/VOO) so the
    # table only reflects indexes this script actually keeps refreshed.
    prune_stale_signals()
