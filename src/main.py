import os
import sys
# Ensure project root is in sys.path so 'src' module imports resolve correctly
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import yaml
import json
import asyncio
import logging
from src.considerations import ConsiderationsTracker
import yfinance as yf
from datetime import datetime
import pytz
from typing import Dict, Any
from dotenv import load_dotenv
from src.llm import LLMClient
from src.broker import BrokerAgent
from src.agents.specialized import (
    MarketScannerAgent,
    TechnicalAgent,
    FundamentalAgent,
    NewsAgent,
    RiskAgent,
    PortfolioManagerAgent,
    GrowthAgent,
    MacroEconomicsAgent,
    GlobalSectorRotationAgent,
    QualitativeResearchAgent,
    HistoricalAnalogAgent,
    OptionsFlowAgent,
    InsiderTradingAgent,
    RetailSentimentAgent,
    DividendIncomeAgent,
    CorrelationAgent,
    VolatilityArbitrageAgent,
    EarningsCatalystAgent,
    PortfolioHedgingAgent,
    MergerArbitrageAgent,
    OptionsWheelAgent,
    BrainstormingAgent
)
from src.notifications import NotificationClient

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("trading_system.log")
    ]
)
logger = logging.getLogger("TradingSystemMain")

STATE_FILE = "trading_state.json"

def load_state() -> Dict[str, Any]:
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error reading state file: {e}")
    return {"active_trades": {}}

def save_state(state: Dict[str, Any]):
    try:
        with open(STATE_FILE, "w") as f:
            json.dump(state, f, indent=4)
    except Exception as e:
        logger.error(f"Error writing state file: {e}")

def compile_learnings_feedback(state: Dict[str, Any]) -> str:
    completed = state.get("completed_trades", [])
    if not completed:
        return ""
    
    successful = [t for t in completed if t.get("realized_pnl", 0) > 0]
    failed = [t for t in completed if t.get("realized_pnl", 0) <= 0]
    
    feedback = f"Total Completed Trades: {len(completed)} ({len(successful)} wins, {len(failed)} losses)\n"
    if successful:
        symbols = [t['symbol'] for t in successful[-5:]]
        feedback += f"- Recent Profitable Tickers: {', '.join(symbols)}\n"
    if failed:
        symbols = [t['symbol'] for t in failed[-5:]]
        feedback += f"- Recent Losing/Stopped-out Tickers: {', '.join(symbols)}\n"
    
    if successful:
        avg_tech_win = sum(t.get("analysis", {}).get("tech_score", 5.0) for t in successful) / len(successful)
        avg_fund_win = sum(t.get("analysis", {}).get("fund_score", 5.0) for t in successful) / len(successful)
        feedback += f"- Successful Trades Avg Scores: Tech: {avg_tech_win:.1f}/10, Fund: {avg_fund_win:.1f}/10\n"
    if failed:
        avg_tech_loss = sum(t.get("analysis", {}).get("tech_score", 5.0) for t in failed) / len(failed)
        avg_fund_loss = sum(t.get("analysis", {}).get("fund_score", 5.0) for t in failed) / len(failed)
        feedback += f"- Failed Trades Avg Scores: Tech: {avg_tech_loss:.1f}/10, Fund: {avg_fund_loss:.1f}/10\n"
        
    return feedback

def is_within_execution_window(windows: list) -> bool:
    if not windows:
        return True
    
    tz = pytz.timezone('US/Eastern')
    now = datetime.now(tz)
    current_time_str = now.strftime("%H:%M")
    
    for window in windows:
        start_str, end_str = window.split('-')
        if start_str <= current_time_str <= end_str:
            return True
    return False

