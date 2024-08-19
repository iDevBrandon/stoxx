import puppeteer from "puppeteer";

// Function to scrape DXY value from TradingView
const scrapeDXY = async (browser) => {
  const page = await browser.newPage();
  const url = "https://www.tradingview.com/symbols/TVC-DXY/";

  try {
    await page.goto(url, { waitUntil: "networkidle2" });
    await page.waitForSelector(".last-JWoJqCpY.js-symbol-last");

    const dxyValue = await page.evaluate(() => {
      const valueElement = document.querySelector(
        ".last-JWoJqCpY.js-symbol-last"
      );
      return valueElement ? valueElement.textContent.trim() : null;
    });

    console.log("DXY Value:", dxyValue);
  } catch (error) {
    console.error("Error scraping DXY:", error);
  } finally {
    await page.close();
  }
};

// Function to scrape Fear and Greed Index from another source
const scrapeFearAndGreedIndex = async (browser) => {
  const page = await browser.newPage();
  const url = "https://edition.cnn.com/markets/fear-and-greed"; // Replace with the actual URL

  try {
    await page.goto(url, { waitUntil: "networkidle2" });
    await page.waitForSelector(".market-fng-gauge__dial-number-value"); // Updated selector

    const fearAndGreedIndex = await page.evaluate(() => {
      const indexElement = document.querySelector(
        ".market-fng-gauge__dial-number-value" // Updated selector
      );
      return indexElement ? indexElement.textContent.trim() : null;
    });

    console.log("Fear and Greed Index:", fearAndGreedIndex);
  } catch (error) {
    console.error("Error scraping Fear and Greed Index:", error);
  } finally {
    await page.close();
  }
};

// Main function to handle the scraping of both DXY and Fear and Greed Index
const scrape = async () => {
  const browser = await puppeteer.launch({ headless: false });

  // Scrape DXY Value
  await scrapeDXY(browser);

  // Scrape Fear and Greed Index
  await scrapeFearAndGreedIndex(browser);

  // Close the browser
  await browser.close();
};

scrape();
