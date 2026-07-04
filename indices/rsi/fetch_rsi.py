import json
import os
from datetime import datetime
from playwright.sync_api import sync_playwright

TRADINGVIEW_URL = "https://www.tradingview.com/symbols/AMEX-VOO/technicals/"


class RSIFetcher:
    def fetch_voo_rsi(self):
        timestamp = datetime.now()

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                context = browser.new_context(
                    user_agent=(
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/124.0.0.0 Safari/537.36"
                    ),
                    viewport={"width": 1280, "height": 900},
                )
                page = context.new_page()

                print(f"🌐 Navigating to TradingView technicals...")
                page.goto(TRADINGVIEW_URL, wait_until="domcontentloaded", timeout=60_000)
                page.wait_for_timeout(6_000)

                rsi_value = None

                # ── Strategy 1: find RSI row by label, get value from 2nd <td> ──
                try:
                    print("🔍 Strategy 1: row label → 2nd cell value...")
                    rows = page.locator("tr").all()
                    for row in rows:
                        try:
                            label = row.locator("td").first.inner_text(timeout=300).strip()
                        except Exception:
                            continue
                        if "Relative Strength Index" in label:
                            try:
                                raw = row.locator("td").nth(1).inner_text(timeout=2_000).strip()
                                rsi_value = float(raw)
                                print(f"✅ Strategy 1 found RSI: {rsi_value}")
                            except Exception as e:
                                print(f"⚠️  RSI row found but value parse failed: {e}")
                            break
                except Exception as e:
                    print(f"⚠️  Strategy 1 failed: {e}")

                # ── Strategy 2: all td.cell-* elements — skip non-numeric ────────
                if rsi_value is None:
                    try:
                        print("🔍 Strategy 2: scan value cells for numeric RSI...")
                        # grab all tds; RSI (0–100) will be among the first oscillator values
                        cells = page.locator("td").all()
                        for cell in cells[:60]:
                            try:
                                raw = cell.inner_text(timeout=200).strip()
                                candidate = float(raw)
                                if 0 < candidate < 100:
                                    rsi_value = candidate
                                    print(f"✅ Strategy 2 found RSI: {rsi_value}")
                                    break
                            except Exception:
                                continue
                    except Exception as e:
                        print(f"⚠️  Strategy 2 failed: {e}")

                browser.close()

            status = "success" if rsi_value is not None else "no_data"
            return {
                "symbol": "VOO",
                "rsi": rsi_value,
                "timestamp": timestamp.isoformat(),
                "source": "TradingView",
                "url": TRADINGVIEW_URL,
                "status": status,
            }

        except Exception as e:
            return {
                "symbol": "VOO",
                "rsi": None,
                "timestamp": timestamp.isoformat(),
                "source": "TradingView",
                "url": TRADINGVIEW_URL,
                "status": "error",
                "error": str(e),
            }

    def save_to_file(self, data, filename="rsi_data.json"):
        try:
            existing = []
            if os.path.exists(filename):
                with open(filename, "r") as f:
                    existing = json.load(f)
            existing.append(data)
            existing = existing[-1000:]
            with open(filename, "w") as f:
                json.dump(existing, f, indent=2, default=str)
            return True
        except Exception as e:
            print(f"Error saving to file: {e}")
            return False

    def run(self):
        print("Fetching RSI(14) for VOO from TradingView...")
        data = self.fetch_voo_rsi()

        print(f"RSI Value: {data['rsi']}")
        print(f"Status: {data['status']}")
        print(f"Timestamp: {data['timestamp']}")

        if self.save_to_file(data):
            print("✅ Data saved to local file")

        if data["status"] not in ("success",):
            raise RuntimeError(f"rsi fetch failed: {data.get('error', data['status'])}")

        return data


if __name__ == "__main__":
    fetcher = RSIFetcher()
    fetcher.run()
