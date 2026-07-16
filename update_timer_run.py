import yaml
import sys
import os

sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from src.dashboard import update_systemd_timer

if __name__ == "__main__":
    with open("config.yaml", "r") as f:
        cfg = yaml.safe_load(f)
    interval = cfg.get("scheduler", {}).get("interval_minutes", 30)
    update_systemd_timer(interval)
    print(f"Systemd timer updated successfully with interval {interval}!")
