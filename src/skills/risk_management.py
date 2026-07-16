from typing import Dict, Any
from src.skills.base import Skill

class CalculatePositionSizeSkill(Skill):
    def __init__(self, max_cap_pct: float = 0.20, risk_pct: float = 0.01):
        super().__init__(
            name="CalculatePositionSize",
            description="Calculates position quantity and stop-loss price based on portfolio value, entry price, ATR, and risk rules."
        )
        self.max_cap_pct = max_cap_pct
        self.risk_pct = risk_pct

    def execute(self, portfolio_value: float, entry_price: float, atr: float, risk_pct: float = None, max_cap_pct: float = None) -> Dict[str, Any]:
        r_pct = risk_pct if risk_pct is not None else self.risk_pct
        c_pct = max_cap_pct if max_cap_pct is not None else self.max_cap_pct

        # Initial stop-loss: 3 * ATR
        atr_stop = entry_price - (3 * atr)
        
        # Bounded between 5% and 7% stop loss away from entry to avoid noise and protect capital
        stop_loss_price = max(atr_stop, entry_price * 0.93) # looser bound (7% max risk distance)
        stop_loss_price = min(stop_loss_price, entry_price * 0.95) # tighter bound (5% min risk distance)

        # Risk amount
        max_risk_amount = portfolio_value * r_pct
        risk_distance = entry_price - stop_loss_price
        
        # Quantity calculation based on risk distance
        quantity = int(max_risk_amount // risk_distance)
        capital_required = quantity * entry_price
        
        # Limit capital allocated
        max_capital_allowed = portfolio_value * c_pct
        if capital_required > max_capital_allowed:
            quantity = int(max_capital_allowed // entry_price)
            capital_required = quantity * entry_price
            
        return {
            "quantity": quantity,
            "stop_loss_price": round(stop_loss_price, 2),
            "capital_required": round(capital_required, 2),
            "risk_amount": round(quantity * risk_distance, 2),
            "risk_pct_of_portfolio": round((quantity * risk_distance) / portfolio_value * 100, 2),
            "capital_pct_of_portfolio": round(capital_required / portfolio_value * 100, 2)
        }

class EvaluateActivePositionSkill(Skill):
    def __init__(self):
        super().__init__(
            name="EvaluateActivePosition",
            description="Evaluates active position performance to determine if trailing stop-loss should be raised or if position should be sold."
        )

    def execute(self, symbol: str, entry_price: float, current_price: float, current_stop: float, atr: float, momentum_is_strong: bool) -> Dict[str, Any]:
        return_pct = (current_price - entry_price) / entry_price
        
        verdict = "HOLD"
        new_stop = current_stop
        rationale = "Position is performing within normal bounds."

        # Exit if trailing stop triggered
        if current_price <= current_stop:
            return {"action": "SELL", "new_stop": 0.0, "rationale": f"Stop loss triggered at ${current_stop:.2f}"}

        # Dynamic stop adjustment after 3% return
        if return_pct >= 0.03:
            if momentum_is_strong:
                # Lock in profits by moving stop loss up to entry (breakeven) or trailing by 2 * ATR
                potential_stop = current_price - (2 * atr)
                # Ensure stop is only moved UP, never down
                new_stop = max(current_stop, potential_stop, entry_price)
                verdict = "HOLD_RAISE_STOP"
                rationale = f"Strong momentum with {return_pct*100:.1f}% gain. Raised stop-loss to ${new_stop:.2f} to let winner run."
            else:
                # Momentum is weakening after hitting target: take profit / sell
                verdict = "SELL"
                rationale = f"Target return hit with weakening momentum. Exiting position at ${current_price:.2f}."

        return {
            "action": verdict,
            "new_stop": round(new_stop, 2),
            "return_pct": round(return_pct * 100, 2),
            "rationale": rationale
        }
