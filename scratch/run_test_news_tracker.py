import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.news_tracker import NewsTracker

def test():
    print("Testing NewsTracker...")
    
    mock_analysis = {
        "sentiment_score": 0.8,
        "sentiment_label": "Bullish",
        "summary": "Strong earnings and growth.",
        "key_events": ["Earnings Beat", "New Product Launch"]
    }
    
    NewsTracker.log("AAPL", mock_analysis)
    
    data = NewsTracker.load()
    print(f"Loaded {len(data)} items from NewsTracker:")
    for d in data:
        print(d)

if __name__ == "__main__":
    test()
