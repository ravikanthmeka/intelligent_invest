import json

data = {
    "net_liquidation": 1000.0,
    "cash": 1000.0,
    "active_trades": {},
    "completed_trades": [],
    "candidate_evaluations": []
}

with open("trading_state.json", "w") as f:
    json.dump(data, f, indent=4)

print("State reset successfully!")
