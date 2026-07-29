import logging
import yfinance as yf
import pandas as pd
from typing import List, Dict, Any, Tuple, Optional
from src.llm import LLMClient
from src.agents.base import Agent
from src.skills.market_data import CalculateIndicatorsSkill, FetchEarningsCalendarSkill, FetchRecentNewsSkill
from src.skills.analysis import TechnicalAnalysisSkill, FundamentalAnalysisSkill, NewsSentimentSkill, GrowthRnDEvaluationSkill
from src.skills.risk_management import CalculatePositionSizeSkill, EvaluateActivePositionSkill

logger = logging.getLogger("SpecializedAgents")

class MarketScannerAgent(Agent):
    def __init__(self, tickers: List[str], llm: LLMClient = None, tier_rules: Dict[str, Any] = None, learnings_feedback: str = "", dynamic_market_scanning: bool = True, blacklist: List[str] = None):
        super().__init__(name="MarketScannerAgent", role="Scan watchlist or dynamic suggestions for bullish trading candidates.")
        self.tickers = tickers
        self.llm = llm
        self.tier_rules = tier_rules or {}
        self.learnings_feedback = learnings_feedback
        self.dynamic_market_scanning = dynamic_market_scanning
        self.blacklist = blacklist or []
        self.register_skill(CalculateIndicatorsSkill())

    def _fetch_sp500_tickers(self) -> List[str]:
        try:
            import urllib.request
            url = "https://raw.githubusercontent.com/datasets/s-and-p-500-companies/master/data/constituents.csv"
            res = urllib.request.urlopen(url, timeout=5).read().decode('utf-8')
            lines = res.split('\n')
            tickers = [line.split(',')[0].strip().upper() for line in lines[1:] if line]
            # Replace dot with hyphen for Yahoo Finance compatibility (e.g. BRK.B to BRK-B)
            cleaned = []
            for t in tickers:
                t_clean = t.replace(".", "-")
                if t_clean:
                    cleaned.append(t_clean)
            return cleaned
        except Exception as e:
            logger.error(f"Error fetching S&P 500 tickers: {e}")
            return []

    def scan(self) -> List[Dict[str, Any]]:
        return self.scan_tier("moderate")

    def scan_tier(self, risk_tier: str) -> List[Dict[str, Any]]:
        logger.info(f"Generating ticker suggestions for risk tier: {risk_tier}...")
        
        tier_conf = self.tier_rules.get(risk_tier, {})
        guidelines = tier_conf.get("guidelines", "")
        if not guidelines:
            if risk_tier == "high":
                guidelines = "High-beta, high-growth technology, biotech, or emerging stocks with high volatility."
            elif risk_tier == "low":
                guidelines = "Low-beta, defensive stocks, utilities, consumer staples, or high-quality dividend payers."
            else:
                guidelines = "Stable growth stocks, mid-large cap leaders with solid earnings and moderate volatility."

        min_rsi = tier_conf.get("min_rsi", 45)
        max_rsi = tier_conf.get("max_rsi", 70)
        require_trend = tier_conf.get("require_trend", True)

        tickers = []
        if self.llm:
            import random
            learnings_str = f"\nPortfolio learnings from past trades:\n{self.learnings_feedback}\n" if self.learnings_feedback else ""
            
            # Use dynamic market sampling for standard risk tiers if enabled
            if self.dynamic_market_scanning and risk_tier in ["high", "moderate", "low"]:
                sp500_list = self._fetch_sp500_tickers()
                combined_pool = list(set(self.tickers + sp500_list))
                # Filter out blacklisted tickers
                combined_pool = [t for t in combined_pool if t not in self.blacklist]
                
                # Sample 40 tickers
                sampled_tickers = random.sample(combined_pool, min(len(combined_pool), 40))
                logger.info(f"Dynamically sampled 40 broad-market tickers for {risk_tier} screening: {sampled_tickers}")
                
                prompt = f"""
                From the following list of 40 stock tickers, select the 12 most promising tickers that fit the '{risk_tier}' risk profile:
                Tickers: {sampled_tickers}
                
                Guidelines: {guidelines}
                {learnings_str}
                Important: Select candidates that represent the target risk profile. For high/moderate risk tiers, prefer candidates with strong growth potential or high R&D intensity.
                
                Respond in valid JSON structure:
                {{
                    "tickers": ["SYMBOL1", "SYMBOL2", ...]
                }}
                Do not add any markup or markdown wraps besides the raw JSON.
                """
            elif risk_tier == "penny":
                # Special prompt for penny stocks: must be strictly under $5/share
                prompt = f"""
                Suggest a list of 16 US stock ticker symbols that represent the '{risk_tier}' risk/return profile:
                Guidelines: {guidelines}
                {learnings_str}
                Important: Every suggested stock must be a speculative US penny stock trading strictly under $5.00 per share. Prefer companies with high volume, upcoming growth catalysts, and solid emerging business models or research investments.
                Respond in valid JSON structure:
                {{
                    "tickers": ["SYMBOL1", "SYMBOL2", ...]
                }}
                Do not add any markup or markdown wraps besides the raw JSON.
                """
            else:
                prompt = f"""
                Suggest a list of 16 US stock ticker symbols that represent the '{risk_tier}' risk/return profile:
                Guidelines: {guidelines}
                {learnings_str}
                Respond in valid JSON structure:
                {{
                    "tickers": ["SYMBOL1", "SYMBOL2", ...]
                }}
                Do not add any markup or markdown wraps besides the raw JSON.
                """
                
            try:
                response_text = self.llm.call(prompt, system_prompt="You are a professional equity research and portfolio analyst.")
                import json
                clean_text = response_text.replace("```json", "").replace("```", "").strip()
                tickers = json.loads(clean_text).get("tickers", [])
                logger.info(f"LLM selected/suggested tickers for {risk_tier}: {tickers}")
            except Exception as e:
                logger.error(f"Error generating/selecting tickers from LLM for {risk_tier}: {e}")
        
        if not tickers:
            logger.info(f"Falling back to default watchlist for {risk_tier} scan.")
            tickers = self.tickers
            
        candidates = []
        calc_skill = self.get_skill("CalculateIndicators")
        
        for symbol in tickers:
            try:
                ticker_obj = yf.Ticker(symbol)
                df = ticker_obj.history(period="1y", interval="1d")
                if len(df) < 50:
                    continue
                
                df = calc_skill.execute(df)
                last_row = df.iloc[-1]
                
                close = last_row['Close']
                
                # Hard price limit of $5.00 for penny stocks to ensure compliance
                if risk_tier == "penny" and close >= 5.0:
                    continue
                    
                sma_50 = last_row['SMA_50']
                sma_200 = last_row['SMA_200']
                rsi = last_row['RSI']
                
                # Check for dynamic technical criteria
                rsi_ok = (rsi > min_rsi and rsi < max_rsi)
                trend_ok = (not require_trend) or (close > sma_50 and sma_50 > sma_200)
                
                if rsi_ok and trend_ok:
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
                
        candidates.sort(key=lambda x: x['rsi'], reverse=True)
        logger.info(f"Scan complete for {risk_tier}. Found {len(candidates)} bullish candidates.")
        return candidates[:5]