async def run_trading_cycle(config: Dict[str, Any], dry_run: bool):
    logger.info("=== Starting Trading Cycle ===")
    
    # 0. Load state and compile learnings
    state = load_state()
    learnings_feedback = compile_learnings_feedback(state)
    if learnings_feedback:
        logger.info(f"Loaded past learnings feedback:\n{learnings_feedback}")
    
    # 1. Initialize LLM Client and Agents
    llm = LLMClient(
        provider=config.get("llm", {}).get("provider"),
        model=config.get("llm", {}).get("model")
    )
    
    scanner = MarketScannerAgent(
        tickers=config.get("watchlist", []),
        llm=llm,
        tier_rules=config.get("tier_rules", {}),
        learnings_feedback=learnings_feedback,
        dynamic_market_scanning=config.get("trading", {}).get("dynamic_market_scanning", True),
        blacklist=config.get("blacklist", [])
    )
    tech_agent = TechnicalAgent(llm=llm)
    fund_agent = FundamentalAgent(llm=llm)
    growth_agent = GrowthAgent(llm=llm)
    news_agent = NewsAgent(llm=llm)
    macro_agent = MacroEconomicsAgent(llm=llm)
    sector_agent = GlobalSectorRotationAgent(llm=llm)
    qual_agent = QualitativeResearchAgent(llm=llm)
    hist_agent = HistoricalAnalogAgent(llm=llm)
    options_agent = OptionsFlowAgent(llm=llm)
    insider_agent = InsiderTradingAgent(llm=llm)
    retail_agent = RetailSentimentAgent(llm=llm)
    dividend_agent = DividendIncomeAgent(llm=llm)
    corr_agent = CorrelationAgent(llm=llm)
    vol_arb_agent = VolatilityArbitrageAgent(llm=llm)
    earnings_agent = EarningsCatalystAgent(llm=llm)
    hedge_agent = PortfolioHedgingAgent(llm=llm)
    merger_arb_agent = MergerArbitrageAgent(llm=llm)
    wheel_agent = OptionsWheelAgent(llm=llm)
    brainstorming_agent = BrainstormingAgent(llm=llm)
    notification_client = NotificationClient()
    
    risk_agent = RiskAgent(
        max_positions=config.get("risk", {}).get("max_positions", 5),
        max_cap_pct=config.get("risk", {}).get("max_capital_pct", 0.20),
        risk_pct=config.get("risk", {}).get("risk_per_trade_pct", 0.01),
        min_stop_loss_pct=config.get("risk", {}).get("min_stop_loss_pct", 0.05),
        max_stop_loss_pct=config.get("risk", {}).get("max_stop_loss_pct", 0.07),
        trail_trigger_pct=config.get("risk", {}).get("trail_trigger_pct", 0.03),
        size_by_capital=config.get("risk", {}).get("size_by_capital", False)
    )

    
    pm = PortfolioManagerAgent(
        llm=llm,
        scanner=scanner,
        technical=tech_agent,
        fundamental=fund_agent,
        news=news_agent,
        risk=risk_agent
    )

    # 2. Connect to Broker
    broker = BrokerAgent(
        host=config.get("broker", {}).get("host", "127.0.0.1"),
        port=config.get("broker", {}).get("port", 4002),
        client_id=config.get("broker", {}).get("client_id", 1),
        dry_run=dry_run
    )
    
    connected = await broker.connect()
    if not connected:
        logger.error("Failed to connect to Broker. Aborting cycle.")
        return

    try:
        # 2.5 Macro & Sector Rotation Analysis
        logger.info("Evaluating Macroeconomic Risk Posture...")
        macro_result = macro_agent.evaluate_market()
        macro_posture = macro_result.get("posture", "NEUTRAL")
        macro_multiplier = macro_result.get("risk_multiplier", 1.0)
        macro_themes = macro_result.get("suggested_themes", [])
        logger.info(f"Macro Posture: {macro_posture} | Risk Multiplier: {macro_multiplier} | Themes: {macro_themes}")

        # 2.6 Dynamic Brainstorming Notification
        last_brainstorm = state.get("last_brainstorm_date", "")
        today_str = datetime.now().strftime("%Y-%m-%d")
        if last_brainstorm != today_str:
            logger.info("Executing daily macro brainstorming...")
            try:
                # We pass the formatted macro output to the brainstorming agent
                import json
                macro_data_str = json.dumps(macro_result, indent=2)
                brainstorm_report = brainstorming_agent.brainstorm(macro_data_str)
                
                # Send the notification
                notification_client.send_brainstorm_alert("Daily Macro & Strategy Brainstorm", brainstorm_report)
                
                state["last_brainstorm_date"] = today_str
                state["latest_brainstorm_report"] = brainstorm_report
            except Exception as e:
                logger.error(f"Failed to execute daily brainstorm: {e}")

        logger.info("Evaluating Global Sector Rotation...")
        sector_result = sector_agent.evaluate_sectors()
        top_sectors = sector_result.get("top_sectors", [])
        logger.info(f"Top Sectors: {top_sectors}")

        # Apply Macro Risk Multiplier
        risk_agent.max_cap_pct *= macro_multiplier
        risk_agent.risk_pct *= macro_multiplier

        # Load local trade tracking state
        active_trades = state.get("active_trades", {})

        # 3. Get current portfolio details
        portfolio = await broker.get_portfolio_value()
        net_liq = portfolio["net_liquidation"]
        cash = portfolio["cash"]
        logger.info(f"Portfolio Net Liquidation: ${net_liq:,.2f} | Cash: ${cash:,.2f}")
        
        state["net_liquidation"] = net_liq
        state["cash"] = cash

        # Portfolio Hedging Evaluation
        active_exposure_pct = (net_liq - cash) / net_liq if net_liq > 0 else 0.0
        hedge_decision = hedge_agent.evaluate(macro_posture, active_exposure_pct)
        logger.info(f"Hedge Evaluation: {hedge_decision}")
        state["hedge_status"] = hedge_decision

        # Fetch actual broker positions
        broker_positions = await broker.get_positions()
        logger.info(f"Found {len(broker_positions)} active positions in broker account.")

        # Sync local state with actual broker positions (remove closed trades)
        broker_stock_positions = [p for p in broker_positions if p.get("sec_type") == "STK"]
        broker_option_positions = [p for p in broker_positions if p.get("sec_type") == "OPT"]
        
        broker_stocks = {pos["symbol"] for pos in broker_stock_positions}
        broker_options = {pos["symbol"] for pos in broker_option_positions}
        pending_symbols = {sym for sym, sec in await broker.get_pending_symbols() if sec == "STK"}
        active_broker_symbols = broker_stocks.union(pending_symbols)
        
        for symbol in list(active_trades.keys()):
            if symbol not in active_broker_symbols:
                logger.info(f"Removing {symbol} from tracking state (no longer active in broker portfolio).")
                # Archive the stop loss hit
                trade_info = active_trades[symbol]
                entry_price = trade_info.get("entry_price", 1.0)
                exit_price = trade_info.get("stop_loss_price", entry_price * 0.94)
                qty = trade_info.get("quantity", 0)
                pnl = (exit_price - entry_price) * qty
                ret_pct = (exit_price - entry_price) / entry_price if entry_price else 0.0
                
                completed_trade = {
                    "symbol": symbol,
                    "risk_tier": trade_info.get("risk_tier", "moderate"),
                    "quantity": qty,
                    "entry_price": entry_price,
                    "exit_price": exit_price,
                    "initial_capital": trade_info.get("initial_capital", 0.0),
                    "purchased_at": trade_info.get("purchased_at", ""),
                    "sold_at": datetime.now().isoformat(),
                    "realized_pnl": pnl,
                    "return_pct": ret_pct,
                    "exit_reason": "Stop loss triggered (broker execution)",
                    "analysis": trade_info.get("analysis", {})
                }
                if "completed_trades" not in state:
                    state["completed_trades"] = []
                state["completed_trades"].append(completed_trade)
                del active_trades[symbol]

        # 4. Evaluate existing positions (Trailing Stops / Profit Targets)
        for pos in broker_stock_positions:
            symbol = pos["symbol"]
            current_price = pos["market_price"]
            avg_cost = pos["average_cost"]
            shares = pos["shares"]
            unrealized_pnl = pos["unrealized_pnl"]
            return_pct = pos["unrealized_pnl_pct"]

            logger.info(f"Evaluating {symbol}: {shares} shares | Avg Cost: ${avg_cost:.2f} | Current: ${current_price:.2f} | Return: {return_pct*100:.2f}%")

            # Determine entry price and active stop loss from local state or fallback
            trade_info = active_trades.get(symbol, {})
            entry_price = trade_info.get("entry_price", avg_cost)
            current_stop = trade_info.get("stop_loss_price", avg_cost * 0.94)  # Default 6% stop loss fallback

            # Fetch ATR for trailing calculations
            ticker_obj = yf.Ticker(symbol)
            hist = ticker_obj.history(period="1mo")
            atr = 1.0  # Fallback
            if len(hist) >= 14:
                from src.skills.market_data import CalculateIndicatorsSkill
                hist = CalculateIndicatorsSkill().execute(hist)
                atr = hist['ATR'].iloc[-1]

            # Check if profit threshold reached to evaluate winner momentum
            momentum_is_strong = False
            if return_pct >= risk_agent.trail_trigger_pct: # Dynamic return threshold
                logger.info(f"{symbol} has gained {return_pct*100:.1f}%. Checking momentum...")
                momentum_is_strong = pm.evaluate_winner_momentum(symbol, current_price, atr)
                logger.info(f"Momentum evaluation result for {symbol}: {'STRONG' if momentum_is_strong else 'WEAK'}")

            # Risk assessment for existing trade
            decision = risk_agent.evaluate_active_position(
                symbol=symbol,
                entry_price=entry_price,
                current_price=current_price,
                current_stop=current_stop,
                atr=atr,
                momentum_is_strong=momentum_is_strong
            )

            action = decision["action"]
            logger.info(f"Risk Agent action for {symbol}: {action} | {decision['rationale']}")

            if action == "SELL":
                logger.info(f"Liquidating position in {symbol}...")
                success = await broker.execute_sell_all(symbol)
                if success and symbol in active_trades:
                    # Move to completed_trades
                    trade_info = active_trades[symbol]
                    completed_trade = {
                        "symbol": symbol,
                        "risk_tier": trade_info.get("risk_tier", "moderate"),
                        "quantity": trade_info.get("quantity", 0),
                        "entry_price": trade_info.get("entry_price", avg_cost),
                        "exit_price": current_price,
                        "initial_capital": trade_info.get("initial_capital", 0.0),
                        "purchased_at": trade_info.get("purchased_at", ""),
                        "sold_at": datetime.now().isoformat(),
                        "realized_pnl": unrealized_pnl,
                        "return_pct": return_pct,
                        "exit_reason": decision.get("rationale", "Stop loss / profit target liquidation"),
                        "analysis": trade_info.get("analysis", {})
                    }
                    if "completed_trades" not in state:
                        state["completed_trades"] = []
                    state["completed_trades"].append(completed_trade)
                    del active_trades[symbol]
            elif action == "HOLD_RAISE_STOP":
                new_stop = decision["new_stop"]
                if new_stop > current_stop:
                    logger.info(f"Raising stop loss for {symbol} to ${new_stop:.2f}")
                    success = await broker.update_stop_loss(symbol, new_stop)
                    if success:
                        if symbol not in active_trades:
                            active_trades[symbol] = {
                                "symbol": symbol,
                                "risk_tier": "moderate",
                                "quantity": shares,
                                "entry_price": avg_cost,
                                "stop_loss_price": current_stop,
                                "initial_capital": avg_cost * shares,
                                "purchased_at": datetime.now().isoformat(),
                                "analysis": {}
                            }
                        active_trades[symbol]["stop_loss_price"] = new_stop
                        active_trades[symbol]["updated_at"] = datetime.now().isoformat()

        # Save state after adjustments
        state["active_trades"] = active_trades
        save_state(state)

        # --- 4b. Evaluate Speculative Options (Profit Targets / Stop Loss) ---
        active_opts = state.get("active_options", {})
        for opt_key in list(active_opts.keys()):
            opt_info = active_opts[opt_key]
            symbol = opt_info["symbol"]
            expiration = opt_info["expiration"]
            strike = opt_info["strike"]
            right = opt_info["right"]
            
            ib_exp = expiration.replace("-", "")
            pos = next((p for p in broker_option_positions if p["symbol"] == symbol and p["contract"].lastTradeDateOrContractMonth == ib_exp and p["contract"].strike == strike and p["contract"].right == right), None)
            
            if not pos:
                logger.info(f"Removing speculative option {opt_key} (no longer active in broker portfolio).")
                completed_trade = opt_info.copy()
                completed_trade["status"] = "Closed"
                completed_trade["closed_at"] = datetime.now().isoformat()
                state.setdefault("completed_trades", []).append(completed_trade)
                del active_opts[opt_key]
                continue
                
            current_price = pos["market_price"]
            entry_price = opt_info["entry_price"]
            unrealized_pct = (current_price - entry_price) / entry_price if entry_price else 0.0
            
            logger.info(f"Evaluating Option {opt_key} | Entry: ${entry_price:.2f} | Current: ${current_price:.2f} | Return: {unrealized_pct*100:.2f}%")
            
            if unrealized_pct >= 0.50 or unrealized_pct <= -0.30:
                reason = "Profit Target Reached" if unrealized_pct >= 0.50 else "Stop Loss Hit"
                logger.info(f"Closing speculative option {opt_key} ({reason}: {unrealized_pct:.1%})")
                order_id = await broker.execute_option_sell(
                    symbol=symbol,
                    expiration=expiration,
                    strike=strike,
                    right=right,
                    quantity=opt_info["quantity"]
                )
                if order_id:
                    completed_trade = opt_info.copy()
                    completed_trade["status"] = reason
                    completed_trade["closed_at"] = datetime.now().isoformat()
                    completed_trade["exit_price"] = current_price
                    completed_trade["realized_pnl"] = (current_price - entry_price) * opt_info["quantity"] * 100
                    state.setdefault("completed_trades", []).append(completed_trade)
                    del active_opts[opt_key]
                    
        state["active_options"] = active_opts
        save_state(state)

        # --- 4c. Evaluate Wheel Portfolio (Assignment & Phase 2) ---
        wheel_portfolio = state.get("wheel_portfolio", {})
        for wheel_key in list(wheel_portfolio.keys()):
            wheel_info = wheel_portfolio[wheel_key]
            phase = wheel_info["phase"]
            symbol = wheel_info["symbol"]
            
            if phase == "CSP":
                expiration = wheel_info["expiration"]
                strike = wheel_info["strike"]
                ib_exp = expiration.replace("-", "")
                
                pos = next((p for p in broker_option_positions if p["symbol"] == symbol and p["contract"].lastTradeDateOrContractMonth == ib_exp and p["contract"].strike == strike and p["contract"].right == "P"), None)
                
                if not pos:
                    stock_pos = next((p for p in broker_stock_positions if p["symbol"] == symbol and p["shares"] >= 100), None)
                    if stock_pos:
                        logger.info(f"Wheel Strategy {symbol}: CSP assigned. Transitioning to Phase 2 (Covered Call).")
                        wheel_info["phase"] = "CC"
                        wheel_info["assignment_price"] = strike
                        wheel_info["assigned_at"] = datetime.now().isoformat()
                        if "collateral_locked" in wheel_info:
                            del wheel_info["collateral_locked"]
                    else:
                        logger.info(f"Wheel Strategy {symbol}: CSP closed/expired without assignment. Releasing capital.")
                        completed_trade = wheel_info.copy()
                        completed_trade["status"] = "Expired Worthless / Closed"
                        completed_trade["closed_at"] = datetime.now().isoformat()
                        state.setdefault("completed_trades", []).append(completed_trade)
                        del wheel_portfolio[wheel_key]
                        
            elif phase == "CC":
                stock_pos = next((p for p in broker_stock_positions if p["symbol"] == symbol and p["shares"] >= 100), None)
                if not stock_pos:
                    logger.info(f"Wheel Strategy {symbol}: Stock called away. Strategy complete.")
                    completed_trade = wheel_info.copy()
                    completed_trade["status"] = "Called Away"
                    completed_trade["closed_at"] = datetime.now().isoformat()
                    state.setdefault("completed_trades", []).append(completed_trade)
                    del wheel_portfolio[wheel_key]
                    
        state["wheel_portfolio"] = wheel_portfolio
        save_state(state)
        # 5. Scan for new entries if we have empty slots
        active_positions_count = len(active_trades)
        max_positions = config.get("risk", {}).get("max_positions", 5)
        
        # Load rules configurations
        rules_cfg = config.get("rules", {})
        min_fund = rules_cfg.get("min_fundamental_score", 5.0)
        min_tech = rules_cfg.get("min_technical_score", 7.0)
        min_news = rules_cfg.get("min_news_score", 5.0)
        earnings_days = rules_cfg.get("earnings_shield_days", 3)
        
        # Load growth reinvestment rules
        growth_rules = rules_cfg.get("growth_reinvestment_rules", {})
        growth_agent_enabled = growth_rules.get("enabled", True)
        min_growth_score = growth_rules.get("min_growth_score", 6.5)
        min_rnd_intensity = growth_rules.get("min_rnd_intensity_pct", 10.0) / 100.0
        min_growth_rev = growth_rules.get("min_revenue_growth_pct", 15.0) / 100.0
        
        evaluations = []
        
        # Check execution windows and VIX before scanning
        execution_windows = config.get("scheduler", {}).get("execution_windows", [])
        in_window = is_within_execution_window(execution_windows)
        
        max_vix = config.get("risk", {}).get("max_vix", 25.0)
        vix_val = 0.0
        try:
            vix_ticker = yf.Ticker("^VIX")
            vix_hist = vix_ticker.history(period="1d")
            if not vix_hist.empty:
                vix_val = vix_hist['Close'].iloc[-1]
        except Exception as e:
            logger.warning(f"Could not fetch VIX: {e}")
            
        if not in_window:
            logger.info("Outside configured execution windows. Skipping new candidate scan.")
        elif vix_val > max_vix:
            logger.warning(f"VIX is {vix_val:.2f}, above max threshold of {max_vix}. Skipping new candidate scan.")
        elif active_positions_count >= max_positions:
            logger.info(f"Portfolio is at max position limit ({active_positions_count}/{max_positions}). Skipping scanner.")
        else:
            slots_available = max_positions - active_positions_count
            logger.info(f"Scanning for candidates to fill {slots_available} available slots across risk tiers...")
            
            # Load allocation percentages
            alloc = config.get("allocation", {"high_risk_pct": 0.30, "moderate_risk_pct": 0.40, "low_risk_pct": 0.25, "penny_risk_pct": 0.05})
            
            # --- 0. ARBITRAGE PRIORITY SCAN ---
            logger.info("--- Starting Arbitrage Priority Scan ---")
            watchlist = config.get("watchlist", [])
            moderate_pct = alloc.get("moderate_risk_pct", 0.40)
            target_arb_cap = net_liq * moderate_pct
            deployed_mod_cap = sum(details.get("initial_capital", 0.0) for details in active_trades.values() if details.get("risk_tier", "moderate") == "moderate")
            available_arb_cap = target_arb_cap - deployed_mod_cap
            
            if available_arb_cap > 500:
                for symbol in watchlist:
                    if symbol in active_trades or slots_available <= 0:
                        continue
                        
                    try:
                        ticker_obj = yf.Ticker(symbol)
                        hist = ticker_obj.history(period="1d")
                        if hist.empty:
                            continue
                        current_price = hist['Close'].iloc[-1]
                    except Exception:
                        continue
                        
                    arb_analysis = merger_arb_agent.analyze(symbol, current_price)
                    if arb_analysis.get("is_actionable"):
                        logger.warning(f"!!! ARBITRAGE OPPORTUNITY FOUND for {symbol} !!!")
                        logger.info(f"Deal Price: ${arb_analysis.get('deal_price')}, Current: ${current_price}, Spread: {arb_analysis.get('spread_pct', 0)*100:.1f}%")
                        logger.info(f"Rationale: {arb_analysis.get('rationale')}")
                        
                        sizing = risk_agent.calculate_position_size(
                            portfolio_value=net_liq,
                            entry_price=current_price,
                            atr=current_price * 0.02, # Synthetic ATR for tight risk
                            available_tier_capital=available_arb_cap,
                            min_stop_loss_pct=0.03, # Very tight stop loss for arbitrage
                            max_stop_loss_pct=0.05,
                            confidence_score=9.0 # Arbitrage implies high confidence
                        )
                        
                        qty = sizing["quantity"]
                        if qty > 0:
                            order_id = await broker.execute_buy(symbol, qty, sizing["stop_loss_price"])
                            if order_id:
                                active_trades[symbol] = {
                                    "entry_price": current_price,
                                    "stop_loss_price": sizing["stop_loss_price"],
                                    "quantity": qty,
                                    "initial_capital": sizing["capital_required"],
                                    "purchased_at": datetime.now().isoformat(),
                                    "order_id": order_id,
                                    "risk_tier": "moderate", # Borrows from moderate
                                    "analysis": {
                                        "fund_verdict": "MERGER_ARBITRAGE",
                                        "arb_spread_pct": arb_analysis.get("spread_pct"),
                                        "deal_price": arb_analysis.get("deal_price")
                                    }
                                }
                                slots_available -= 1
                                available_arb_cap -= sizing["capital_required"]
                                logger.info(f"Successfully executed priority arbitrage buy for {symbol}.")
            

            for tier, tier_pct in [("high", alloc.get("high_risk_pct", 0.30)), 
                                   ("moderate", alloc.get("moderate_risk_pct", 0.40)), 
                                   ("low", alloc.get("low_risk_pct", 0.25)),
                                   ("penny", alloc.get("penny_risk_pct", 0.05))]:
                
                # Check if we still have portfolio slots
                active_positions_count = len(active_trades)
                opportunity_hunt_mode = False
                if active_positions_count >= max_positions:
                    logger.info("Portfolio at max capacity. Entering Opportunity Hunt mode (only swapping for +1.0 score candidates).")
                    opportunity_hunt_mode = True
                
                slots_available = max_positions - active_positions_count
                
                # Calculate available capital for this tier
                target_tier_cap = net_liq * tier_pct
                deployed_tier_cap = sum(details.get("initial_capital", 0.0) 
                                        for details in active_trades.values() 
                                        if details.get("risk_tier", "moderate") == tier)
                available_tier_cap = target_tier_cap - deployed_tier_cap
                
                if available_tier_cap <= 0 and not opportunity_hunt_mode:
                    logger.info(f"No available capital for '{tier}' risk tier (Target: ${target_tier_cap:,.2f}, Deployed: ${deployed_tier_cap:,.2f}). Skipping.")
                    continue
                
                logger.info(f"Scanning for '{tier}' risk candidates with available capital: ${available_tier_cap:,.2f}...")
                
                candidates = scanner.scan_tier(tier)
                
                for cand in candidates:
                    symbol = cand["symbol"]
                    
                    # Filter out blacklisted tickers
                    blacklist = config.get("blacklist", [])
                    if symbol in blacklist:
                        logger.info(f"Skipping {symbol}: Ticker is in the blacklist.")
                        continue
                        
                    if symbol in active_trades:
                        continue  # Already in portfolio
                        
                    # Filter out recently traded tickers (7 day cooldown)
                    recently_traded = False
                    completed_trades = state.get("completed_trades", [])
                    for trade in reversed(completed_trades):
                        if trade.get("symbol") == symbol:
                            sold_at_str = trade.get("sold_at")
                            if sold_at_str:
                                try:
                                    sold_at = datetime.fromisoformat(sold_at_str)
                                    if (datetime.now() - sold_at).days < 7:
                                        recently_traded = True
                                        break
                                except Exception:
                                    pass
                    if recently_traded:
                        logger.info(f"Skipping {symbol}: Traded recently (cooldown active).")
                        continue
                    
                    if slots_available <= 0 and not opportunity_hunt_mode:
                        break
                    
                    logger.info(f"Evaluating candidate {symbol} for '{tier}' risk tier...")
    
                    passed_shield = True
                    reason = None
                    news_score = None
                    news_verd = None
                    tech_score = None
                    tech_verd = None
                    fund_score = None
                    fund_verd = None
                    status = "Passed"
                    
                    is_growth_reinvestment_play = False
                    rnd_intensity_pct = 0.0
                    revenue_growth_pct = 0.0
                    net_margin_pct = 0.0
                    growth_score = None
                    growth_verd = None
                    
                    # A. Earnings Shield Check
                    passed_shield, reason = news_agent.check_earnings_shield(symbol, days_range=earnings_days)
                    if not passed_shield:
                        logger.info(f"Skipping {symbol}: Earnings shield active ({reason})")
                        status = f"Skipped: Earnings Shield ({reason})"
                    else:
                        # B. News Sentiment Check
                        news_analysis = news_agent.analyze_news(symbol, learnings_feedback=learnings_feedback)
                        news_score = news_analysis.get("sentiment_score", 5.0)
                        news_verd = news_analysis.get("verdict", "NEUTRAL")
                        logger.info(f"News Verdict for {symbol}: {news_verd} | Score: {news_score}/10")
                        
                        if news_verd == "NEGATIVE" or news_score < min_news:
                            logger.info(f"Skipping {symbol}: News sentiment insufficient.")
                            status = f"Skipped: News Sentiment ({news_verd}, Score: {news_score})"
                        else:
                            # C. Technical Analysis Check
                            tech_analysis = tech_agent.analyze(symbol, cand, learnings_feedback=learnings_feedback)
                            tech_score = tech_analysis.get("score", 5.0)
                            tech_verd = tech_analysis.get("verdict", "NEUTRAL")
                            logger.info(f"Technical Verdict for {symbol}: {tech_verd} | Score: {tech_score}/10")
                            
                            if tech_verd == "BEARISH" or tech_score < min_tech:
                                logger.info(f"Skipping {symbol}: Technical setup insufficient.")
                                status = f"Skipped: Technical Setup ({tech_verd}, Score: {tech_score})"
                            else:
                                # D. Fundamental Analysis Check
                                fund_analysis = fund_agent.analyze(symbol, learnings_feedback=learnings_feedback)
                                fund_score = fund_analysis.get("score", 5.0)
                                fund_verd = fund_analysis.get("verdict", "NEUTRAL")
                                logger.info(f"Fundamental Verdict for {symbol}: {fund_verd} | Score: {fund_score}/10")
                                
                                if fund_verd == "UNFAVORABLE" or fund_score < min_fund:
                                    # Traditional fundamentals failed. Check if this is a valid Growth/R&D play for High/Moderate risk tiers
                                    if tier in ["high", "moderate"] and growth_agent_enabled:
                                        logger.info(f"Traditional fundamentals unfavorable for {symbol}. Evaluating as Growth/R&D Reinvestment play...")
                                        growth_analysis = growth_agent.analyze(symbol, learnings_feedback=learnings_feedback)
                                        
                                        growth_score = growth_analysis.get("score", 5.0)
                                        growth_verd = growth_analysis.get("verdict", "NEUTRAL")
                                        rnd_intensity_pct = growth_analysis.get("rnd_intensity_pct", 0.0)
                                        revenue_growth_pct = growth_analysis.get("revenue_growth_pct", 0.0)
                                        net_margin_pct = growth_analysis.get("net_margin_pct", 0.0)
                                        
                                        logger.info(f"Growth Agent Verdict for {symbol}: {growth_verd} | Score: {growth_score}/10 | R&D Intensity: {rnd_intensity_pct:.1f}% | Revenue Growth: {revenue_growth_pct:.1f}%")
                                        
                                        
                                        if (growth_verd == "FAVORABLE" and 
                                            growth_score >= min_growth_score and 
                                            (rnd_intensity_pct / 100.0) >= min_rnd_intensity and 
                                            (revenue_growth_pct / 100.0) >= min_growth_rev):
                                            
                                            logger.info(f"Overriding traditional fundamental filter for {symbol}: Qualified as high-reinvestment growth play.")
                                            is_growth_reinvestment_play = True
                                
                                # E. Qualitative Research Check
                                min_qual = rules_cfg.get("min_qualitative_score", 6.0)
                                qual_analysis = qual_agent.analyze(symbol)
                                qual_score = qual_analysis.get("score", 5.0)
                                qual_verd = qual_analysis.get("verdict", "NEUTRAL")
                                logger.info(f"Qualitative Verdict for {symbol}: {qual_verd} | Score: {qual_score}/10")
                                
                                is_qual_play = False
                                if qual_verd in ["HIGH_QUALITY", "STRONG"] and qual_score >= 8.0:
                                    logger.info(f"Overriding traditional fundamental filter for {symbol}: Qualified as high-quality qualitative play.")
                                    is_qual_play = True
                                
                                if (fund_verd == "UNFAVORABLE" or fund_score < min_fund) and not (is_growth_reinvestment_play or is_qual_play):
                                    logger.info(f"Skipping {symbol}: Unfavorable fundamentals.")
                                    status = f"Skipped: Fundamental Strength ({fund_verd}, Score: {fund_score})"
                                elif qual_verd == "POOR" or qual_score < min_qual:
                                    logger.info(f"Skipping {symbol}: Qualitative strength insufficient.")
                                    status = f"Skipped: Qualitative Research ({qual_verd}, Score: {qual_score})"
                                else:
                                        # F. Historical Analog Check
                                        min_hist = rules_cfg.get("min_historical_score", 6.0)
                                        hist_analysis = hist_agent.analyze(
                                            symbol=symbol,
                                            current_price=cand["close"],
                                            rsi=cand["rsi"],
                                            sma_50=cand["sma_50"],
                                            sma_200=cand["sma_200"]
                                        )
                                        hist_score = hist_analysis.get("score", 5.0)
                                        hist_verd = hist_analysis.get("verdict", "NEUTRAL")
                                        logger.info(f"Historical Analog Verdict for {symbol}: {hist_verd} | Score: {hist_score}/10")
                                        
                                        if hist_verd == "BEARISH" or hist_score < min_hist:
                                            logger.info(f"Skipping {symbol}: Historical analog insufficient.")
                                            status = f"Skipped: Historical Analog ({hist_verd}, Score: {hist_score})"
                                        else:
                                            # G. Correlation Check
                                            max_corr = rules_cfg.get("max_correlation_threshold", 0.75)
                                            corr_analysis = corr_agent.analyze(symbol, list(active_trades.keys()), max_threshold=max_corr)
                                            corr_verd = corr_analysis.get("verdict", "UNCORRELATED")
                                            logger.info(f"Correlation Verdict for {symbol}: {corr_verd}")
                                            
                                            if corr_verd == "HIGHLY_CORRELATED":
                                                logger.info(f"Skipping {symbol}: Highly correlated with active portfolio.")
                                                status = f"Skipped: Correlation ({corr_verd})"
                                            else:
                                                # H. Options Flow Check
                                                min_options = rules_cfg.get("min_options_score", 5.0)
                                                opt_analysis = options_agent.analyze(symbol)
                                                opt_score = opt_analysis.get("score", 5.0)
                                                opt_verd = opt_analysis.get("verdict", "NEUTRAL")
                                                logger.info(f"Options Flow Verdict for {symbol}: {opt_verd} | Score: {opt_score}/10")
                                                
                                                if opt_verd == "BEARISH" or opt_score < min_options:
                                                    logger.info(f"Skipping {symbol}: Options flow insufficient.")
                                                    status = f"Skipped: Options Flow ({opt_verd}, Score: {opt_score})"
                                                else:
                                                    # I. Insider Trading Check
                                                    min_insider = rules_cfg.get("min_insider_score", 5.0)
                                                    ins_analysis = insider_agent.analyze(symbol)
                                                    ins_score = ins_analysis.get("score", 5.0)
                                                    ins_verd = ins_analysis.get("verdict", "NEUTRAL")
                                                    logger.info(f"Insider Verdict for {symbol}: {ins_verd} | Score: {ins_score}/10")
                                                    
                                                    if ins_verd == "BEARISH" or ins_score < min_insider:
                                                        logger.info(f"Skipping {symbol}: Insider trading insufficient.")
                                                        status = f"Skipped: Insider Trading ({ins_verd}, Score: {ins_score})"
                                                    else:
                                                        # J. Tier-Specific Checks
                                                        if tier == "penny":
                                                            retail_analysis = retail_agent.analyze(symbol, cand.get("volume", 0), cand.get("avg_volume", 1))
                                                            ret_verd = retail_analysis.get("verdict", "NEUTRAL")
                                                            logger.info(f"Retail Sentiment Verdict for {symbol}: {ret_verd}")
                                                            if ret_verd == "LOW_MOMENTUM":
                                                                logger.info(f"Skipping {symbol}: Insufficient retail momentum for penny stock.")
                                                                status = f"Skipped: Retail Momentum ({ret_verd})"
                                                                
                                                        if status.startswith("Passed") and tier == "low":
                                                            min_div = rules_cfg.get("min_dividend_yield", 0.02)
                                                            div_analysis = dividend_agent.analyze(symbol)
                                                            div_verd = div_analysis.get("verdict", "NO_YIELD")
                                                            yield_pct = div_analysis.get("dividend_yield", 0.0)
                                                            logger.info(f"Dividend Verdict for {symbol}: {div_verd}")
                                                            
                                                            if div_verd in ["NO_YIELD", "YIELD_TRAP"] or yield_pct < min_div:
                                                                logger.info(f"Skipping {symbol}: Dividend yield insufficient for low-risk tier.")
                                                                status = f"Skipped: Dividend Yield ({div_verd})"
                    # Options Evaluation removed - moved to separate loop
                    eval_entry = {
                        "symbol": symbol,
                        "tier": tier,
                        "status": status,
                        "news_score": news_score,
                        "tech_score": tech_score,
                        "fund_score": fund_score,
                        "growth_score": growth_score,
                        "timestamp": datetime.now().isoformat()
                    }
                    evaluations.append(eval_entry)
                    
                    scores = [s for s in [news_score, tech_score, fund_score, growth_score] if s is not None]
                    confidence_score = sum(scores) / len(scores) if scores else 5.0
                    ConsiderationsTracker.log(symbol, f"Swing ({tier.capitalize()})", confidence_score, status)
                    
                    if status != "Passed":
                        continue
                        
                    # --- OPPORTUNITY HUNT SWAP LOGIC ---
                    if opportunity_hunt_mode:
                        # Find the weakest active trade (lowest unrealized_pnl_pct) in this tier
                        weakest_symbol = None
                        lowest_return = float('inf')
                        weakest_trade_info = None
                        
                        # Use broker_stock_positions to get accurate return
                        for p in broker_stock_positions:
                            sym = p["symbol"]
                            if sym in active_trades and active_trades[sym].get("risk_tier", "moderate") == tier:
                                ret = p.get("unrealized_pnl_pct", 0.0)
                                if ret < lowest_return:
                                    lowest_return = ret
                                    weakest_symbol = sym
                                    weakest_trade_info = active_trades[sym]
                        
                        if not weakest_symbol:
                            logger.info(f"Opportunity Hunt: Could not find an active trade in tier '{tier}' to swap. Passing.")
                            continue
                            
                        # Calculate original scores for the weakest link
                        w_analysis = weakest_trade_info.get("analysis", {})
                        w_scores = [w_analysis.get(k) for k in ["news_score", "tech_score", "fund_score", "growth_score"] if w_analysis.get(k) is not None]
                        w_confidence = sum(w_scores) / len(w_scores) if w_scores else 5.0
                        
                        # Compare against candidate
                        if confidence_score >= (w_confidence + 1.0):
                            logger.info(f"Opportunity Hunt Triggered! Candidate {symbol} ({confidence_score:.2f}) is > 1.0 better than weakest link {weakest_symbol} ({w_confidence:.2f}, ret: {lowest_return*100:.2f}%). Swapping!")
                            
                            # Execute Swap Liquidate
                            success = await broker.execute_sell_all(weakest_symbol)
                            if success:
                                # Archive the trade
                                completed_trade = {
                                    "symbol": weakest_symbol,
                                    "risk_tier": weakest_trade_info.get("risk_tier", "moderate"),
                                    "quantity": weakest_trade_info.get("quantity", 0),
                                    "entry_price": weakest_trade_info.get("entry_price", 1.0),
                                    "exit_price": 1.0, # Just a placeholder since we don't have fill price instantly
                                    "initial_capital": weakest_trade_info.get("initial_capital", 0.0),
                                    "purchased_at": weakest_trade_info.get("purchased_at", ""),
                                    "sold_at": datetime.now().isoformat(),
                                    "realized_pnl": lowest_return * weakest_trade_info.get("initial_capital", 0.0), # Approximate
                                    "return_pct": lowest_return,
                                    "exit_reason": f"Opportunity Cost: Swapped for superior candidate {symbol}",
                                    "analysis": w_analysis
                                }
                                if "completed_trades" not in state:
                                    state["completed_trades"] = []
                                state["completed_trades"].append(completed_trade)
                                
                                # Add the freed capital to the available tier capital
                                available_tier_cap += weakest_trade_info.get("initial_capital", 0.0)
                                slots_available += 1
                                del active_trades[weakest_symbol]
                            else:
                                logger.error(f"Failed to sell {weakest_symbol} during opportunity swap. Skipping {symbol}.")
                                continue
                        else:
                            logger.info(f"Opportunity Hunt: Candidate {symbol} ({confidence_score:.2f}) not sufficiently better than weakest link {weakest_symbol} ({w_confidence:.2f}). No swap.")
                            continue
    
                    # E. Position Sizing & Entry Execution
                    min_sl_val = 0.10 if tier == "penny" else None
                    max_sl_val = 0.20 if tier == "penny" else None
                    
                    scores = [s for s in [news_score, tech_score, fund_score, growth_score] if s is not None]
                    confidence_score = sum(scores) / len(scores) if scores else 5.0
                    
                    sizing = risk_agent.calculate_position_size(
                        portfolio_value=net_liq,
                        entry_price=cand["close"],
                        atr=cand["atr"],
                        available_tier_capital=available_tier_cap,
                        min_stop_loss_pct=min_sl_val,
                        max_stop_loss_pct=max_sl_val
                    )
    
                    qty = sizing["quantity"]
                    if qty <= 0:
                        logger.warning(f"Sizing calculation returned quantity 0 for {symbol}. Skipping.")
                        eval_entry["status"] = "Skipped: Quantity Sized to 0"
                        continue
    
                    logger.info(f"Candidate {symbol} passed all filters. Buying {qty} shares (Capital Required: ${sizing['capital_required']:.2f}, Stop Loss: ${sizing['stop_loss_price']:.2f})")
    
                    # Execute Bracket Buy Order
                    order_id = await broker.execute_buy(symbol, qty, sizing["stop_loss_price"])
                    if order_id:
                        active_trades[symbol] = {
                            "entry_price": cand["close"],
                            "stop_loss_price": sizing["stop_loss_price"],
                            "quantity": qty,
                            "initial_capital": sizing["capital_required"],
                            "purchased_at": datetime.now().isoformat(),
                            "order_id": order_id,
                            "risk_tier": tier,
                            "analysis": {
                                "news_score": news_score,
                                "news_verdict": news_verd,
                                "tech_score": tech_score,
                                "tech_verdict": tech_verd,
                                "fund_score": fund_score if not is_growth_reinvestment_play else growth_score,
                                "fund_verdict": fund_verd if not (is_growth_reinvestment_play or ('is_qual_play' in locals() and is_qual_play)) else (f"GROWTH_PLAY ({growth_verd})" if is_growth_reinvestment_play else f"QUAL_PLAY ({qual_verd})"),
                                "qual_score": qual_score,
                                "hist_score": hist_score,
                                "rnd_intensity_pct": rnd_intensity_pct,
                                "revenue_growth_pct": revenue_growth_pct,
                                "net_margin_pct": net_margin_pct
                            }
                        }
                        
                        slots_available -= 1
                        available_tier_cap -= sizing["capital_required"]
                        eval_entry["status"] = "Purchased (Growth Play)" if is_growth_reinvestment_play else ("Purchased (Qual Play)" if 'is_qual_play' in locals() and is_qual_play else "Purchased")

            ## --- 3. OPTIONS PORTFOLIO SCAN ---
            options_pct = config.get("allocation", {}).get("options_pct", 0.20)
            target_opt_cap = net_liq * options_pct
            active_opts = state.get("active_options", {})
            deployed_opt_cap = sum(details.get("initial_capital", 0.0) for details in active_opts.values())
            available_opt_cap = target_opt_cap - deployed_opt_cap

            if available_opt_cap > 200:
                logger.info(f"--- Starting Options Portfolio Scan (Available Cap: ${available_opt_cap:,.2f}) ---")
                
                ## --- 3a. Options Wheel Strategy ---
                wheel_portfolio = state.get("wheel_portfolio", {})
                watchlist = config.get("watchlist", [])
                
                for symbol in watchlist:
                    if available_opt_cap <= 200:
                        break
                        
                    # Check if we already have an active wheel trade for this symbol
                    already_wheeling = any(p["symbol"] == symbol for p in wheel_portfolio.values())
                    if already_wheeling:
                        continue
                        
                    logger.info(f"Evaluating {symbol} for Options Wheel Strategy (Phase 1: CSP)...")
                    try:
                        current_price = yf.Ticker(symbol).history(period="1d")['Close'].iloc[-1]
                        
                        # Ensure we have enough capital to Cash Secure the Put (approx 100 shares)
                        if available_opt_cap < (current_price * 100 * 0.8): # roughly 80% check before exact strike
                            logger.info(f"Skipping {symbol} for CSP: Insufficient options capital (${available_opt_cap:,.2f}).")
                            continue
                            
                        wheel_eval = wheel_agent.analyze(symbol, current_price, phase="CSP")
                        if wheel_eval.get("verdict") == "SELECTED":
                            opt_data = wheel_eval["option"]
                            strike = opt_data["strike"]
                            required_capital = strike * 100
                            
                            if available_opt_cap >= required_capital:
                                opt_price = opt_data.get("bid", 0) or opt_data.get("lastPrice", 0)
                                logger.info(f"Executing CSP for {symbol}: SELL 1 contract of {opt_data['expiration']} ${strike}P at ~${opt_price}")
                                opt_order_id = await broker.execute_option_sell(
                                    symbol=symbol,
                                    expiration=opt_data["expiration"],
                                    strike=strike,
                                    right=opt_data["right"],
                                    quantity=1
                                )
                                if opt_order_id:
                                    wheel_key = f"{symbol}_CSP_{opt_data['expiration']}_{strike}"
                                    wheel_portfolio[wheel_key] = {
                                        "symbol": symbol,
                                        "phase": "CSP",
                                        "expiration": opt_data["expiration"],
                                        "strike": strike,
                                        "quantity": 1,
                                        "entry_premium": opt_price,
                                        "collateral_locked": required_capital,
                                        "purchased_at": datetime.now().isoformat(),
                                        "order_id": opt_order_id
                                    }
                                    state["wheel_portfolio"] = wheel_portfolio
                                    available_opt_cap -= required_capital
                    except Exception as e:
                        logger.error(f"Error evaluating Wheel for {symbol}: {e}")
                
                ## --- 3b. Speculative Options ---
                # Retrieve options universe using High and Moderate Risk tier candidates for momentum
                options_candidates = scanner.scan_tier("high") + scanner.scan_tier("moderate")
                
                # Fetch threshold from config
                min_options_catalyst_score = config.get("risk", {}).get("min_options_catalyst_score", 5.0)
                
                for cand in options_candidates:
                    symbol = cand["symbol"]
                    
                    if available_opt_cap <= 200:
                        break
                        
                    # Filter out blacklisted tickers
                    blacklist = config.get("blacklist", [])
                    if symbol in blacklist:
                        continue
                        
                    logger.info(f"Evaluating {symbol} for standalone speculative options...")
                    
                    eval_entry = {
                        "symbol": symbol,
                        "risk_tier": "options",
                        "timestamp": datetime.now().isoformat(),
                        "status": "Evaluated for Options",
                        "analysis": {}
                    }
                    
                    # 1. News Catalyst Check
                    news_analysis = news_agent.analyze_news(symbol, learnings_feedback=learnings_feedback)
                    news_score = news_analysis.get("sentiment_score", 5.0)
                    eval_entry["analysis"]["news_score"] = news_score
                    
                    if news_score < min_options_catalyst_score:
                        eval_entry["status"] = f"Skipped: News Catalyst too low ({news_score} < {min_options_catalyst_score})"
                        evaluations.append(eval_entry)
                        ConsiderationsTracker.log(symbol, "Options", news_score, eval_entry["status"])
                        continue # Needs a strong catalyst
                        
                    # 2. Technical Momentum Check
                    tech_analysis = tech_agent.analyze(symbol, cand, learnings_feedback=learnings_feedback)
                    tech_verd = tech_analysis.get("verdict", "NEUTRAL")
                    eval_entry["analysis"]["tech_verdict"] = tech_verd
                    
                    # 3. Options Flow Check
                    opt_analysis = options_agent.analyze(symbol)
                    opt_verd = opt_analysis.get("verdict", "NEUTRAL")
                    eval_entry["analysis"]["opt_verdict"] = opt_verd
                    
                    # 4. Earnings Catalyst Check
                    earnings_analysis = earnings_agent.analyze(symbol)
                    earn_verd = earnings_analysis.get("verdict", "NEUTRAL")
                    eval_entry["analysis"]["earnings_verdict"] = earn_verd
                    
                    # Determine Bias
                    direction_bias = None
                    if tech_verd == "BULLISH" and opt_verd == "BULLISH":
                        direction_bias = "bullish"
                    elif earn_verd == "BULLISH_CATALYST":
                        direction_bias = "bullish"
                    elif tech_verd == "BEARISH" and opt_verd == "BEARISH":
                        direction_bias = "bearish"
                    elif earn_verd == "BEARISH_CATALYST":
                        direction_bias = "bearish"
                        
                    if direction_bias:
                        # 5. Volatility Check (crucial for debit strategies)
                        vol_arb_analysis = vol_arb_agent.analyze(symbol, direction_bias=direction_bias.upper())
                        vol_verd = vol_arb_analysis.get("verdict", "FAVORABLE_IV")
                        eval_entry["analysis"]["volatility_verdict"] = vol_verd
                        
                        if vol_verd == "IV_TOO_HIGH":
                            logger.info(f"Skipping options for {symbol}: IV is too high for debit strategies.")
                            eval_entry["status"] = "Skipped: IV Too High"
                        else:
                            logger.info(f"Candidate {symbol} selected for options... Evaluating Speculative {direction_bias.capitalize()} Option...")
                            from src.skills.market_data import SelectSpeculativeOptionSkill, FetchUnusualOptionsFlowSkill
                            from src.skills.analysis import UnusualOptionsAnalysisSkill
                            
                            try:
                                flow_data = FetchUnusualOptionsFlowSkill().execute(symbol)
                                flow_analysis = UnusualOptionsAnalysisSkill(llm_client).execute(symbol, flow_data, cand["close"])
                                eval_entry["analysis"]["unusual_options_flow"] = flow_analysis
                                logger.info(f"Unusual options flow for {symbol}: {flow_analysis.get('verdict')} - {flow_analysis.get('rationale')}")
                            except Exception as e:
                                logger.warning(f"Failed unusual options flow analysis: {e}")
                                
                            opt_skill = SelectSpeculativeOptionSkill()
                            opt_data = opt_skill.execute(symbol, cand["close"], bias=direction_bias)

                            if opt_data and "expiration" in opt_data:
                                eval_entry["analysis"]["considered_options"] = opt_data.get("considered_options", [])
                                opt_price = opt_data.get("ask", 0) or opt_data.get("lastPrice", 0)
                                if opt_price > 0:
                                    # Risk max 25% of options cap per trade or $2000, whichever is smaller
                                    trade_cap = min(available_opt_cap * 0.25, 2000.0)
                                    qty_opts = int(trade_cap / (opt_price * 100))
                                    if qty_opts > 0:
                                        logger.info(f"Executing Speculative {direction_bias.capitalize()} Option for {symbol}: {qty_opts} contracts of {opt_data['expiration']} ${opt_data['strike']} at ~${opt_price}")
                                        opt_order_id = await broker.execute_option_buy(
                                            symbol=symbol,
                                            expiration=opt_data["expiration"],
                                            strike=opt_data["strike"],
                                            right=opt_data["right"],
                                            quantity=qty_opts
                                        )
                                        if opt_order_id:
                                            eval_entry["status"] = f"Purchased ({direction_bias.capitalize()} Option)"
                                            opt_key = f"{symbol}_{opt_data['expiration']}_{opt_data['strike']}{opt_data['right']}"
                                            active_opts[opt_key] = {
                                                "symbol": symbol,
                                                "expiration": opt_data["expiration"],
                                                "strike": opt_data["strike"],
                                                "right": opt_data["right"],
                                                "quantity": qty_opts,
                                                "entry_price": opt_price,
                                                "initial_capital": qty_opts * opt_price * 100,
                                                "purchased_at": datetime.now().isoformat(),
                                                "order_id": opt_order_id,
                                                "analysis": eval_entry["analysis"]
                                            }
                                            state["active_options"] = active_opts
                                            available_opt_cap -= (qty_opts * opt_price * 100)
                    else:
                        eval_entry["status"] = "Skipped: No Clear Directional Bias"
                        
                    evaluations.append(eval_entry)
                    opt_score = eval_entry.get("analysis", {}).get("news_score", 5.0)
                    ConsiderationsTracker.log(symbol, "Options", opt_score, eval_entry["status"])

            # Save state after scans and executions
            state["active_trades"] = active_trades
            if "candidate_evaluations" not in state:
                state["candidate_evaluations"] = []
            state["candidate_evaluations"] = (evaluations + state["candidate_evaluations"])[:50]
            save_state(state)

    except Exception as e:
        logger.error(f"Error in trading cycle execution: {e}", exc_info=True)
    finally:
        await broker.disconnect()
        logger.info("=== Trading Cycle Complete ===")

if __name__ == "__main__":
    # Load environment variables
    load_dotenv()
    
    # Read config
    config_path = "config.yaml"
    if not os.path.exists(config_path):
        logger.error("config.yaml not found. Please create one.")
        sys.exit(1)
        
    with open(config_path, "r") as f:
        config = yaml.safe_load(f)
        
    dry_run = config.get("trading", {}).get("dry_run", True)
    
    # Run the cycle once (intended for execution via cron or systemd timer)
    asyncio.run(run_trading_cycle(config, dry_run))
