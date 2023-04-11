const express = require("express");
const request = require("request-promise");

const app = express();
const PORT = process.env.PORT || 8000;

app.use(express.json());

app.get("/", (req, res) => {
  res.send("Welcome to OXINION Finance!");
});

// Get stocks data

app.get("/stocks/:symbol", async (req, res) => {
  const { symbol } = req.params;
  try {

  } catch (err) {
    res.json(err)
  }
});

//stocks?symbol={ticker}

app.listen(PORT, () => {
  console.log(`Server started on port ${PORT}`);
});
