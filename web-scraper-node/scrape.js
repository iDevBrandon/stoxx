import puppeteer from "puppeteer";

// Function to scrape Fear and Greed Index from CNN
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

// Function to scrape VIX value from Yahoo Finance
const scrapeVIX = async (browser) => {
  const page = await browser.newPage();
  const url = "https://www.tradingview.com/symbols/TVC-VIX/"; // Replace with the actual URL

  try {
    await page.goto(url, { waitUntil: "networkidle2" });
    await page.waitForSelector(".last-JWoJqCpY.js-symbol-last");

    const vixValue = await page.evaluate(() => {
      const valueElement = document.querySelector(
        ".last-JWoJqCpY.js-symbol-last"
      );
      return valueElement ? valueElement.textContent.trim() : null;
    });

    console.log("VIX Value:", vixValue);
  } catch (error) {
    console.error("Error scraping VIX:", error);
  } finally {
    await page.close();
  }
};

const scrapeRSI = async (browser) => {
  const page = await browser.newPage();
  const url = "https://finviz.com/quote.ashx?t=VOO&p=d";

  try {
    await page.goto(url, { waitUntil: "networkidle2" });
    await page.waitForSelector("table.snapshot-table2"); // Wait for the table to be loaded

    const rsiValue = await page.evaluate(() => {
      // Locate the table with class 'snapshot-table2'
      const table = document.querySelector("table.snapshot-table2");

      if (!table) {
        console.error("Table not found");
        return null;
      }

      // Locate the row that contains the text 'RSI (14)'
      const rows = Array.from(table.querySelectorAll("tbody tr"));

      for (const row of rows) {
        const cells = Array.from(row.querySelectorAll("td"));
        for (const cell of cells) {
          if (cell.innerText.includes("RSI (14)")) {
            // Extract the value from the cell next to 'RSI (14)'
            const rsiValueCell = cell.nextElementSibling;
            return rsiValueCell ? rsiValueCell.innerText.trim() : null;
          }
        }
      }

      return null;
    });

    console.log("RSI (14) Value:", rsiValue);
  } catch (error) {
    console.error("Error scraping RSI (14) Value:", error);
  } finally {
    await page.close();
  }
};

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

// Function to scrape BI value from GuruFocus
const scrapeBI = async (browser) => {
  const page = await browser.newPage();
  const url = "https://www.gurufocus.com/stock-market-valuations.php";

  try {
    await page.goto(url, { waitUntil: "networkidle2" });
    await page.waitForSelector("table.at"); // Wait for the table to be loaded

    const biValue = await page.evaluate(() => {
      // Locate all tables with class 'at'
      const tables = Array.from(document.querySelectorAll("table.at"));

      // Find the first table that contains the header "Ratio = Total Market Cap / GDP"
      const targetTable = tables.find((table) => {
        const header = table.querySelector("th");
        return (
          header &&
          header.textContent.includes("Ratio = Total Market Cap / GDP")
        );
      });

      console.log(targetTable);

      if (targetTable) {
        // Extract the last row's second cell value from the identified table
        const lastRow = targetTable.querySelector("tbody tr:last-child");
        if (lastRow) {
          const cells = lastRow.querySelectorAll("td");
          return cells.length > 1 ? cells[1].textContent.trim() : null;
        }
      }

      return null;
    });

    console.log("BI Value:", biValue);
  } catch (error) {
    console.error("Error scraping BI Value:", error);
  } finally {
    await page.close();
  }
};

// Main function to handle the scraping of all values
const scrape = async () => {
  const browser = await puppeteer.launch({ headless: false });

  // Scrape Fear and Greed Index
  await scrapeFearAndGreedIndex(browser);

  // Scrape VIX Value
  await scrapeVIX(browser);

  // Scrape RSI Value
  await scrapeRSI(browser);

  // Scrape DXY Value
  await scrapeDXY(browser);

  // Scrape BI Value
  await scrapeBI(browser);

  // Close the browser
  await browser.close();
};

scrape();
