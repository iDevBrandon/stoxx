const express = require("express");
const request = require("request-promise");
const axios = require("axios");
const cheerio = require("cheerio");

const app = express();
const PORT = process.env.PORT || 8000;

app.use(express.json());

app.get("/", (req, res) => {
  res.send("Welcome to OXINION Finance!");
});

// Get stocks data

app.get("/stocks/:symbol", async (req, res) => {
  let dividends = [];

  const { symbol } = req.params;
  try {
    axios
      .get(`https://cors.bridged.cc/https://www.digrin.com/stocks/detail/${symbol}/`)
      .then((response) => {
        const html = response.data;
        const $ = cheerio.load(html);

        $("h2", html).each(function () {
          const name = $(this).text();

          dividends.push(name);
        });

        $('p:contains("DGR5")', html).each(function () {
          const dgrFive = $(this).text();

          dividends.push(dgrFive);
        });
        res.json(dividends);
      });
  } catch (err) {
    res.json(err);
  }
});

//stocks?symbol={ticker}

app.listen(PORT, () => {
  console.log(`Server started on port ${PORT}`);
});
