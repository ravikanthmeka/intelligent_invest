import yfinance as yf

ticker = yf.Ticker("AMD")
print("AMD info keys sample:", list(ticker.info.keys())[:10])
print("\nAMD financials columns:", ticker.financials.index.tolist())
