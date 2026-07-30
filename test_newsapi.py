import os
import sys
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

load_dotenv("c:\\Users\\Codewiz Nashua\\geminiprojects\\intelligent_invest\\.env")

from src.skills.market_data import FetchRecentNewsSkill

def main():
    skill = FetchRecentNewsSkill()
    print("Testing News API integration...")
    news = skill.execute("AAPL")
    
    print("\nResults:")
    import json
    print(json.dumps(news, indent=2))

if __name__ == "__main__":
    main()
