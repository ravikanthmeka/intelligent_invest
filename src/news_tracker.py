import json
import os
from datetime import datetime, timedelta
from typing import Dict, Any, List

class NewsTracker:
    FILE_PATH = "data/news_analysis.json"

    @classmethod
    def load(cls) -> List[Dict[str, Any]]:
        if not os.path.exists(cls.FILE_PATH):
            return []
        try:
            with open(cls.FILE_PATH, "r") as f:
                return json.load(f)
        except Exception:
            return []

    @classmethod
    def save(cls, data: List[Dict[str, Any]]):
        os.makedirs(os.path.dirname(cls.FILE_PATH), exist_ok=True)
        try:
            with open(cls.FILE_PATH, "w") as f:
                json.dump(data, f, indent=4)
        except Exception as e:
            print(f"Error saving news analysis: {e}")

    @classmethod
    def log(cls, symbol: str, analysis: Dict[str, Any]):
        """
        Logs a news analysis to the persistent JSON file.
        Automatically prunes logs older than 24 hours.
        """
        now = datetime.now()
        data = cls.load()
        
        # Prune old entries (> 24 hours)
        data = [
            item for item in data 
            if datetime.fromisoformat(item["timestamp"]) > now - timedelta(hours=24)
        ]
        
        # Add new entry
        entry = {
            "timestamp": now.isoformat(),
            "symbol": symbol,
            "sentiment_score": analysis.get("sentiment_score", 0),
            "sentiment_label": analysis.get("sentiment_label", "Neutral"),
            "summary": analysis.get("summary", "No summary available"),
            "key_events": analysis.get("key_events", [])
        }
        
        # Insert at the beginning so the newest is first (though we can sort in the UI)
        data.insert(0, entry)
        
        cls.save(data)
