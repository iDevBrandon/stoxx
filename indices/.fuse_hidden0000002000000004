#!/usr/bin/env python3

import os
import sys
import json
import argparse
from datetime import datetime
from supabase import create_client, Client

class IndicatorsInserter:
    def __init__(self):
        self.supabase_url = os.environ.get("SUPABASE_URL")
        self.supabase_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_KEY")
        
        if not self.supabase_url or not self.supabase_key:
            raise ValueError("Missing Supabase credentials (SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)")
            
        self.supabase: Client = create_client(self.supabase_url, self.supabase_key)
    
    def load_summary(self, summary_path):
        """Load the indicators summary from JSON file"""
        if not os.path.exists(summary_path):
            raise FileNotFoundError(f"Summary file not found: {summary_path}")
            
        with open(summary_path, "r") as f:
            return json.load(f)
    
    def extract_indicator_values(self, summary):
        """Extract indicator values from the summary data"""
        results = summary.get("results", {})
        
        # Extract data with safe fallbacks
        bi = self._safe_extract(results, 'buffett_indicator', 'indicator_value')
        dxy = self._safe_extract(results, 'dxy', 'value')
        fg = self._safe_extract(results, 'fear_greed', 'index_value')
        rsi = self._safe_extract(results, 'rsi', 'rsi')
        vix = self._safe_extract(results, 'vix', 'value')
        
        return {
            "biMultiplier": float(bi or 0.0),
            "dxyMultiplier": float(dxy or 0.0),
            "fgMultiplier": float(fg or 0.0),
            "rsiMultiplier": float(rsi or 0.0),
            "vixMultiplier": float(vix or 0.0),
        }
    
    def _safe_extract(self, results, indicator_name, value_key):
        """Safely extract indicator value with fallbacks"""
        try:
            indicator = results.get(indicator_name, {})
            if indicator.get('status') == 'success':
                return indicator.get('data', {}).get(value_key)
            return None
        except Exception:
            return None
    
    def insert_indicators(self, payload):
        """Insert indicators data into Supabase"""
        try:
            response = self.supabase.table("indicators").insert(payload).execute()
            return True, response.data
        except Exception as e:
            return False, str(e)
    
    def print_summary(self, summary, payload, success, error=None):
        """Print a summary of the insertion operation"""
        print("\n" + "="*50)
        print("📊 INDICATORS DATABASE INSERTION SUMMARY")
        print("="*50)
        
        print(f"📅 Fetch Timestamp: {summary.get('fetch_timestamp', 'Unknown')}")
        print(f"📊 Total Indicators: {summary.get('total_indicators', 0)}")
        print(f"✅ Successful Fetches: {summary.get('successful', 0)}")
        print(f"❌ Failed Fetches: {summary.get('failed', 0)}")
        
        print("\n📝 Payload to Insert:")
        for key, value in payload.items():
            print(f"   {key}: {value}")
        
        print("\n📤 Database Insertion:")
        if success:
            print("✅ Successfully inserted into public.indicators")
        else:
            print(f"❌ Failed to insert: {error}")
        
        print("="*50)

def main():
    parser = argparse.ArgumentParser(description='Insert indicators data into Supabase')
    parser.add_argument('--input', '-i', default='fetch_summary.json',
                       help='Input JSON file with indicators data (default: fetch_summary.json)')
    parser.add_argument('--quiet', '-q', action='store_true',
                       help='Suppress detailed output')
    
    args = parser.parse_args()
    
    try:
        inserter = IndicatorsInserter()
        
        print(f"🔄 Loading indicators data from {args.input}...")
        summary = inserter.load_summary(args.input)
        
        print("📊 Extracting indicator values...")
        payload = inserter.extract_indicator_values(summary)
        
        print("💾 Inserting data into Supabase...")
        success, result = inserter.insert_indicators(payload)
        
        if not args.quiet:
            inserter.print_summary(summary, payload, success, result if not success else None)
        elif success:
            print("✅ Successfully inserted indicators into database")
        else:
            print(f"❌ Failed to insert indicators: {result}")
        
        # Exit with appropriate code
        sys.exit(0 if success else 1)
        
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()