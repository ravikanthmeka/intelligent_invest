import unittest
from src.agents.specialized import RiskAgent

class TestRiskAgent(unittest.TestCase):
    def setUp(self):
        # Initialize RiskAgent with standard parameters
        self.risk_agent = RiskAgent(max_positions=5, max_cap_pct=0.20, risk_pct=0.01)

    def test_position_sizing_standard(self):
        """
        Verify position size is correctly calculated with 1% portfolio risk.
        Portfolio: $100,000. Risk 1% = $1,000.
        Entry: $100. ATR: $2. Stop loss = 3 * ATR = $6 below entry -> $94 (within 5-7% boundary).
        Quantity = $1000 / $6 = 166.
        Capital allocated = 166 * 100 = $16,600 (less than 20% limit of $20,000).
        """
        portfolio_val = 100000.0
        entry_price = 100.0
        atr = 2.0  # 3 * 2 = 6, stop loss is $94 (6% stop loss)
        
        sizing = self.risk_agent.calculate_position_size(portfolio_val, entry_price, atr)
        
        self.assertEqual(sizing["quantity"], 166)
        self.assertEqual(sizing["stop_loss_price"], 94.0)
        self.assertEqual(sizing["capital_required"], 16600.0)
        self.assertLessEqual(sizing["capital_pct_of_portfolio"], 20.0)

    def test_position_sizing_capital_cap_exceeded(self):
        """
        Verify position size is reduced when capital requirement exceeds 20% of portfolio.
        Portfolio: $100,000. Risk 1% = $1,000.
        Entry: $100. ATR: $0.5. 3 * ATR = $1.5 -> stop loss $98.5.
        However, stop loss is bounded by 5-7% rule. Entry * 0.95 = $95.0.
        So stop loss is set to $95.0 (5% stop loss).
        Quantity = $1,000 / $5.0 = 200 shares.
        Capital required = 200 * $100 = $20,000 (exactly 20% limit).
        
        If we make ATR even smaller, e.g. $0.2:
        Stop loss becomes $95.0 (5% boundary).
        Quantity from risk: $1,000 / $5.0 = 200 shares.
        Capital required = 200 * $100 = $20,000.
        
        Let's try a case where the risk distance is very narrow, e.g. if we had no stop-loss boundaries:
        If stop loss was $98.0 (2% risk), Quantity = $1000 / $2 = 500.
        Capital required = 500 * $100 = $50,000 (exceeds 20% limit of $20,000).
        With 20% cap: Quantity should be reduced to 200 shares.
        Our ATR bound forces stop-loss to at least 5% ($95), which keeps capital under 20% naturally.
        Let's test if the capital cap is applied correctly when we bypass the ATR bound or force a tight stop.
        """
        # Let's test with a larger portfolio or smaller risk distance.
        # Say portfolio is $1,000,000. Risk 1% = $10,000.
        # Entry = $100. Stop-loss = $95 (5% boundary).
        # Quantity = $10,000 / $5.0 = 2000.
        # Capital required = 2000 * 100 = $200,000 (exactly 20% cap).
        # If we set risk_pct to 2% (max risk $20,000):
        self.risk_agent.risk_pct = 0.02
        portfolio_val = 100000.0
        entry_price = 100.0
        atr = 2.0 # 3 * 2 = 6, stop-loss $94 (6%)
        # Risk amount = 2% of $100,000 = $2,000.
        # Quantity based on risk = $2,000 / $6 = 333 shares.
        # Capital required = 333 * $100 = $33,300 (exceeds 20% limit of $20,000).
        # Capital cap should reduce quantity to $20,000 / $100 = 200 shares.
        
        sizing = self.risk_agent.calculate_position_size(portfolio_val, entry_price, atr)
        
        self.assertEqual(sizing["quantity"], 200)
        self.assertEqual(sizing["capital_required"], 20000.0)
        self.assertEqual(sizing["capital_pct_of_portfolio"], 20.0)

    def test_evaluate_active_position_stop_triggered(self):
        """
        Verify that a position is liquidated if current price goes below stop loss.
        """
        decision = self.risk_agent.evaluate_active_position(
            symbol="AAPL",
            entry_price=100.0,
            current_price=93.5,
            current_stop=94.0,
            atr=2.0,
            momentum_is_strong=False
        )
        self.assertEqual(decision["action"], "SELL")
        self.assertIn("Stop loss triggered", decision["rationale"])

    def test_evaluate_active_position_hold_under_threshold(self):
        """
        Verify position is held normally if return is positive but below 3%.
        """
        decision = self.risk_agent.evaluate_active_position(
            symbol="AAPL",
            entry_price=100.0,
            current_price=102.0,
            current_stop=94.0,
            atr=2.0,
            momentum_is_strong=False
        )
        self.assertEqual(decision["action"], "HOLD")
        self.assertEqual(decision["new_stop"], 94.0)

    def test_evaluate_active_position_raise_stop_loss(self):
        """
        Verify that stop-loss is raised when return >= 3% and momentum is strong.
        Entry: $100. Current: $105 (5% return).
        ATR: $2. Trailing stop = $105 - 2*ATR = $101.
        Since $101 > old stop ($94) and entry ($100), new stop should be $101.
        """
        decision = self.risk_agent.evaluate_active_position(
            symbol="AAPL",
            entry_price=100.0,
            current_price=105.0,
            current_stop=94.0,
            atr=2.0,
            momentum_is_strong=True
        )
        self.assertEqual(decision["action"], "HOLD_RAISE_STOP")
        self.assertEqual(decision["new_stop"], 101.0)
        self.assertIn("Raised stop-loss", decision["rationale"])

    def test_evaluate_active_position_take_profit_weak_momentum(self):
        """
        Verify position is sold (take profit) when return >= 3% and momentum is weak.
        """
        decision = self.risk_agent.evaluate_active_position(
            symbol="AAPL",
            entry_price=100.0,
            current_price=105.0,
            current_stop=94.0,
            atr=2.0,
            momentum_is_strong=False
        )
        self.assertEqual(decision["action"], "SELL")
        self.assertIn("Target return hit with weakening momentum", decision["rationale"])

    def test_position_sizing_dynamic_bounds(self):
        """
        Verify position sizing respects dynamic min/max stop-loss percentages.
        Set min_stop_loss_pct to 10% and max_stop_loss_pct to 15%.
        At ATR = 2.0, default stop loss is $94.0 (6% stop loss).
        This should be bounded by min_stop_loss_pct (10%) to $90.0.
        """
        dynamic_agent = RiskAgent(
            max_positions=5, max_cap_pct=0.20, risk_pct=0.01,
            min_stop_loss_pct=0.10, max_stop_loss_pct=0.15
        )
        portfolio_val = 100000.0
        entry_price = 100.0
        atr = 2.0
        
        sizing = dynamic_agent.calculate_position_size(portfolio_val, entry_price, atr)
        
        # Stop loss should be forced to 10% -> 90.0
        self.assertEqual(sizing["stop_loss_price"], 90.0)
        self.assertEqual(sizing["quantity"], 100) # $1000 risk / $10 risk distance = 100 shares

    def test_evaluate_active_position_dynamic_trail_trigger(self):
        """
        Verify active position evaluation respects dynamic trail trigger thresholds.
        Set trail_trigger_pct to 10%.
        At return of 5% (current: $105, entry: $100), it should hold and not raise stop
        since return is below the 10% threshold.
        """
        dynamic_agent = RiskAgent(
            max_positions=5, max_cap_pct=0.20, risk_pct=0.01,
            trail_trigger_pct=0.10
        )
        decision = dynamic_agent.evaluate_active_position(
            symbol="AAPL",
            entry_price=100.0,
            current_price=105.0,
            current_stop=94.0,
            atr=2.0,
            momentum_is_strong=True
        )
        # return of 5% is less than 10% trigger, so action must be HOLD and stop loss unchanged
        self.assertEqual(decision["action"], "HOLD")
        self.assertEqual(decision["new_stop"], 94.0)

if __name__ == "__main__":
    unittest.main()
