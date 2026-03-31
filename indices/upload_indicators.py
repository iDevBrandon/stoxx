import os
import json
from supabase import create_client, Client

def main():
    supabase_url = os.environ.get("SUPABASE_URL")
    supabase_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_KEY")
    
    if not supabase_url or not supabase_key:
        print("Error: Missing Supabase credentials (SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)")
        return
        
    supabase: Client = create_client(supabase_url, supabase_key)
    
    summary_path = "fetch_summary.json"
    if not os.path.exists(summary_path):
        print(f"Error: {summary_path} not found. Run fetch_all_indicators.py first.")
        return
        
    with open(summary_path, "r") as f:
        summary = json.load(f)
        
    results = summary.get("results", {})
    
    # Extract data securely
    bi = results.get('buffett_indicator', {}).get('data', {}).get('indicator_value', 0.0)
    dxy = results.get('dxy', {}).get('data', {}).get('value', 0.0)
    fg = results.get('fear_greed', {}).get('data', {}).get('index_value', 0.0)
    rsi = results.get('rsi', {}).get('data', {}).get('rsi', 0.0)
    vix = results.get('vix', {}).get('data', {}).get('value', 0.0)
    
    payload = {
        "biMultiplier": float(bi or 0.0),
        "dxyMultiplier": float(dxy or 0.0),
        "fgMultiplier": float(fg or 0.0),
        "rsiMultiplier": float(rsi or 0.0),
        "vixMultiplier": float(vix or 0.0),
    }

    try:
        response = supabase.table("indicators").insert(payload).execute()
        print(f"✅ Successfully inserted into public.indicators: {payload}")
    except Exception as e:
        print(f"❌ Failed to insert into Supabase: {e}")

if __name__ == "__main__":
    main()
