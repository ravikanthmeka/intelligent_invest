import os
import sys
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
    PortfolioManagerAgent
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
    
                    # A. Earnings Shield Check
                    passed_shield, reason = news_agent.check_earnings_shield(symbol)
                    if not passed_shield:
                        logger.info(f"Skipping {symbol}: Earnings shield active ({reason})")
                        continue
    
                    # B. News Sentiment Check
                    news_analysis = news_agent.analyze_news(symbol, learnings_feedback=learnings_feedback)
                    logger.info(f"News Verdict for {symbol}: {news_analysis['verdict']} | Score: {news_analysis['sentiment_score']}/10")
                    if news_analysis["verdict"] == "NEGATIVE":
                        logger.info(f"Skipping {symbol}: Negative news sentiment.")
                        continue
    
                    # C. Technical Analysis Check
                    tech_analysis = tech_agent.analyze(symbol, cand, learnings_feedback=learnings_feedback)
                    logger.info(f"Technical Verdict for {symbol}: {tech_analysis['verdict']} | Score: {tech_analysis['score']}/10")
                    if tech_analysis["verdict"] != "BULLISH":
                        logger.info(f"Skipping {symbol}: Technical setup not bullish.")
                        continue
    
                    # D. Fundamental Analysis Check
                    fund_analysis = fund_agent.analyze(symbol, learnings_feedback=learnings_feedback)
                    logger.info(f"Fundamental Verdict for {symbol}: {fund_analysis['verdict']} | Score: {fund_analysis['score']}/10")
                    if fund_analysis["verdict"] == "UNFAVORABLE":
                        logger.info(f"Skipping {symbol}: Unfavorable fundamentals.")
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
                                "news_score": news_analysis.get("sentiment_score", 5.0),
                                "news_verdict": news_analysis.get("verdict", "NEUTRAL"),
                                "tech_score": tech_analysis.get("score", 5.0),
                                "tech_verdict": tech_analysis.get("verdict", "BULLISH"),
                                "fund_score": fund_analysis.get("score", 5.0),
                                "fund_verdict": fund_analysis.get("verdict", "FAVORABLE")
                            }
                        }
                        slots_available -= 1
                        available_tier_cap -= sizing["capital_required"]

            # Save state after scans and executions
            state["active_trades"] = active_trades
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
