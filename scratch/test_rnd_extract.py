import yfinance as yf
import pandas as pd

ticker = yf.Ticker("AMD")
financials = ticker.financials

print("Financials shape:", financials.shape)
print("\nFinancials index:", financials.index.tolist())

# Try to extract Research And Development
if "Research And Development" in financials.index:
    rnd_row = financials.loc["Research And Development"]
    print("\nResearch And Development row:")
    print(rnd_row)
    print("Types:", type(rnd_row))
else:
    print("\nResearch And Development row not found.")

if "Total Revenue" in financials.index:
    rev_row = financials.loc["Total Revenue"]
    print("\nTotal Revenue row:")
    print(rev_row)
else:
    print("\nTotal Revenue row not found.")
