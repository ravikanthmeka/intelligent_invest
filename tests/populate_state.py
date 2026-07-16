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
    ],
    "candidate_evaluations": [
        {
            "symbol": "CRWD",
            "risk_tier": "high",
            "timestamp": "2026-07-16T16:24:10.000000",
            "status": "Skipped: Fundamental Strength (UNFAVORABLE, Score: 3.5)",
            "analysis": {
                "earnings_checked": "PASSED",
                "news_score": 6.0,
                "news_verdict": "NEUTRAL",
                "tech_score": 7.8,
                "tech_verdict": "BULLISH",
                "fund_score": 3.5,
                "fund_verdict": "UNFAVORABLE"
            }
        },
        {
            "symbol": "UNH",
            "risk_tier": "moderate",
            "timestamp": "2026-07-16T16:24:41.000000",
            "status": "Skipped: Earnings Shield (Upcoming earnings on 2026-07-16 (0 days away))",
            "analysis": {
                "earnings_checked": "TRIGGERED",
                "news_score": None,
                "news_verdict": None,
                "tech_score": None,
                "tech_verdict": None,
                "fund_score": None,
                "fund_verdict": None
            }
        },
        {
            "symbol": "KO",
            "risk_tier": "low",
            "timestamp": "2026-07-16T16:24:52.000000",
            "status": "Purchased",
            "analysis": {
                "earnings_checked": "PASSED",
                "news_score": 8.0,
                "news_verdict": "POSITIVE",
                "tech_score": 8.5,
                "tech_verdict": "BULLISH",
                "fund_score": 7.5,
                "fund_verdict": "FAVORABLE"
            }
        }
    ]
}

with open("trading_state.json", "w") as f:
    json.dump(data, f, indent=4)
print("Populated state successfully!")
