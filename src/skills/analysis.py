import json
import logging
import yfinance as yf
from typing import Dict, Any, List
from src.llm import LLMClient
from src.skills.base import Skill

logger = logging.getLogger("AnalysisSkills")

class TechnicalAnalysisSkill(Skill):
    def __init__(self, llm: LLMClient):
        super().__init__(
            name="TechnicalAnalysis",
            description="Evaluates a technical indicator profile for a stock using LLM reasoning and outputs a JSON verdict."
        )
        self.llm = llm

    def execute(self, symbol: str, data: Dict[str, Any]) -> Dict[str, Any]:
        prompt = f"""
        Analyze the following technical indicator profile for stock ticker '{symbol}':
        - Current Price: ${data['close']:.2f}
        - 14-day RSI: {data['rsi']:.1f}
        - 50-day Simple Moving Average (SMA): ${data['sma_50']:.2f}
        - 200-day Simple Moving Average (SMA): ${data['sma_200']:.2f}
        - 14-day Average True Range (ATR): ${data['atr']:.2f}
        - Volume Spike Detected: {data['volume_spike']}

        Provide a verdict. You must respond in a valid JSON structure:
        {{
            "verdict": "BULLISH" | "NEUTRAL" | "BEARISH",
            "score": float (0.0 to 10.0),
            "rationale": "Short analysis of indicators, support levels, and momentum."
        }}
        Do not add any markup or markdown wraps besides the raw JSON.
        """
        try:
            response_text = self.llm.call(prompt, system_prompt="You are a professional quantitative technical analyst.")
            clean_text = response_text.replace("```json", "").replace("```", "").strip()
            return json.loads(clean_text)
        except Exception as e:
            logger.error(f"TechnicalAnalysisSkill failed: {e}")
            return {"verdict": "NEUTRAL", "score": 5.0, "rationale": "Fallback: technical analysis failed."}

class FundamentalAnalysisSkill(Skill):
    def __init__(self, llm: LLMClient):
        super().__init__(
            name="FundamentalAnalysis",
            description="Extracts fundamental data for a stock and uses LLM to score growth, debt, and value properties in JSON."
        )
        self.llm = llm

    def execute(self, symbol: str) -> Dict[str, Any]:
        try:
            ticker_obj = yf.Ticker(symbol)
            info = ticker_obj.info
            
            pe_ratio = info.get("trailingPE", "N/A")
            forward_pe = info.get("forwardPE", "N/A")
            peg_ratio = info.get("pegRatio", "N/A")
            debt_to_equity = info.get("debtToEquity", "N/A")
            rev_growth = info.get("revenueGrowth", "N/A")
            margin = info.get("profitMargins", "N/A")
            fcf = info.get("freeCashflow", "N/A")

            prompt = f"""
            Evaluate the financial fundamentals of company ticker '{symbol}':
            - Trailing P/E: {pe_ratio}
            - Forward P/E: {forward_pe}
            - PEG Ratio: {peg_ratio}
            - Debt to Equity Ratio: {debt_to_equity}
            - Year-over-Year Revenue Growth: {rev_growth}
            - Profit Margin: {margin}
            - Free Cash Flow: {fcf}

            Provide a fundamental strength score. Verify if company is financially healthy, has clean debt margins, and positive free cash flows.
            Respond in a valid JSON structure:
            {{
                "verdict": "FAVORABLE" | "NEUTRAL" | "UNFAVORABLE",
                "score": float (0.0 to 10.0),
                "rationale": "Brief critique of valuation, debt burden, and growth profile."
            }}
            Do not add any markup or markdown wraps besides the raw JSON.
            """
            response_text = self.llm.call(prompt, system_prompt="You are an experienced equity research analyst.")
            clean_text = response_text.replace("```json", "").replace("```", "").strip()
            return json.loads(clean_text)
        except Exception as e:
            logger.error(f"FundamentalAnalysisSkill failed for {symbol}: {e}")
            return {"verdict": "NEUTRAL", "score": 5.0, "rationale": "Fallback due to fundamental analysis failure."}

class NewsSentimentSkill(Skill):
    def __init__(self, llm: LLMClient):
        super().__init__(
            name="NewsSentiment",
            description="Analyzes the sentiment of recent headlines for a stock symbol using LLM and returns a JSON verdict."
        )
        self.llm = llm

    def execute(self, symbol: str, news_items: List[Dict[str, Any]]) -> Dict[str, Any]:
        try:
            news_summary = ""
            for item in news_items:
                title = item.get("title", "")
                publisher = item.get("publisher", "")
                news_summary += f"- [{publisher}] {title}\n"

            if not news_summary:
                news_summary = "No recent news articles found."

            prompt = f"""
            Analyze the recent headlines for stock '{symbol}':
            {news_summary}

            Identify any negative/positive binary events (lawsuits, product recalls, FDA approvals, executive departures).
            Provide a news sentiment verdict. Respond in valid JSON structure:
            {{
                "verdict": "POSITIVE" | "NEUTRAL" | "NEGATIVE",
                "binary_event_detected": boolean,
                "sentiment_score": float (0.0 to 10.0),
                "rationale": "Brief summary of news landscape."
            }}
            Do not add any markup or markdown wraps besides the raw JSON.
            """
            response_text = self.llm.call(prompt, system_prompt="You are a financial news intelligence analyst.")
            clean_text = response_text.replace("```json", "").replace("```", "").strip()
            return json.loads(clean_text)
        except Exception as e:
            logger.error(f"NewsSentimentSkill failed for {symbol}: {e}")
            return {"verdict": "NEUTRAL", "binary_event_detected": False, "sentiment_score": 5.0, "rationale": "Fallback: news sentiment failed."}
