// import puppeteer from "puppeteer";

// const scrape = async () => {
//   const browser = await puppeteer.launch({ headless: false }); // Browser stays visible
//   const page = await browser.newPage();

//   const url = "https://www.tradingview.com/symbols/TVC-DXY/";

//   await page.goto(url, { waitUntil: "domcontentloaded" });

//   // Wait for the selector
//   const content = await page.content();
//   console.log(content);

//   // Keep the browser open for 30 seconds so we can inspect it manually

//   await browser.close();
// };

// scrape();

import puppeteer from "puppeteer";

const scrape = async () => {
  const browser = await puppeteer.launch({ headless: false }); // Browser stays visible
  const page = await browser.newPage();

  const url = "https://www.tradingview.com/symbols/TVC-DXY/";

  await page.goto(url, { waitUntil: "networkidle2" }); // Wait until the network is idle

  // Wait for the specific element to be loaded in the DOM
  await page.waitForSelector(".last-JWoJqCpY.js-symbol-last");

  // Extract the value
  const tradingviewDXYValue = await page.evaluate(() => {
    const valueElement = document.querySelector(
      ".last-JWoJqCpY.js-symbol-last"
    );
    return valueElement ? valueElement.textContent.trim() : null;
  });

  console.log("DXY Value:", tradingviewDXYValue);

  // Close the browser
  await browser.close();
};

scrape();
