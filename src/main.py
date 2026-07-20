import os
import sys
# Ensure project root is in sys.path so 'src' module imports resolve correctly
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import yaml
import json
import asyncio
import logging
import yfinance as yf
from datetime import datetime
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
    GrowthAgent
)

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
        learnings_feedback=learnings_feedback
    )
    tech_agent = TechnicalAgent(llm=llm)
    fund_agent = FundamentalAgent(llm=llm)
    growth_agent = GrowthAgent(llm=llm)
    news_agent = NewsAgent(llm=llm)
    risk_agent = RiskAgent(
        max_positions=config.get("risk", {}).get("max_positions", 5),
        max_cap_pct=config.get("risk", {}).get("max_capital_pct", 0.20),
        risk_pct=config.get("risk", {}).get("risk_per_trade_pct", 0.01),
        min_stop_loss_pct=config.get("risk", {}).get("min_stop_loss_pct", 0.05),
        max_stop_loss_pct=config.get("risk", {}).get("max_stop_loss_pct", 0.07),
        trail_trigger_pct=config.get("risk", {}).get("trail_trigger_pct", 0.03)
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
        # Load local trade tracking state
        active_trades = state.get("active_trades", {})

        # 3. Get current portfolio details
        portfolio = await broker.get_portfolio_value()
        net_liq = portfolio["net_liquidation"]
        cash = portfolio["cash"]
        logger.info(f"Portfolio Net Liquidation: ${net_liq:,.2f} | Cash: ${cash:,.2f}")
        
        state["net_liquidation"] = net_liq
        state["cash"] = cash

        # Fetch actual broker positions
        broker_positions = await broker.get_positions()
        logger.info(f"Found {len(broker_positions)} active positions in broker account.")

        # Sync local state with actual broker positions (remove closed trades)
        broker_symbols = {pos["symbol"] for pos in broker_positions}
        for symbol in list(active_trades.keys()):
            if symbol not in broker_symbols:
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
        for pos in broker_positions:
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
                        active_trades[symbol]["stop_loss_price"] = new_stop
                        active_trades[symbol]["updated_at"] = datetime.now().isoformat()

        # Save state after adjustments
        state["active_trades"] = active_trades
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
        
        if active_positions_count >= max_positions:
            logger.info(f"Portfolio is at max position limit ({active_positions_count}/{max_positions}). Skipping scanner.")
        else:
            slots_available = max_positions - active_positions_count
            logger.info(f"Scanning for candidates to fill {slots_available} available slots across risk tiers...")
            
            # Load allocation percentages
            alloc = config.get("allocation", {"high_risk_pct": 0.30, "moderate_risk_pct": 0.40, "low_risk_pct": 0.30})
            
            for tier, tier_pct in [("high", alloc.get("high_risk_pct", 0.30)), 
                                   ("moderate", alloc.get("moderate_risk_pct", 0.40)), 
                                   ("low", alloc.get("low_risk_pct", 0.30))]:
                
                # Check if we still have portfolio slots
                active_positions_count = len(active_trades)
                if active_positions_count >= max_positions:
                    logger.info("Portfolio reached max position limit. Stopping scan.")
                    break
                
                slots_available = max_positions - active_positions_count
                
                # Calculate available capital for this tier
                target_tier_cap = net_liq * tier_pct
                deployed_tier_cap = sum(details.get("initial_capital", 0.0) 
                                        for details in active_trades.values() 
                                        if details.get("risk_tier", "moderate") == tier)
                available_tier_cap = target_tier_cap - deployed_tier_cap
                
                if available_tier_cap <= 0:
                    logger.info(f"No available capital for '{tier}' risk tier (Target: ${target_tier_cap:,.2f}, Deployed: ${deployed_tier_cap:,.2f}). Skipping.")
                    continue
                
                logger.info(f"Scanning for '{tier}' risk candidates with available capital: ${available_tier_cap:,.2f}...")
                
                candidates = scanner.scan_tier(tier)
                
                for cand in candidates:
                    symbol = cand["symbol"]
                    if symbol in active_trades:
                        continue  # Already in portfolio
                    
                    if slots_available <= 0:
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
                                
                                if (fund_verd == "UNFAVORABLE" or fund_score < min_fund) and not is_growth_reinvestment_play:
                                    logger.info(f"Skipping {symbol}: Unfavorable fundamentals.")
                                    status = f"Skipped: Fundamental Strength ({fund_verd}, Score: {fund_score})"
                    
                    # Log candidate evaluation snapshot
                    eval_entry = {
                        "symbol": symbol,
                        "risk_tier": tier,
                        "timestamp": datetime.now().isoformat(),
                        "status": status if status != "Passed" else ("Passed (Growth Play)" if is_growth_reinvestment_play else "Passed"),
                        "analysis": {
                            "earnings_checked": "PASSED" if passed_shield else "TRIGGERED",
                            "news_score": news_score,
                            "news_verdict": news_verd,
                            "tech_score": tech_score,
                            "tech_verdict": tech_verd,
                            "fund_score": fund_score if not is_growth_reinvestment_play else growth_score,
                            "fund_verdict": fund_verd if not is_growth_reinvestment_play else f"GROWTH_PLAY ({growth_verd})",
                            "growth_evaluated": "YES" if (tier in ["high", "moderate"] and growth_agent_enabled and fund_score is not None and (fund_verd == "UNFAVORABLE" or fund_score < min_fund)) else "NO",
                            "rnd_intensity_pct": rnd_intensity_pct,
                            "revenue_growth_pct": revenue_growth_pct,
                            "net_margin_pct": net_margin_pct
                        }
                    }
                    evaluations.append(eval_entry)
                    
                    if status != "Passed":
                        continue
    
                    # E. Position Sizing & Entry Execution
                    sizing = risk_agent.calculate_position_size(
                        portfolio_value=net_liq,
                        entry_price=cand["close"],
                        atr=cand["atr"],
                        available_tier_capital=available_tier_cap
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
                                "fund_verdict": fund_verd if not is_growth_reinvestment_play else f"GROWTH_PLAY ({growth_verd})",
                                "rnd_intensity_pct": rnd_intensity_pct,
                                "revenue_growth_pct": revenue_growth_pct,
                                "net_margin_pct": net_margin_pct
                            }
                        }
                        slots_available -= 1
                        available_tier_cap -= sizing["capital_required"]
                        eval_entry["status"] = "Purchased (Growth Play)" if is_growth_reinvestment_play else "Purchased"

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
