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

class DXYFetcher:
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

    def fetch_dxy_from_tradingview(self):
        """Fetch DXY (Dollar Index) data from TradingView"""
        try:
            url = "https://www.tradingview.com/symbols/TVC-DXY/"
            
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            dxy_value = None
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
                        r'DXY[^}]*?(\d+\.?\d+)'
                    ]
                    
                    for pattern in price_patterns:
                        match = re.search(pattern, script.string, re.IGNORECASE)
                        if match:
                            try:
                                value = float(match.group(1))
                                # DXY typically ranges from 80-120
                                if 70 <= value <= 150:
                                    dxy_value = value
                                    break
                            except:
                                continue
                    if dxy_value:
                        break
            
            # Method 2: Look for price in specific TradingView class elements
            if not dxy_value:
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
                                if 70 <= value <= 150:
                                    dxy_value = value
                                    break
                            except:
                                continue
                    if dxy_value:
                        break
            
            # Method 3: Look for any number that could be the DXY price
            if not dxy_value:
                # Find all text that contains decimal numbers
                all_text = soup.get_text()
                number_matches = re.findall(r'\b(\d{2,3}\.\d{2,4})\b', all_text)
                
                for match in number_matches:
                    try:
                        value = float(match)
                        if 70 <= value <= 150:  # Reasonable DXY range
                            dxy_value = value
                            break
                    except:
                        continue
            
            return {
                'symbol': 'DXY',
                'value': dxy_value,
                'timestamp': timestamp.isoformat(),
                'source': 'TradingView',
                'url': url,
                'status': 'success' if dxy_value is not None else 'no_data'
            }
            
        except Exception as e:
            return {
                'symbol': 'DXY',
                'value': None,
                'timestamp': datetime.now().isoformat(),
                'source': 'TradingView',
                'url': url,
                'status': 'error',
                'error': str(e)
            }

    def fetch_dxy_from_investing(self):
        """Alternative: Fetch DXY from Investing.com"""
        try:
            url = "https://www.investing.com/indices/usdollar"
            
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            dxy_value = None
            timestamp = datetime.now()
            
            # Look for price in common Investing.com selectors
            price_selectors = [
                '[data-test="instrument-price-last"]',
                '.text-2xl',
                '.instrument-price_last__JQN7_',
                '#last_last',
                '.pid-8827-last'
            ]
            
            for selector in price_selectors:
                elements = soup.select(selector)
                for element in elements:
                    text = element.get_text().strip()
                    # Remove commas and extract number
                    text = text.replace(',', '')
                    match = re.search(r'(\d{2,3}\.\d{2,4})', text)
                    if match:
                        try:
                            value = float(match.group(1))
                            if 70 <= value <= 150:
                                dxy_value = value
                                break
                        except:
                            continue
                if dxy_value:
                    break
            
            return {
                'symbol': 'DXY',
                'value': dxy_value,
                'timestamp': timestamp.isoformat(),
                'source': 'Investing.com',
                'url': url,
                'status': 'success' if dxy_value is not None else 'no_data'
            }
            
        except Exception as e:
            return {
                'symbol': 'DXY',
                'value': None,
                'timestamp': datetime.now().isoformat(),
                'source': 'Investing.com',
                'url': url,
                'status': 'error',
                'error': str(e)
            }

    def fetch_dxy_from_yahoo(self):
        """Alternative: Fetch DXY from Yahoo Finance"""
        try:
            url = "https://finance.yahoo.com/quote/DX-Y.NYB"
            
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            dxy_value = None
            timestamp = datetime.now()
            
            # Yahoo Finance price selectors
            price_selectors = [
                '[data-field="regularMarketPrice"]',
                '.Fw\\(b\\).Fz\\(36px\\)',
                '.Trsdu\\(0\\.3s\\)',
                '[data-symbol="DX-Y.NYB"][data-field="regularMarketPrice"]'
            ]
            
            for selector in price_selectors:
                try:
                    elements = soup.select(selector)
                    for element in elements:
                        text = element.get_text().strip()
                        match = re.search(r'(\d{2,3}\.\d{2,4})', text)
                        if match:
                            value = float(match.group(1))
                            if 70 <= value <= 150:
                                dxy_value = value
                                break
                    if dxy_value:
                        break
                except:
                    continue
            
            return {
                'symbol': 'DXY',
                'value': dxy_value,
                'timestamp': timestamp.isoformat(),
                'source': 'Yahoo Finance',
                'url': url,
                'status': 'success' if dxy_value is not None else 'no_data'
            }
            
        except Exception as e:
            return {
                'symbol': 'DXY',
                'value': None,
                'timestamp': datetime.now().isoformat(),
                'source': 'Yahoo Finance',
                'url': url,
                'status': 'error',
                'error': str(e)
            }

    def fetch_dxy(self):
        """Try multiple sources for DXY data"""
        sources = [
            self.fetch_dxy_from_tradingview,
            self.fetch_dxy_from_yahoo,
            self.fetch_dxy_from_investing
        ]
        
        for source_func in sources:
            try:
                result = source_func()
                if result['status'] == 'success':
                    return result
                else:
                    print(f"{result['source']} failed, trying next source...")
            except Exception as e:
                print(f"Source failed with error: {e}")
                continue
        
        # If all sources fail, return the last result
        return result

    def save_to_supabase(self, data):
        """Save DXY data to Supabase"""
        if not self.supabase:
            print("Supabase not configured")
            return False
            
        try:
            result = self.supabase.table("indicators").upsert({
                "indicator_type": "DXY",
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

    def save_to_file(self, data, filename="dxy_data.json"):
        """Save DXY data to local file"""
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
        print("Fetching DXY (Dollar Index) data...")
        
        data = self.fetch_dxy()
        
        print(f"DXY Value: {data['value']}")
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
    fetcher = DXYFetcher()
    result = fetcher.run()