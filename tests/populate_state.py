import json

data = {
    "net_liquidation": 1000.0,
    "cash": 1000.0,
    "active_trades": {
        "XOM": {
            "entry_price": 146.4600067138672,
            "stop_loss_price": 137.69,
            "quantity": 1,
            "initial_capital": 146.46,
            "purchased_at": "2026-07-16T16:30:36.554798",
            "order_id": "12",
            "risk_tier": "low"
        },
        "KO": {
            "entry_price": 84.16000366210938,
            "stop_loss_price": 78.83,
            "quantity": 1,
            "initial_capital": 84.16,
            "purchased_at": "2026-07-16T16:30:52.089612",
            "order_id": "15",
            "risk_tier": "low"
        }
    },
    "completed_trades": [
        {
            "symbol": "CVX",
            "risk_tier": "moderate",
            "quantity": 2,
            "entry_price": 155.20,
            "exit_price": 162.80,
            "initial_capital": 310.40,
            "purchased_at": "2026-07-15T14:30:00",
            "sold_at": "2026-07-16T10:30:00",
            "realized_pnl": 15.20,
            "return_pct": 0.0489,
            "exit_reason": "Profit target / weak momentum liquidation",
            "analysis": {
                "tech_score": 8.2,
                "fund_score": 7.5,
                "news_score": 7.0
            }
        },
        {
            "symbol": "KO",
            "risk_tier": "low",
            "quantity": 2,
            "entry_price": 62.50,
            "exit_price": 58.75,
            "initial_capital": 125.00,
            "purchased_at": "2026-07-15T15:00:00",
            "sold_at": "2026-07-16T11:00:00",
            "realized_pnl": -7.50,
            "return_pct": -0.0600,
            "exit_reason": "Stop loss triggered (broker execution)",
            "analysis": {
                "tech_score": 6.8,
                "fund_score": 6.2,
                "news_score": 5.5
            }
        }
    ]
}

with open("trading_state.json", "w") as f:
    json.dump(data, f, indent=4)
print("Populated state successfully!")
