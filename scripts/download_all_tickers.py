import os

import yfinance as yf

popular_tickers = ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA", "META", "NVDA", "JPM", "V", "DIS"]
start = "2016-01-01"
end = "2026-01-01"
data_dir = "data"

if not os.path.exists(data_dir):
    os.makedirs(data_dir)

for ticker in popular_tickers:
    print(f"Downloading {ticker}...")
    df = yf.download(ticker, start=start, end=end)
    if not df.empty:
        df.to_csv(f"{data_dir}/{ticker}_10y.csv")
        print(f"Saved {ticker}_10y.csv")
    else:
        print(f"No data for {ticker}")
