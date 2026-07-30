import yfinance as yf
import json

def test_yf():
    t = yf.Ticker("AAPL")
    
    print("--- INSIDER ---")
    try:
        ins = t.insider_purchases
        print("Purchases:", ins)
    except Exception as e:
        print("Insider error:", e)
        
    print("\n--- DIVIDENDS ---")
    try:
        info = t.info
        print("Yield:", info.get('dividendYield'))
        print("Payout Ratio:", info.get('payoutRatio'))
    except Exception as e:
        print("Dividend error:", e)
        
    print("\n--- OPTIONS ---")
    try:
        exp = t.options
        if exp:
            chain = t.option_chain(exp[0])
            print("Calls shape:", chain.calls.shape)
            print("Puts shape:", chain.puts.shape)
    except Exception as e:
        print("Options error:", e)

if __name__ == "__main__":
    test_yf()
