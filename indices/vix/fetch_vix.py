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

class VIXFetcher:
    def __init__(self):
        self.supabase_url = os.getenv("FINANCE_SUPABASE_URL")
        self.supabase_key = os.getenv("FINANCE_SUPABASE_SECRET_KEY") 
        if self.supabase_url and self.supabase_key:
            self.supabase = create_client(self.supabase_url, self.supabase_key)
        else:
            self.supabase = None
        
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })

    def fetch_vix_from_tradingview(self):
        """Fetch VIX data from TradingView"""
        try:
            url = "https://www.tradingview.com/symbols/TVC-VIX/"
            
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            vix_value = None
            timestamp = datetime.now()
            
            # Method 1: Look for price in script tags (TradingView often has JSON data)
            scripts = soup.find_all('script')
            for script in scripts:
                if script.string:
                    # Look for price or last price patterns
                    price_patterns = [
                        r'"last_price"[:\s]*(\d+\.?\d*)',
                        r'"price"[:\s]*(\d+\.?\d*)',
                        r'"last"[:\s]*(\d+\.?\d*)',
                        r'"close"[:\s]*(\d+\.?\d*)',
                        r'VIX[^}]*?(\d+\.?\d+)'
                    ]
                    
                    for pattern in price_patterns:
                        match = re.search(pattern, script.string, re.IGNORECASE)
                        if match:
                            try:
                                value = float(match.group(1))
                                # VIX typically ranges from 10-80+
                                if 5 <= value <= 100:
                                    vix_value = value
                                    break
                            except:
                                continue
                    if vix_value:
                        break
            
            # Method 2: Look for price in specific TradingView class elements
            if not vix_value:
                price_selectors = [
                    'div[data-field="last_price"]',
                    '.js-symbol-last',
                    '.tv-symbol-price-quote__value',
                    '[data-symbol-last]',
                    '.last-price',
                    '.symbol-last-price'
                ]
                
                for selector in price_selectors:
                    elements = soup.select(selector)
                    for element in elements:
                        text = element.get_text().strip()
                        match = re.search(r'(\d+\.?\d*)', text)
                        if match:
                            try:
                                value = float(match.group(1))
                                if 5 <= value <= 100:
                                    vix_value = value
                                    break
                            except:
                                continue
                    if vix_value:
                        break
            
            # Method 3: Look for any large number that could be the VIX price
            if not vix_value:
                # Find all text that contains decimal numbers
                all_text = soup.get_text()
                number_matches = re.findall(r'\b(\d{1,2}\.\d{2})\b', all_text)
                
                for match in number_matches:
                    try:
                        value = float(match)
                        if 5 <= value <= 100:  # Reasonable VIX range
                            vix_value = value
                            break
                    except:
                        continue
            
            return {
                'symbol': 'VIX',
                'value': vix_value,
                'timestamp': timestamp.isoformat(),
                'source': 'TradingView',
                'url': url,
                'status': 'success' if vix_value is not None else 'no_data'
            }
            
        except Exception as e:
            return {
                'symbol': 'VIX',
                'value': None,
                'timestamp': datetime.now().isoformat(),
                'source': 'TradingView',
                'url': url,
                'status': 'error',
                'error': str(e)
            }

    def fetch_vix_from_google(self):
        """Alternative: Fetch VIX from Google Finance"""
        try:
            url = "https://www.google.com/finance/quote/VIX:INDEXCBOE"
            
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            vix_value = None
            timestamp = datetime.now()
            
            # Google Finance typically has the price in a specific div
            price_elements = soup.find_all('div', {'data-last-price': True})
            if price_elements:
                try:
                    vix_value = float(price_elements[0]['data-last-price'])
                except:
                    pass
            
            # Alternative: look for price in text content
            if not vix_value:
                # Look for the main price display
                price_divs = soup.find_all('div', class_=re.compile(r'.*price.*', re.IGNORECASE))
                for div in price_divs:
                    text = div.get_text().strip()
                    match = re.search(r'(\d+\.?\d*)', text)
                    if match:
                        try:
                            value = float(match.group(1))
                            if 5 <= value <= 100:
                                vix_value = value
                                break
                        except:
                            continue
            
            return {
                'symbol': 'VIX',
                'value': vix_value,
                'timestamp': timestamp.isoformat(),
                'source': 'Google Finance',
                'url': url,
                'status': 'success' if vix_value is not None else 'no_data'
            }
            
        except Exception as e:
            return {
                'symbol': 'VIX',
                'value': None,
                'timestamp': datetime.now().isoformat(),
                'source': 'Google Finance',
                'url': url,
                'status': 'error',
                'error': str(e)
            }

    def fetch_vix(self):
        """Try multiple sources for VIX data"""
        # Try TradingView first
        result = self.fetch_vix_from_tradingview()
        
        # If TradingView fails, try Google Finance
        if result['status'] != 'success':
            print("TradingView failed, trying Google Finance...")
            result = self.fetch_vix_from_google()
        
        return result

    def save_to_supabase(self, data):
        """Save VIX data to Supabase"""
        if not self.supabase:
            print("Supabase not configured")
            return False
            
        try:
            result = self.supabase.table("financial_indicators").upsert({
                "indicator_type": "VIX",
                "symbol": data['symbol'],
                "value": data['value'],
                "metadata": {
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

    def save_to_file(self, data, filename="vix_data.json"):
        """Save VIX data to local file"""
        try:
            # Read existing data
            if os.path.exists(filename):
                with open(filename, 'r') as f:
                    existing_data = json.load(f)
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
        print("Fetching VIX data...")
        
        data = self.fetch_vix()
        
        print(f"VIX Value: {data['value']}")
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
    fetcher = VIXFetcher()
    result = fetcher.run()