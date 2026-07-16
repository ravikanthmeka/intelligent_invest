import logging
import yfinance as yf
import pandas as pd
from typing import List, Dict, Any, Tuple, Optional
from src.llm import LLMClient
from src.agents.base import Agent
from src.skills.market_data import CalculateIndicatorsSkill, FetchEarningsCalendarSkill, FetchRecentNewsSkill
from src.skills.analysis import TechnicalAnalysisSkill, FundamentalAnalysisSkill, NewsSentimentSkill
from src.skills.risk_management import CalculatePositionSizeSkill, EvaluateActivePositionSkill

logger = logging.getLogger("SpecializedAgents")

class MarketScannerAgent(Agent):
    def __init__(self, tickers: List[str]):
        super().__init__(name="MarketScannerAgent", role="Scan watchlist for bullish trading candidates.")
        self.tickers = tickers
        self.register_skill(CalculateIndicatorsSkill())

    def scan(self) -> List[Dict[str, Any]]:
        logger.info(f"Scanning watchlist of {len(self.tickers)} tickers...")
        candidates = []
        calc_skill = self.get_skill("CalculateIndicators")
        
        for symbol in self.tickers:
            try:
                # Fetch 1 year of daily data to compute indicators
                ticker_obj = yf.Ticker(symbol)
                df = ticker_obj.history(period="1y", interval="1d")
                if len(df) < 50:
                    continue
                
                df = calc_skill.execute(df)
                last_row = df.iloc[-1]
                
                close = last_row['Close']
                sma_50 = last_row['SMA_50']
                sma_200 = last_row['SMA_200']
                rsi = last_row['RSI']
                
                # Check for basic bullish criteria
                if (close > sma_50 and sma_50 > sma_200 and rsi > 45 and rsi < 70):
                    candidates.append({
                        "symbol": symbol,
                        "close": close,
                        "rsi": rsi,
                        "sma_50": sma_50,
                        "sma_200": sma_200,
                        "atr": last_row['ATR'],
                        "volume_spike": last_row['Volume'] > (df['Volume'].rolling(20).mean().iloc[-1] * 1.2)
                    })
            except Exception as e:
                logger.error(f"Error scanning {symbol}: {e}")
                
        # Sort candidates by a blend of momentum (RSI) and volume spike
        candidates.sort(key=lambda x: x['rsi'], reverse=True)
        logger.info(f"Scan complete. Found {len(candidates)} bullish candidates.")
        return candidates[:5]  # Return top 5 candidates

class TechnicalAgent(Agent):
    def __init__(self, llm: LLMClient):
        super().__init__(name="TechnicalAgent", role="Analyze and score technical charts of assets.")
        self.llm = llm
        self.register_skill(TechnicalAnalysisSkill(llm))

    def analyze(self, symbol: str, data: Dict[str, Any]) -> Dict[str, Any]:
        tech_skill = self.get_skill("TechnicalAnalysis")
        return tech_skill.execute(symbol, data)

class FundamentalAgent(Agent):
    def __init__(self, llm: LLMClient):
        super().__init__(name="FundamentalAgent", role="Analyze and score company balance sheets and fundamentals.")
        self.llm = llm
        self.register_skill(FundamentalAnalysisSkill(llm))

    def analyze(self, symbol: str) -> Dict[str, Any]:
        fund_skill = self.get_skill("FundamentalAnalysis")
        return fund_skill.execute(symbol)

class NewsAgent(Agent):
    def __init__(self, llm: LLMClient):
        super().__init__(name="NewsAgent", role="Monitor news sentiment and corporate events like earnings.")
        self.llm = llm
        self.register_skill(FetchEarningsCalendarSkill())
        self.register_skill(FetchRecentNewsSkill())
        self.register_skill(NewsSentimentSkill(llm))

    def check_earnings_shield(self, symbol: str) -> Tuple[bool, Optional[str]]:
        shield_skill = self.get_skill("FetchEarningsCalendar")
        return shield_skill.execute(symbol)

    def analyze_news(self, symbol: str) -> Dict[str, Any]:
        fetch_news_skill = self.get_skill("FetchRecentNews")
        news_sentiment_skill = self.get_skill("NewsSentiment")
        
        news_items = fetch_news_skill.execute(symbol)
        return news_sentiment_skill.execute(symbol, news_items)

