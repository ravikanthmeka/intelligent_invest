import sys
import os
import asyncio
import logging
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.skills.market_data import FetchRecentNewsSkill

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

def main():
    load_dotenv()
    
    # We expect ALPHAVANTAGE_API_KEY to be in .env
    print("ALPHAVANTAGE_API_KEY:", os.environ.get("ALPHAVANTAGE_API_KEY"))
    
    skill = FetchRecentNewsSkill()
    
    print("Fetching news for AAPL...")
    news_aapl = skill.execute("AAPL")
    print(f"Found {len(news_aapl)} articles for AAPL:")
    for a in news_aapl:
        print(f"  - {a['title']} ({a['publisher']})")
        
    print("\nFetching news for MSFT...")
    news_msft = skill.execute("MSFT")
    print(f"Found {len(news_msft)} articles for MSFT:")
    for a in news_msft:
        print(f"  - {a['title']} ({a['publisher']})")

if __name__ == "__main__":
    main()
