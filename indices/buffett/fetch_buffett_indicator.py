import json
from datetime import datetime
import os
from playwright.sync_api import sync_playwright

# CSS selector for the current Buffett Indicator value on macromicro.me
BUFFETT_SELECTOR = (
    "#panel > main > div "
    "> div.mm-cc-hd > div "
    "> div.mm-cc-chart-stats-title.pb-2.d-flex.flex-wrap.align-items-baseline "
    "> div.stat-val > span.val"
)

BUFFETT_URL = "https://en.macromicro.me/series/617/wilshire5000-to-gdp"


def _get_valuation_level(percentage):
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


class BuffettIndicatorFetcher:
    def __init__(self):
        pass

    def fetch_buffett_indicator(self):
        """Fetch the Buffett Indicator from macromicro.me using a headless browser."""
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

                print(f"Navigating to {BUFFETT_URL} ...")
                page.goto(BUFFETT_URL, wait_until="domcontentloaded", timeout=60_000)

                # Wait for the header stat value to be populated
                page.wait_for_selector(BUFFETT_SELECTOR, timeout=30_000)
                page.wait_for_function(
                    f"""() => {{
                        const el = document.querySelector('{BUFFETT_SELECTOR}');
                        const v = el && el.innerText.trim();
                        return v && parseFloat(v) > 0;
                    }}""",
                    timeout=30_000,
                )

                raw_text = page.locator(BUFFETT_SELECTOR).inner_text().strip()
                browser.close()

            # Parse e.g. "175.3%" → 175.3
            percentage = None
            cleaned = raw_text.replace("%", "").strip()
            if cleaned:
                percentage = float(cleaned)

            valuation = _get_valuation_level(percentage)

            return {
                "percentage": percentage,
                "indicator_value": percentage / 100 if percentage is not None else None,
                "valuation_level": valuation,
                "raw": raw_text,
                "timestamp": timestamp.isoformat(),
                "source": "MacroMicro",
                "url": BUFFETT_URL,
                "status": "success" if percentage is not None else "no_data",
                "error": None if percentage is not None else "No value found",
            }

        except Exception as e:
            return {
                "percentage": None,
                "indicator_value": None,
                "valuation_level": None,
                "raw": None,
                "timestamp": timestamp.isoformat(),
                "source": "MacroMicro",
                "url": BUFFETT_URL,
                "status": "error",
                "error": str(e),
            }

    def save_to_file(self, data, filename=None):
        """Save Buffett Indicator data to a local JSON file."""
        try:
            if filename is None:
                filename = os.path.join(
                    os.path.dirname(os.path.dirname(__file__)),
                    "buffett_indicator_data.json",
                )

            existing_data = []
            if os.path.exists(filename):
                try:
                    with open(filename, "r") as f:
                        existing_data = json.load(f)
                except (json.JSONDecodeError, ValueError):
                    existing_data = []

            existing_data.append(data)
            existing_data = existing_data[-1000:]

            with open(filename, "w") as f:
                json.dump(existing_data, f, indent=2, default=str)

            return True
        except Exception as e:
            print(f"Error saving to file: {e}")
            return False

    def run(self):
        """Main execution function."""
        print("Fetching Buffett Indicator from MacroMicro...")

        data = self.fetch_buffett_indicator()

        print(f"Buffett Indicator: {data['percentage']}%")
        print(f"Valuation Level:   {data['valuation_level']}")
        print(f"Status:            {data['status']}")
        print(f"Timestamp:         {data['timestamp']}")

        saved_to_file = self.save_to_file(data)
        if saved_to_file:
            print("✅ Data saved to local file")

        return data


if __name__ == "__main__":
    fetcher = BuffettIndicatorFetcher()
    result = fetcher.run()