class RiskAgent(Agent):
    def __init__(self, max_positions: int = 5, max_cap_pct: float = 0.20, risk_pct: float = 0.01, min_stop_loss_pct: float = 0.05, max_stop_loss_pct: float = 0.07, trail_trigger_pct: float = 0.03):
        super().__init__(name="RiskAgent", role="Calculate position sizing, evaluate risk parameters and active position status.")
        self.max_positions = max_positions
        self.max_cap_pct = max_cap_pct
        self.risk_pct = risk_pct
        self.min_stop_loss_pct = min_stop_loss_pct
        self.max_stop_loss_pct = max_stop_loss_pct
        self.trail_trigger_pct = trail_trigger_pct
        
        self.register_skill(CalculatePositionSizeSkill(max_cap_pct=max_cap_pct, risk_pct=risk_pct, min_stop_loss_pct=min_stop_loss_pct, max_stop_loss_pct=max_stop_loss_pct))
        self.register_skill(EvaluateActivePositionSkill(trail_trigger_pct=trail_trigger_pct))

    def calculate_position_size(self, portfolio_value: float, entry_price: float, atr: float) -> Dict[str, Any]:
        size_skill = self.get_skill("CalculatePositionSize")
        return size_skill.execute(
            portfolio_value, 
            entry_price, 
            atr, 
            risk_pct=self.risk_pct, 
            max_cap_pct=self.max_cap_pct,
            min_stop_loss_pct=self.min_stop_loss_pct,
            max_stop_loss_pct=self.max_stop_loss_pct
        )

    def evaluate_active_position(self, symbol: str, entry_price: float, current_price: float, current_stop: float, atr: float, momentum_is_strong: bool) -> Dict[str, Any]:
        eval_skill = self.get_skill("EvaluateActivePosition")
        return eval_skill.execute(
            symbol, 
            entry_price, 
            current_price, 
            current_stop, 
            atr, 
            momentum_is_strong,
            trail_trigger_pct=self.trail_trigger_pct
        )

class PortfolioManagerAgent(Agent):
    def __init__(self, llm: LLMClient, scanner: MarketScannerAgent, technical: TechnicalAgent, fundamental: FundamentalAgent, news: NewsAgent, risk: RiskAgent):
        super().__init__(name="PortfolioManagerAgent", role="Coordinate sub-agents and oversee overall portfolio strategy.")
        self.llm = llm
        self.scanner = scanner
        self.technical = technical
        self.fundamental = fundamental
        self.news = news
        self.risk = risk
        self.register_skill(CalculateIndicatorsSkill())

    def evaluate_winner_momentum(self, symbol: str, current_price: float, atr: float) -> bool:
        try:
            ticker_obj = yf.Ticker(symbol)
            df = ticker_obj.history(period="1mo", interval="1d")
            if len(df) < 10:
                return False
            
            calc_indicators = self.get_skill("CalculateIndicators")
            df = calc_indicators.execute(df)
            last_row = df.iloc[-1]
            
            sma_10 = df['Close'].rolling(10).mean().iloc[-1]
            rsi = last_row['RSI']
            
            prompt = f"""
            Evaluate momentum for winning position '{symbol}':
            - Current Price: ${current_price:.2f}
            - 10-day SMA: ${sma_10:.2f}
            - RSI: {rsi:.1f}
            - ATR: ${atr:.2f}

            Is momentum still strong enough to raise the stop loss and let it run, or should we liquidate and take profit?
            Respond in valid JSON structure:
            {{
                "momentum_is_strong": boolean,
                "rationale": "Brief reason."
            }}
            Do not add any markup or markdown wraps besides the raw JSON.
            """
            response_text = self.llm.call(prompt, system_prompt="You are a professional portfolio manager.")
            clean_text = response_text.replace("```json", "").replace("```", "").strip()
            import json
            result = json.loads(clean_text)
            return result.get("momentum_is_strong", False)
        except Exception as e:
            logger.error(f"Error evaluating momentum for {symbol}: {e}")
            return False
