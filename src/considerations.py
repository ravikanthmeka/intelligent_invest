import json
import os
import datetime
from typing import Dict, Any
import logging

logger = logging.getLogger("ConsiderationsTracker")

CONSIDERATIONS_FILE = "data/considerations.json"

class ConsiderationsTracker:
    """Tracks discarded and evaluated trades so they can be viewed in the dashboard."""
    
    @staticmethod
    def _load_data() -> Dict[str, Any]:
        if not os.path.exists("data"):
            os.makedirs("data", exist_ok=True)
            
        if not os.path.exists(CONSIDERATIONS_FILE):
            return {}
            
        try:
            with open(CONSIDERATIONS_FILE, "r") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load considerations: {e}")
            return {}
            
    @staticmethod
    def _save_data(data: Dict[str, Any]):
        if not os.path.exists("data"):
            os.makedirs("data", exist_ok=True)
            
        try:
            with open(CONSIDERATIONS_FILE, "w") as f:
                json.dump(data, f, indent=4)
        except Exception as e:
            logger.error(f"Error saving considerations: {e}")
            
    @classmethod
    def log(cls, symbol: str, strategy: str, score: float, reason: str):
        data = cls._load_data()
        
        # We store by symbol + strategy to keep the latest attempt per ticker
        key = f"{symbol}_{strategy}"
        data[key] = {
            "symbol": symbol,
            "strategy": strategy,
            "score": round(score, 2) if isinstance(score, (float)) else score,
            "reason": reason,
            "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        # Optional: Prune very old entries to keep file size small (e.g. older than 24h)
        now = datetime.datetime.now()
        keys_to_delete = []
        for k, v in data.items():
            try:
                item_time = datetime.datetime.strptime(v["timestamp"], "%Y-%m-%d %H:%M:%S")
                if (now - item_time).total_seconds() > 86400: # 24 hours
                    keys_to_delete.append(k)
            except Exception:
                keys_to_delete.append(k) # Delete malformed
                
        for k in keys_to_delete:
            del data[k]
        
        cls._save_data(data)
        
    @classmethod
    def get_all(cls) -> list:
        data = cls._load_data()
        # Sort by most recent
        items = list(data.values())
        items.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
        return items
