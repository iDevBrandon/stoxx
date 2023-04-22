// https://www.nasdaq.com/market-activity/stocks/aapl/dividend-history
// https://seekingalpha.com/symbol/AAPL/dividends/dividend-growth
// https://www.digrin.com/stocks/detail/AAPL/

// first, find CSS selector
// li:nth-child(2) > span.dividend-history__summary-item__value > span
// body > div.dialog-off-canvas-main-canvas > div > main > div.page__content > div.quote-detail__content.quote-detail__content--dividend.dividend-history-content > div.layout.layout--2-col-large > div > div.dividend-history.dividend-history--loaded > ul > li:nth-child(2) > span.dividend-history__summary-item__value

import axios from "axios";
import * as cheerio from "cheerio";

export const getDividendYield = async (symbol) => {
  return await axios
    .get(`https://www.digrin.com/stocks/detail/${symbol}/`)
    .then((html) => {
      const $ = cheerio.load(html.data);
      return $(
        "body > div.container > div.row > div.col-sm-3 > p:nth-child(32) > span > strong"
      ).html();
    });
};
