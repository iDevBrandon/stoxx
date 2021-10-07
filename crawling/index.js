/*
 // https://www.nasdaq.com/market-activity/stocks/msft/dividend-history
//li.dividend-history__summary-item:nth-child(2)>span.dividend-history__summary-item__value>span
export const getDividendYiled = async (symbol) => {
  return await axios.get(`https://www.nasdaq.com/market-activity/stocks/${symbol}/dividend-history`)
    .then(html => {
      const $ = cheerio.load(html.data)
      return $("li.dividend-history__summary-item:nth-child(2)").html()
    })
}
*/

// 1. CSS Selector
const cheerio = require("cheerio");
const express = require("express");
const axios = require("axios");
const request = require("request");
const port = process.env.PORT || 3000;

const app = express();

async function getDividend() {
  try {
    var headers = {
      authority: "api.nasdaq.com",
      "sec-ch-ua":
        '"Chromium";v="94", "Google Chrome";v="94", ";Not A Brand";v="99"',
      accept: "application/json, text/plain, */*",
      "sec-ch-ua-mobile": "?0",
      "user-agent":
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/94.0.4606.71 Safari/537.36",
      "sec-ch-ua-platform": '"macOS"',
      origin: "https://www.nasdaq.com",
      "sec-fetch-site": "same-site",
      "sec-fetch-mode": "cors",
      "sec-fetch-dest": "empty",
      referer: "https://www.nasdaq.com/",
      "accept-language": "en-GB,en;q=0.9,ko-KR;q=0.8,ko;q=0.7,en-US;q=0.6",
    };

    var options = {
      url: "https://api.nasdaq.com/api/quote/MSFT/dividends?assetclass=stocks",
      headers: headers,
    };

    function callback(error, response, body) {
      if (!error && response.statusCode == 200) {
        // console.log(body);

        const $ = cheerio.load(body);

        
         
      }
    }

    request(options, callback);
  } catch (error) {
    console.log(error);
  }
}

getDividend();

app.listen(port, () => console.log(`Server is running on PORT ${port}`));

