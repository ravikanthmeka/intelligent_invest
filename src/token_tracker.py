import json
import os
import threading
from datetime import datetime, timedelta
from typing import Dict, Any, List

class TokenTracker:
    DATA_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "token_usage.json")
    _lock = threading.Lock()

    @classmethod
    def _ensure_dir(cls):
        os.makedirs(os.path.dirname(cls.DATA_FILE), exist_ok=True)

    @classmethod
    def log(cls, provider: str, model: str, prompt_tokens: int, completion_tokens: int):
        cls._ensure_dir()
        entry = {
            "timestamp": datetime.now().isoformat(),
            "provider": provider,
            "model": model,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens
        }

        with cls._lock:
            data = cls.load()
            data.append(entry)
            
            # Prune data older than 7 days
            cutoff = datetime.now() - timedelta(days=7)
            pruned_data = [
                item for item in data
                if datetime.fromisoformat(item["timestamp"]) > cutoff
            ]
            
            try:
                with open(cls.DATA_FILE, "w") as f:
                    json.dump(pruned_data, f, indent=4)
            except Exception as e:
                import logging
                logging.getLogger("TokenTracker").error(f"Failed to write token data: {e}")

    @classmethod
    def load(cls) -> List[Dict[str, Any]]:
        cls._ensure_dir()
        if not os.path.exists(cls.DATA_FILE):
            return []
            
        try:
            with open(cls.DATA_FILE, "r") as f:
                return json.load(f)
        except Exception:
            return []

    @classmethod
    def get_today_summary(cls) -> Dict[str, Any]:
        data = cls.load()
        today = datetime.now().date()
        
        summary = {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
            "by_model": {}
        }
        
        for item in data:
            dt = datetime.fromisoformat(item["timestamp"]).date()
            if dt == today:
                summary["prompt_tokens"] += item.get("prompt_tokens", 0)
                summary["completion_tokens"] += item.get("completion_tokens", 0)
                summary["total_tokens"] += item.get("total_tokens", 0)
                
                model = item.get("model", "unknown")
                if model not in summary["by_model"]:
                    summary["by_model"][model] = 0
                summary["by_model"][model] += item.get("total_tokens", 0)
                
        return summary
