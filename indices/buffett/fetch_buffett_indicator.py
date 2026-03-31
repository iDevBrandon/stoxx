import requests
import json
from datetime import datetime
import re
from bs4 import BeautifulSoup
import time
import os
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

class BuffettIndicatorFetcher:
    def __init__(self):
        self.supabase_url = os.getenv("SUPABASE_URL")
        self.supabase_key = os.getenv("SUPABASE_KEY") 
        if self.supabase_url and self.supabase_key:
            self.supabase = create_client(self.supabase_url, self.supabase_key)
        else:
            self.supabase = None
        
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })

    def _extract_percentage(self, text):
        """Extract a Buffett Indicator percentage from scraped text."""
        if not text:
            return None

        match = re.search(r'(\d+(?:\.\d+)?)\s*%', text)
        if not match:
            return None

        value = float(match.group(1))
        return value if 30 <= value <= 300 else None

    def _get_valuation_level(self, percentage):
        """Map a Buffett Indicator percentage to a valuation label."""
        if percentage is None:
            return None

        if percentage < 75:
            return "Significantly Undervalued"
        if percentage < 90:
            return "Modestly Undervalued"
        if percentage < 110:
            return "Fair Valued"
        if percentage < 125:
            return "Modestly Overvalued"
        return "Significantly Overvalued"

    def fetch_buffett_indicator(self):
        """Fetch Buffett Indicator from GuruFocus"""
        try:
            url = "https://www.gurufocus.com/stock-market-valuations.php"
            
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            buffett_value = None
            buffett_percentage = None
            market_valuation = None
            timestamp = datetime.now()

            if response.status_code == 403 and "cloudflare" in response.text.lower():
                raise RuntimeError("GuruFocus blocked the request with a Cloudflare challenge")

            # Method 1: Use the exact selector path provided for the ratio cell.
            selector = "#content1 > table:nth-child(11) > tbody > tr:nth-child(7) > td:nth-child(2)"
            target_cell = soup.select_one(selector)
            if target_cell:
                buffett_percentage = self._extract_percentage(target_cell.get_text(" ", strip=True))
                if buffett_percentage is not None:
                    buffett_value = buffett_percentage / 100
                    print(f"Found Buffett Indicator with CSS selector: {buffett_percentage}%")

            # Method 2: Find the row by label and read the adjacent value cell.
            if buffett_value is None:
                for row in soup.find_all("tr"):
                    cells = row.find_all(["th", "td"])
                    if len(cells) < 2:
                        continue

                    row_label = cells[0].get_text(" ", strip=True).lower()
                    if "total market cap" in row_label and "gdp" in row_label:
                        buffett_percentage = self._extract_percentage(cells[1].get_text(" ", strip=True))
                        if buffett_percentage is not None:
                            buffett_value = buffett_percentage / 100
                            print(f"Found Buffett Indicator from row label: {buffett_percentage}%")
                            break

            # Method 3: Look for Buffett/GDP text and a nearby percentage in a table cell.
            if buffett_value is None:
                for cell in soup.find_all(["td", "th"]):
                    text = cell.get_text(" ", strip=True)
                    context = text.lower()
                    if "buffett" in context or ("market cap" in context and "gdp" in context):
                        buffett_percentage = self._extract_percentage(text)
                        if buffett_percentage is None and cell.find_next_sibling("td"):
                            sibling_text = cell.find_next_sibling("td").get_text(" ", strip=True)
                            buffett_percentage = self._extract_percentage(sibling_text)

                        if buffett_percentage is not None:
                            buffett_value = buffett_percentage / 100
                            print(f"Found Buffett Indicator from contextual cell: {buffett_percentage}%")
                            break

            market_valuation = self._get_valuation_level(buffett_percentage)
            
            return {
                'indicator_value': buffett_value,
                'percentage': buffett_percentage,
                'valuation_level': market_valuation,
                'timestamp': timestamp.isoformat(),
                'source': 'GuruFocus',
                'url': url,
                'status': 'success' if buffett_value is not None else 'no_data',
                'error': None if buffett_value is not None else 'No Buffett Indicator value found'
            }
            
        except Exception as e:
            return {
                'indicator_value': None,
                'percentage': None,
                'valuation_level': None,
                'timestamp': datetime.now().isoformat(),
                'source': 'GuruFocus',
                'url': url,
                'status': 'error',
                'error': str(e)
            }

    def fetch_buffett_indicator_alt(self):
        """Alternative method: Try to fetch from a different source or API"""
        try:
            # Alternative approach: look for market cap to GDP data from other sources
            # This is a placeholder for additional sources
            url = "https://www.currentmarketvaluation.com/models/buffett-indicator.php"
            
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            buffett_value = None
            timestamp = datetime.now()
            
            # Look for percentage indicators
            percentage_elements = soup.find_all(text=re.compile(r'\d+\.?\d*%'))
            for element in percentage_elements:
                match = re.search(r'(\d+\.?\d*)%', element)
                if match:
                    try:
                        value = float(match.group(1))
                        if 30 <= value <= 300:
                            buffett_value = value / 100
                            break
                    except:
                        continue
            
            return {
                'indicator_value': buffett_value,
                'percentage': buffett_value * 100 if buffett_value else None,
                'valuation_level': None,
                'timestamp': timestamp.isoformat(),
                'source': 'CurrentMarketValuation',
                'url': url,
                'status': 'success' if buffett_value is not None else 'no_data'
            }
            
        except Exception as e:
            return {
                'indicator_value': None,
                'percentage': None,
                'valuation_level': None,
                'timestamp': datetime.now().isoformat(),
                'source': 'CurrentMarketValuation',
                'url': url,
                'status': 'error',
                'error': str(e)
            }

    def save_to_supabase(self, data):
        """Save Buffett Indicator data to Supabase"""
        if not self.supabase:
            print("Supabase not configured")
            return False
            
        try:
            result = self.supabase.table("indicators").upsert({
                "indicator_type": "BUFFETT_INDICATOR",
                "symbol": "US_MARKET",
                "value": data['indicator_value'],
                "metadata": {
                    "percentage": data['percentage'],
                    "valuation_level": data['valuation_level'],
                    "source": data['source'],
                    "url": data['url'],
                    "status": data['status']
                },
                "timestamp": data['timestamp']
            }, on_conflict="indicator_type,symbol,timestamp").execute()
            
            return True
        except Exception as e:
            print(f"Error saving to Supabase: {e}")
            return False

    def save_to_file(self, data, filename=None):
        """Save Buffett Indicator data to local file"""
        try:
            if filename is None:
                filename = os.path.join(
                    os.path.dirname(os.path.dirname(__file__)),
                    "buffett_indicator_data.json",
                )

            # Read existing data
            if os.path.exists(filename):
                try:
                    with open(filename, 'r') as f:
                        existing_data = json.load(f)
                except (json.JSONDecodeError, ValueError):
                    existing_data = []
            else:
                existing_data = []
            
            # Append new data
            existing_data.append(data)
            
            # Keep only last 1000 records
            existing_data = existing_data[-1000:]
            
            # Save back to file
            with open(filename, 'w') as f:
                json.dump(existing_data, f, indent=2, default=str)
            
            return True
        except Exception as e:
            print(f"Error saving to file: {e}")
            return False

    def run(self):
        """Main execution function"""
        print("Fetching Buffett Indicator from GuruFocus...")
        
        # Try primary source first
        data = self.fetch_buffett_indicator()
        
        # If primary source fails, try alternative
        if data['status'] != 'success':
            print("Primary source failed, trying alternative...")
            data = self.fetch_buffett_indicator_alt()
        
        print(f"Buffett Indicator: {data['indicator_value']}")
        print(f"Percentage: {data['percentage']}%")
        print(f"Valuation Level: {data['valuation_level']}")
        print(f"Source: {data['source']}")
        print(f"Status: {data['status']}")
        print(f"Timestamp: {data['timestamp']}")
        
        # Save to both Supabase and local file
        saved_to_db = self.save_to_supabase(data)
        saved_to_file = self.save_to_file(data)
        
        if saved_to_db:
            print("✅ Data saved to Supabase")
        if saved_to_file:
            print("✅ Data saved to local file")
        
        return data

if __name__ == "__main__":
    fetcher = BuffettIndicatorFetcher()
    result = fetcher.run()
