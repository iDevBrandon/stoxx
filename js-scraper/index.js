import { getDividendYield } from "./src/getData.js";

const dailyDividendYiledReport = async () => {
  const DividendYield = await getDividendYield("AAPL");
  console.log(DividendYield);
};

dailyDividendYiledReport();
