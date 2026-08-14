import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.token_tracker import TokenTracker

def test():
    print("Testing TokenTracker...")
    
    TokenTracker.log("openai", "gpt-4o", 100, 20)
    TokenTracker.log("bedrock", "google.gemma-3-12b-it", 150, 30)
    
    summary = TokenTracker.get_today_summary()
    print("Today Summary:")
    print(summary)

if __name__ == "__main__":
    test()
