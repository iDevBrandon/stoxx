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
                page.goto(TRADINGVIEW_URL, wait_until="domcontentloaded", timeout=60_000)

                # Wait for the oscillators table cell to appear
                page.wait_for_selector(RSI_SELECTOR, timeout=30_000)

                rsi_text = page.locator(RSI_SELECTOR).inner_text().strip()
                rsi_value = float(rsi_text) if rsi_text else None

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