class TechnicalAgent(Agent):
    def __init__(self, llm: LLMClient):
        super().__init__(name="TechnicalAgent", role="Analyze and score technical charts of assets.")
        self.llm = llm
        self.register_skill(TechnicalAnalysisSkill(llm))

    def analyze(self, symbol: str, data: Dict[str, Any], learnings_feedback: str = "") -> Dict[str, Any]:
        tech_skill = self.get_skill("TechnicalAnalysis")
        return tech_skill.execute(symbol, data, learnings_feedback=learnings_feedback)

class FundamentalAgent(Agent):
    def __init__(self, llm: LLMClient):
        super().__init__(name="FundamentalAgent", role="Analyze and score company balance sheets and fundamentals.")
        self.llm = llm
        self.register_skill(FundamentalAnalysisSkill(llm))

    def analyze(self, symbol: str, learnings_feedback: str = "") -> Dict[str, Any]:
        fund_skill = self.get_skill("FundamentalAnalysis")
        return fund_skill.execute(symbol, learnings_feedback=learnings_feedback)

class NewsAgent(Agent):
    def __init__(self, llm: LLMClient):
        super().__init__(name="NewsAgent", role="Monitor news sentiment and corporate events like earnings.")
        self.llm = llm
        self.register_skill(FetchEarningsCalendarSkill())
        self.register_skill(FetchRecentNewsSkill())
        self.register_skill(NewsSentimentSkill(llm))

    def check_earnings_shield(self, symbol: str, days_range: int = 3) -> Tuple[bool, Optional[str]]:
        shield_skill = self.get_skill("FetchEarningsCalendar")
        return shield_skill.execute(symbol, days_range=days_range)

    def analyze_news(self, symbol: str, learnings_feedback: str = "") -> Dict[str, Any]:
        fetch_news_skill = self.get_skill("FetchRecentNews")
        news_sentiment_skill = self.get_skill("NewsSentiment")
        
        news_items = fetch_news_skill.execute(symbol)
        return news_sentiment_skill.execute(symbol, news_items, learnings_feedback=learnings_feedback)

