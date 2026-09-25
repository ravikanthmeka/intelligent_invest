import yfinance as yf
import numpy as np
import pandas as pd
from typing import Dict, Any
from src.skills.base import Skill

class MonteCarloOptionEvaluatorSkill(Skill):
    def __init__(self):
        super().__init__(
            name="MonteCarloOptionEvaluator",
            description="Runs a Monte Carlo simulation using Geometric Brownian Motion to calculate POP and EV of an option."
        )

    def execute(self, symbol: str, current_price: float, strike: float, days_to_expiry: int, right: str, opt_price: float, num_simulations: int = 10000) -> Dict[str, Any]:
        """
        Calculates POP (Probability of Profit) and EV (Expected Value) for an option.
        right: 'C' or 'P'
        """
        try:
            # 1. Fetch 1 year of historical daily data
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period="1y")
            
            if len(hist) < 50:
                return {"error": "Not enough historical data for simulation", "ev": 0, "pop": 0}
                
            # Calculate daily returns
            hist['Returns'] = hist['Close'].pct_change()
            
            # Calculate daily historical volatility (sigma) and drift (mu)
            mu = hist['Returns'].mean()
            sigma = hist['Returns'].std()
            
            # 2. Run Monte Carlo Simulation using Geometric Brownian Motion (GBM)
            # S_t = S_0 * exp((mu - 0.5 * sigma**2) * t + sigma * W_t)
            # Since we only care about the terminal price, t = days_to_expiry
            # W_t is a normal random variable scaled by sqrt(t)
            
            # Pre-calculate drift term for terminal date
            drift_term = (mu - 0.5 * sigma**2) * days_to_expiry
            
            # Generate random shocks for all simulations at terminal date
            # np.random.normal(0, 1, num_simulations) gives standard normal variables
            random_shocks = sigma * np.sqrt(days_to_expiry) * np.random.normal(0, 1, num_simulations)
            
            # Calculate terminal prices
            terminal_prices = current_price * np.exp(drift_term + random_shocks)
            
            # 3. Calculate Option Payoffs at expiration
            if right.upper() == 'C':
                payoffs = np.maximum(0, terminal_prices - strike)
            else:
                payoffs = np.maximum(0, strike - terminal_prices)
                
            # 4. Calculate Net PnL (subtract premium paid)
            # Multiply by 100 because options are 100 shares per contract
            net_pnl = (payoffs - opt_price) * 100
            
            # 5. Calculate POP and EV
            pop = np.sum(net_pnl > 0) / num_simulations
            ev = np.mean(net_pnl)
            
            return {
                "pop": float(pop),
                "ev": float(ev),
                "simulations": num_simulations,
                "mu_daily": float(mu),
                "sigma_daily": float(sigma)
            }
            
        except Exception as e:
            import logging
            logging.error(f"Monte Carlo simulation failed for {symbol}: {e}")
            return {"error": str(e), "ev": 0, "pop": 0}
