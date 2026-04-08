import json
from datetime import datetime
import os
from playwright.sync_api import sync_playwright


# CSS selector for the RSI value cell in TradingView's oscillators table
RSI_SELECTOR = (
    "#js-category-content > div.technicals-root > div > section > div "
    "> div.tablesWrapper-kg4MJrFB.tabletVertical-kg4MJrFB "
    "> div:nth-child(1) > div.tableWrapper-hvDpy38G "
    "> table > tbody > tr:nth-child(2) > td:nth-child(2)"
)

TRADINGVIEW_URL = "https://www.tradingview.com/symbols/AMEX-VOO/technicals/"


class RSIFetcher:
    def __init__(self):
        pass

    def fetch_voo_rsi(self):
        """Fetch RSI(14) data for VOO from TradingView using a headless browser."""
        timestamp = datetime.now()
        
        # Alternative selectors in case the main one fails
        rsi_selectors = [
            RSI_SELECTOR,
            # Alternative selector patterns for RSI
            "table tbody tr:nth-child(2) td:nth-child(2)",
            "[data-name='RSI'] td:nth-child(2)",
            "table tr:contains('RSI') td:nth-child(2)"
        ]
        
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                context = browser.new_context(
                    user_agent=(
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/124.0.0.0 Safari/537.36"
                    )
                )
                page = context.new_page()

                print(f"Navigating to {TRADINGVIEW_URL} ...")
                
                # Increase timeout and add retry logic
                for attempt in range(3):
                    try:
                        page.goto(TRADINGVIEW_URL, wait_until="networkidle", timeout=90_000)
                        print(f"✅ Successfully navigated to TradingView (attempt {attempt + 1})")
                        break
                    except Exception as e:
                        print(f"❌ Navigation attempt {attempt + 1} failed: {str(e)[:100]}")
                        if attempt == 2:
                            raise e
                        print(f"🔄 Retrying in 5 seconds...")
                        page.wait_for_timeout(5000)

                # Wait for page to fully load
                print("⏳ Waiting for page content to load...")
                page.wait_for_timeout(5000)

                # Try multiple selectors
                rsi_value = None
                for i, selector in enumerate(rsi_selectors):
                    try:
                        print(f"🔍 Trying selector {i+1}: {selector[:50]}...")
                        page.wait_for_selector(selector, timeout=15_000)
                        rsi_text = page.locator(selector).inner_text().strip()
                        
                        if rsi_text and rsi_text.replace('.', '').replace('-', '').isdigit():
                            rsi_value = float(rsi_text)
                            print(f"✅ Found RSI value: {rsi_value}")
                            break
                        else:
                            print(f"⚠️  Selector found but text invalid: '{rsi_text}'")
                    except Exception as e:
                        print(f"❌ Selector {i+1} failed: {str(e)[:50]}")
                        continue

                browser.close()

            return {
                'symbol': 'VOO',
                'rsi': rsi_value,
                'timestamp': timestamp.isoformat(),
                'source': 'TradingView',
                'url': TRADINGVIEW_URL,
                'status': 'success' if rsi_value is not None else 'no_data',
            }

        except Exception as e:
            return {
                'symbol': 'VOO',
                'rsi': None,
                'timestamp': timestamp.isoformat(),
                'source': 'TradingView',
                'url': TRADINGVIEW_URL,
                'status': 'error',
                'error': str(e),
            }


    def save_to_file(self, data, filename="rsi_data.json"):
        """Save RSI data to local file"""
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
        print("Fetching RSI data for VOO...")
        
        data = self.fetch_voo_rsi()
        
        print(f"RSI Value: {data['rsi']}")
        print(f"Status: {data['status']}")
        print(f"Timestamp: {data['timestamp']}")
        
        # Save to local file
        saved_to_file = self.save_to_file(data)

        if saved_to_file:
            print("✅ Data saved to local file")
        
        return data

if __name__ == "__main__":
    fetcher = RSIFetcher()
    result = fetcher.run()