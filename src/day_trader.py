import os
import sys
import yaml
import json
import asyncio
import logging
import yfinance as yf
from datetime import datetime, time
import pytz
from typing import Dict, Any
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.llm import LLMClient
from src.broker import BrokerAgent
from src.agents.specialized import MarketScannerAgent, TechnicalAgent, NewsAgent
from src.notifications import NotificationClient
from src.considerations import ConsiderationsTracker
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("day_trading.log")
    ]
)
logger = logging.getLogger("DayTrader")

STATE_FILE = "day_trading_state.json"

def load_state() -> Dict[str, Any]:
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error reading state file: {e}")
    return {"active_trades": {}, "completed_trades": [], "net_liquidation": 100000.0, "cash": 100000.0}

def save_state(state: Dict[str, Any]):
    try:
        with open(STATE_FILE, "w") as f:
            json.dump(state, f, indent=4)
    except Exception as e:
        logger.error(f"Error writing state file: {e}")

async def run_day_trading_cycle(config: Dict[str, Any], dry_run: bool):
    logger.info("=== Starting Day Trading Cycle ===")
    state = load_state()
    
    day_trading_cfg = config.get("day_trading", {})
    if not day_trading_cfg.get("enabled", False):
        logger.info("Day trading is disabled in config.")
        return

    # Check EOD Liquidation Time
    tz = pytz.timezone("US/Eastern")
    now_est = datetime.now(tz)
    
    eod_time_str = day_trading_cfg.get("eod_liquidation_time", "15:45")
    eod_time_parts = [int(p) for p in eod_time_str.split(":")]
    eod_time = time(eod_time_parts[0], eod_time_parts[1])
    
    broker = BrokerAgent(
        host=config.get("broker", {}).get("host", "127.0.0.1"),
        port=int(config.get("broker", {}).get("port", 4001)),
        client_id=config.get("broker", {}).get("client_id", 88) + 1, # Use different client ID for Day Trader
        dry_run=dry_run
    )

    if not await broker.connect():
        logger.error("Failed to connect to Broker.")
        return
    
    portfolio_val = await broker.get_portfolio_value()
    net_liq = portfolio_val.get("net_liquidation", state.get("net_liquidation", 100000.0))
    cash = portfolio_val.get("cash", state.get("cash", 100000.0))
    
    # Update State with latest balances
    state["net_liquidation"] = net_liq
    state["cash"] = cash
    
    active_trades = state.get("active_trades", {})
    
    # EOD Liquidation Check
    if now_est.time() >= eod_time:
        logger.info(f"Time is {now_est.time()} >= {eod_time}. Enforcing EOD Liquidation.")
        for symbol, data in list(active_trades.items()):
            logger.info(f"Liquidating {symbol} EOD.")
            if not dry_run:
                await broker.execute_sell(symbol, data["quantity"])
            state["completed_trades"].append({
                "symbol": symbol,
                "exit_time": now_est.isoformat(),
                "reason": "EOD Liquidation"
            })
            del active_trades[symbol]
        save_state(state)
        await broker.disconnect()
        return

    # Intraday scanning logic (simplified for speed)
    llm = LLMClient(
        provider=config.get("llm", {}).get("provider"),
        model=config.get("llm", {}).get("model")
    )
    
    # Fetch VIX to ensure no flash crash
    try:
        vix = yf.Ticker("^VIX").history(period="1d")["Close"].iloc[-1]
        max_vix = config.get("risk", {}).get("max_vix", 25.0)
        if vix > max_vix:
            logger.warning(f"VIX is {vix:.2f} > {max_vix}. Halting new day trades.")
            await broker.disconnect()
            return
    except Exception as e:
        logger.error(f"Error fetching VIX: {e}")
        
    day_trading_pct = config.get("allocation", {}).get("day_trading_pct", 0.20)
    available_day_cap = net_liq * day_trading_pct
    
    logger.info(f"Available Day Trading Capital: ${available_day_cap:.2f}")

    # For day trading, just scan watchlist directly for rapid 5m breakouts
    watchlist = config.get("watchlist", [])
    if not watchlist:
        logger.info("No watchlist tickers available.")
        await broker.disconnect()
        return
        
    tech_agent = TechnicalAgent(llm)
    news_agent = NewsAgent(llm)
    
    min_tech_score = day_trading_cfg.get("min_technical_score", 6.5)
    async def evaluate_symbol(symbol: str):
        if symbol in active_trades:
            return
            
        try:
            # Fetch 5m intraday data using live broker API
            df = await broker.get_historical_data(symbol, duration="1 D", bar_size="5 mins")
            if df.empty or len(df) < 5:
                return
                
            close = df["Close"].iloc[-1]
            
            # --- News Check ---
            news_enabled = day_trading_cfg.get("news_feed", {}).get("enabled", False)
            min_sentiment = day_trading_cfg.get("news_feed", {}).get("min_sentiment_score", 8.5)
            
            has_catalyst = False
            if news_enabled:
                logger.info(f"[{symbol}] Fetching and analyzing news...")
                news_analysis = await asyncio.to_thread(news_agent.analyze_news, symbol)
                news_score = news_analysis.get("score", 5.0)
                if news_score >= min_sentiment:
                    has_catalyst = True
                    logger.info(f"[{symbol}] High catalytic news detected (Score: {news_score}). Bypassing momentum check.")
                        
            # Simple momentum check: is price above 5-period 5m MA?
            ma5 = df["Close"].rolling(5).mean().iloc[-1]
            
            if has_catalyst or close > ma5:
                if not has_catalyst:
                    logger.info(f"[{symbol}] Momentum detected (Close: {close:.2f} > MA5: {ma5:.2f}). Triggering Technical Agent.")
                    
                # We need data dictionary for tech_agent.analyze
                data = {"history": df}
                tech_analysis = await asyncio.to_thread(tech_agent.analyze, symbol, data)
                
                score = tech_analysis.get("score", 5.0)
                required_score = min_tech_score - 1.0 if has_catalyst else min_tech_score
                
                if score >= required_score:
                    # Execute Trade
                    risk_pct = day_trading_cfg.get("risk_per_trade_pct", 0.01)
                    risk_amount = available_day_cap * risk_pct
                    
                    min_sl_pct = day_trading_cfg.get("min_stop_loss_pct", 0.01)
                    stop_loss = close * (1 - min_sl_pct)
                    
                    risk_per_share = close - stop_loss
                    if risk_per_share > 0:
                        qty = int(risk_amount / risk_per_share)
                        
                        if qty > 0:
                            capital_req = qty * close
                            if capital_req <= cash:
                                logger.info(f"Executing Day Trade Buy for {symbol}: {qty} shares @ {close:.2f} (SL: {stop_loss:.2f})")
                                if not dry_run:
                                    order_id = await broker.execute_buy(symbol, qty, stop_loss)
                                    if order_id:
                                        active_trades[symbol] = {
                                            "entry_price": close,
                                            "stop_loss_price": stop_loss,
                                            "quantity": qty,
                                            "initial_capital": capital_req,
                                            "purchased_at": now_est.isoformat(),
                                            "order_id": order_id
                                        }
                                        save_state(state)
                                        ConsiderationsTracker.log(symbol, "Day Trade", score, "Trade Executed")
                                else:
                                    ConsiderationsTracker.log(symbol, "Day Trade", score, "Trade Executed (Dry Run)")
                            else:
                                ConsiderationsTracker.log(symbol, "Day Trade", score, f"Skipped: Insufficient Capital (${capital_req:.2f} > ${cash:.2f})")
                        else:
                            ConsiderationsTracker.log(symbol, "Day Trade", score, "Skipped: Calculated Quantity was 0")
                    else:
                        ConsiderationsTracker.log(symbol, "Day Trade", score, "Skipped: Invalid Risk per Share")
                else:
                    ConsiderationsTracker.log(symbol, "Day Trade", score, f"Skipped: Technical Score too low ({score} < {required_score})")
            else:
                ConsiderationsTracker.log(symbol, "Day Trade", 5.0, f"Skipped: Momentum check failed (Close: {close:.2f} <= MA5: {ma5:.2f})")
                
        except Exception as e:
            logger.error(f"Error evaluating {symbol} for day trading: {e}")

    sem = asyncio.Semaphore(5)
    
    async def sem_evaluate_symbol(symbol: str):
        async with sem:
            await evaluate_symbol(symbol)

    tasks = [sem_evaluate_symbol(symbol) for symbol in watchlist]
    await asyncio.gather(*tasks)

    await broker.disconnect()

if __name__ == "__main__":
    load_dotenv()
    with open("config.yaml", "r") as f:
        cfg = yaml.safe_load(f)
    
    dry = cfg.get("trading", {}).get("dry_run", False)
    asyncio.run(run_day_trading_cycle(cfg, dry))
