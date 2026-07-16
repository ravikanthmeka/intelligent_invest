from typing import Dict, Any
from src.skills.base import Skill

class CalculatePositionSizeSkill(Skill):
    def __init__(self, max_cap_pct: float = 0.20, risk_pct: float = 0.01, min_stop_loss_pct: float = 0.05, max_stop_loss_pct: float = 0.07):
        super().__init__(
            name="CalculatePositionSize",
            description="Calculates position quantity and stop-loss price based on portfolio value, entry price, ATR, and risk rules."
        )
        self.max_cap_pct = max_cap_pct
        self.risk_pct = risk_pct
        self.min_stop_loss_pct = min_stop_loss_pct
        self.max_stop_loss_pct = max_stop_loss_pct

    def execute(self, portfolio_value: float, entry_price: float, atr: float, risk_pct: float = None, max_cap_pct: float = None, min_stop_loss_pct: float = None, max_stop_loss_pct: float = None, available_tier_capital: float = None) -> Dict[str, Any]:
        r_pct = risk_pct if risk_pct is not None else self.risk_pct
        c_pct = max_cap_pct if max_cap_pct is not None else self.max_cap_pct
        min_sl = min_stop_loss_pct if min_stop_loss_pct is not None else self.min_stop_loss_pct
        max_sl = max_stop_loss_pct if max_stop_loss_pct is not None else self.max_stop_loss_pct

        # Initial stop-loss: 3 * ATR
        atr_stop = entry_price - (3 * atr)
        
        # Bounded between min_sl and max_sl stop loss away from entry to avoid noise and protect capital
        stop_loss_price = max(atr_stop, entry_price * (1.0 - max_sl))
        stop_loss_price = min(stop_loss_price, entry_price * (1.0 - min_sl))

        # Risk amount
        max_risk_amount = portfolio_value * r_pct
        risk_distance = entry_price - stop_loss_price
        
        # Quantity calculation based on risk distance
        quantity = int(max_risk_amount // risk_distance)
        capital_required = quantity * entry_price
        
        # Limit capital allocated
        max_capital_allowed = portfolio_value * c_pct
        if available_tier_capital is not None:
            max_capital_allowed = min(max_capital_allowed, available_tier_capital)

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
    def __init__(self, trail_trigger_pct: float = 0.03):
        super().__init__(
            name="EvaluateActivePosition",
            description="Evaluates active position performance to determine if trailing stop-loss should be raised or if position should be sold."
        )
        self.trail_trigger_pct = trail_trigger_pct

    def execute(self, symbol: str, entry_price: float, current_price: float, current_stop: float, atr: float, momentum_is_strong: bool, trail_trigger_pct: float = None) -> Dict[str, Any]:
        return_pct = (current_price - entry_price) / entry_price
        trigger_pct = trail_trigger_pct if trail_trigger_pct is not None else self.trail_trigger_pct
        
        verdict = "HOLD"
        new_stop = current_stop
        rationale = "Position is performing within normal bounds."

        # Exit if trailing stop triggered
        if current_price <= current_stop:
            return {"action": "SELL", "new_stop": 0.0, "rationale": f"Stop loss triggered at ${current_stop:.2f}"}

        # Dynamic stop adjustment after trigger threshold return
        if return_pct >= trigger_pct:
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