class RiskAgent(Agent):
    def __init__(self, max_positions: int = 5, max_cap_pct: float = 0.20, risk_pct: float = 0.01, min_stop_loss_pct: float = 0.05, max_stop_loss_pct: float = 0.07, trail_trigger_pct: float = 0.03, size_by_capital: bool = False):
        super().__init__(name="RiskAgent", role="Calculate position sizing, evaluate risk parameters and active position status.")
        self.max_positions = max_positions
        self.max_cap_pct = max_cap_pct
        self.risk_pct = risk_pct
        self.min_stop_loss_pct = min_stop_loss_pct
        self.max_stop_loss_pct = max_stop_loss_pct
        self.trail_trigger_pct = trail_trigger_pct
        self.size_by_capital = size_by_capital
        
        self.register_skill(CalculatePositionSizeSkill(max_cap_pct=max_cap_pct, risk_pct=risk_pct, min_stop_loss_pct=min_stop_loss_pct, max_stop_loss_pct=max_stop_loss_pct))
        self.register_skill(EvaluateActivePositionSkill(trail_trigger_pct=trail_trigger_pct))

    def calculate_position_size(self, portfolio_value: float, entry_price: float, atr: float, available_tier_capital: float = None, min_stop_loss_pct: float = None, max_stop_loss_pct: float = None) -> Dict[str, Any]:
        size_skill = self.get_skill("CalculatePositionSize")
        return size_skill.execute(
            portfolio_value, 
            entry_price, 
            atr, 
            risk_pct=self.risk_pct, 
            max_cap_pct=self.max_cap_pct,
            min_stop_loss_pct=min_stop_loss_pct if min_stop_loss_pct is not None else self.min_stop_loss_pct,
            max_stop_loss_pct=max_stop_loss_pct if max_stop_loss_pct is not None else self.max_stop_loss_pct,
            available_tier_capital=available_tier_capital,
            size_by_capital=self.size_by_capital
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

class GrowthAgent(Agent):
    def __init__(self, llm: LLMClient):
        super().__init__(name="GrowthAgent", role="Evaluate companies focusing on future growth through high R&D intensity and revenue scaling despite lower current profits.")
        self.llm = llm
        self.register_skill(GrowthRnDEvaluationSkill(llm))

    def analyze(self, symbol: str, learnings_feedback: str = "") -> Dict[str, Any]:
        growth_skill = self.get_skill("GrowthRnDEvaluation")
        return growth_skill.execute(symbol, learnings_feedback=learnings_feedback)
