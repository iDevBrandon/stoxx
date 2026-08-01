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

class FearGreedFetcher:
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
        self.graphdata_headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Referer': 'https://edition.cnn.com/markets/fear-and-greed',
            'Origin': 'https://edition.cnn.com',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-site',
            'sec-ch-ua': '"Google Chrome";v="135", "Chromium";v="135", "Not.A/Brand";v="24"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"macOS"',
        }

    def _extract_index_value(self, text):
        """Extract a valid fear & greed score from scraped text."""
        if not text:
            return None

        match = re.search(r'\b(100|\d{1,2})\b', text.strip())
        if not match:
            return None

        value = int(match.group(1))
        return value if 0 <= value <= 100 else None

    def fetch_fear_greed_index(self):
        """Fetch Fear & Greed Index from CNN (like the working crawler)"""
        try:
            url = "https://edition.cnn.com/markets/fear-and-greed"
            graphdata_url = "https://production.dataviz.cnn.io/index/fearandgreed/graphdata"
            
            fear_greed_value = None
            fear_greed_label = None
            timestamp = datetime.now()

            # Method 1: Use CNN's live graphdata endpoint.
            try:
                graphdata_response = self.session.get(
                    graphdata_url,
                    headers=self.graphdata_headers,
                    timeout=30,
                )
                graphdata_response.raise_for_status()
                graphdata = graphdata_response.json()
                score = graphdata.get('fear_and_greed', {}).get('score')

                if score is not None:
                    fear_greed_value = round(float(score))
                    print(f"Found fear & greed value from graphdata endpoint: {fear_greed_value}")
            except Exception as e:
                print(f"Graphdata endpoint failed: {e}")

            response = None
            soup = None
            if fear_greed_value is None:
                response = self.session.get(url, timeout=30)
                response.raise_for_status()
                soup = BeautifulSoup(response.content, 'html.parser')
            
            # Method 2: Use the exact CSS selector path you provided
            css_selector = "body > div.layout__content-wrapper.layout-with-rail__content-wrapper > section.layout__wrapper.layout-with-rail__wrapper > section.layout__main-wrapper.layout-with-rail__main-wrapper > section.layout__main.layout-with-rail__main > div > section > div.market-tabbed-container > div.market-tabbed-container__content > div.market-tabbed-container__tab.market-tabbed-container__tab--1 > div > div.market-fng-gauge__overview > div.market-fng-gauge__meter-container > div > div.market-fng-gauge__dial-number > span"
            
            if soup is not None:
                try:
                    fng_element = soup.select_one(css_selector)
                    if fng_element:
                        text = fng_element.get_text().strip()
                        fear_greed_value = self._extract_index_value(text)
                        if fear_greed_value is not None:
                            print(f"Found fear & greed value with CSS selector: {fear_greed_value}")
                except Exception as e:
                    print(f"CSS selector failed: {e}")
            
            # Method 3: Look for span inside market-fng-gauge__dial-number
            if fear_greed_value is None and soup is not None:
                dial_number_div = soup.find('div', class_='market-fng-gauge__dial-number')
                if dial_number_div:
                    span_element = dial_number_div.find('span')
                    if span_element:
                        text = span_element.get_text().strip()
                        fear_greed_value = self._extract_index_value(text)
                        if fear_greed_value is not None:
                            print(f"Found fear & greed value in dial-number span: {fear_greed_value}")
            
            # Method 4: Alternative CNN selectors
            if fear_greed_value is None and soup is not None:
                selectors = [
                    "market-fng-gauge__dial-number-value",
                    "fng-gauge__dial-number-value", 
                    "fear-greed-gauge-value",
                    "fng-value"
                ]
                for selector in selectors:
                    element = soup.find(class_=selector)
                    if element:
                        text = element.get_text().strip()
                        fear_greed_value = self._extract_index_value(text)
                        if fear_greed_value is not None:
                            print(f"Found fear & greed value with selector {selector}: {fear_greed_value}")
                            break
            
            # Method 5: Look in script tags for JSON data (CNN often embeds data)
            if fear_greed_value is None and soup is not None:
                scripts = soup.find_all('script')
                for script in scripts:
                    if script.string:
                        # Look for fear/greed related JSON
                        fng_matches = re.findall(r'"(?:fear.*greed|fng).*?":\s*(\d+)', script.string, re.IGNORECASE)
                        for match in fng_matches:
                            fear_greed_value = self._extract_index_value(match)
                            if fear_greed_value is not None:
                                print(f"Found fear & greed value in script: {fear_greed_value}")
                                break
                        if fear_greed_value is not None:
                            break
            
            # Determine fear/greed label based on value
            if fear_greed_value is not None:
                if fear_greed_value <= 25:
                    fear_greed_label = "Extreme Fear"
                elif fear_greed_value <= 45:
                    fear_greed_label = "Fear"
                elif fear_greed_value <= 55:
                    fear_greed_label = "Neutral"
                elif fear_greed_value <= 75:
                    fear_greed_label = "Greed"
                else:
                    fear_greed_label = "Extreme Greed"
            
            return {
                'index_value': fear_greed_value,
                'label': fear_greed_label,
                'timestamp': timestamp.isoformat(),
                'source': 'CNN',
                'url': url,
                'status': 'success' if fear_greed_value is not None else 'error',
                'error': 'No fear & greed value found' if fear_greed_value is None else None
            }
            
        except Exception as e:
            return {
                'index_value': None,
                'label': None,
                'timestamp': datetime.now().isoformat(),
                'source': 'CNN',
                'url': url,
                'status': 'error',
                'error': str(e)
            }

    def save_to_supabase(self, data):
        """Save Fear & Greed Index data to Supabase"""
        if not self.supabase:
            print("Supabase not configured")
            return False
            
        try:
            result = self.supabase.table("indicators").upsert({
                "indicator_type": "FEAR_GREED",
                "symbol": "US_MARKET",
                "value": data['index_value'],
                "metadata": {
                    "label": data['label'],
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
        """Save Fear & Greed Index data to local file"""
        try:
            if filename is None:
                filename = os.path.join(
                    os.path.dirname(os.path.dirname(__file__)),
                    "fear_greed_data.json",
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
        print("Fetching Fear & Greed Index from CNN...")
        
        data = self.fetch_fear_greed_index()
        
        print(f"Fear & Greed Index: {data['index_value']}")
        print(f"Label: {data['label']}")
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
    fetcher = FearGreedFetcher()
    result = fetcher.run()
