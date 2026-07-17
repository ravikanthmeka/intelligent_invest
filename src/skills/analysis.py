import json
import logging
import yfinance as yf
import yaml
from typing import Dict, Any, List
from src.llm import LLMClient
from src.skills.base import Skill

logger = logging.getLogger("AnalysisSkills")

def load_config() -> Dict[str, Any]:
    try:
        with open("config.yaml", "r") as f:
            return yaml.safe_load(f) or {}
    except Exception:
        return {}

class TechnicalAnalysisSkill(Skill):
    def __init__(self, llm: LLMClient):
        super().__init__(
            name="TechnicalAnalysis",
            description="Evaluates a technical indicator profile for a stock using LLM reasoning and outputs a JSON verdict."
        )
        self.llm = llm

    def execute(self, symbol: str, data: Dict[str, Any], learnings_feedback: str = "") -> Dict[str, Any]:
        learnings_str = f"\nPortfolio learnings from past trades:\n{learnings_feedback}\n" if learnings_feedback else ""
        
        config = load_config()
        prompt_cfg = config.get("prompts", {}).get("technical_analysis", {})
        system_prompt = prompt_cfg.get("system_prompt", "You are a professional quantitative technical analyst.")
        
        default_template = """Analyze the following technical indicator profile for stock ticker '{symbol}':
        - Current Price: ${close:.2f}
        - 14-day RSI: {rsi:.1f}
        - 50-day Simple Moving Average (SMA): ${sma_50:.2f}
        - 200-day Simple Moving Average (SMA): ${sma_200:.2f}
        - 14-day Average True Range (ATR): ${atr:.2f}
        - Volume Spike Detected: {volume_spike}
        {learnings_str}
        Provide a verdict. You must respond in a valid JSON structure:
        {{
            "verdict": "BULLISH" | "NEUTRAL" | "BEARISH",
            "score": float (0.0 to 10.0),
            "rationale": "Short analysis of indicators, support levels, and momentum."
        }}
        Do not add any markup or markdown wraps besides the raw JSON."""
        
        template = prompt_cfg.get("user_prompt_template", default_template)
        
        try:
            prompt = template.format(
                symbol=symbol,
                close=data['close'],
                rsi=data['rsi'],
                sma_50=data['sma_50'],
                sma_200=data['sma_200'],
                atr=data['atr'],
                volume_spike=data['volume_spike'],
                learnings_str=learnings_str
            )
        except Exception as e:
            logger.error(f"Failed to format technical analysis prompt template: {e}. Falling back to default.")
            prompt = default_template.format(
                symbol=symbol,
                close=data['close'],
                rsi=data['rsi'],
                sma_50=data['sma_50'],
                sma_200=data['sma_200'],
                atr=data['atr'],
                volume_spike=data['volume_spike'],
                learnings_str=learnings_str
            )
            
        try:
            response_text = self.llm.call(prompt, system_prompt=system_prompt)
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

    def execute(self, symbol: str, learnings_feedback: str = "") -> Dict[str, Any]:
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

            learnings_str = f"\nPortfolio learnings from past trades:\n{learnings_feedback}\n" if learnings_feedback else ""
            
            config = load_config()
            prompt_cfg = config.get("prompts", {}).get("fundamental_analysis", {})
            system_prompt = prompt_cfg.get("system_prompt", "You are an experienced equity research analyst.")
            
            default_template = """Evaluate the financial fundamentals of company ticker '{symbol}':
            - Trailing P/E: {pe_ratio}
            - Forward P/E: {forward_pe}
            - PEG Ratio: {peg_ratio}
            - Debt to Equity Ratio: {debt_to_equity}
            - Year-over-Year Revenue Growth: {rev_growth}
            - Profit Margin: {margin}
            - Free Cash Flow: {fcf}
            {learnings_str}
            Provide a fundamental strength score. Verify if company is financially healthy, has clean debt margins, and positive free cash flows.
            Respond in a valid JSON structure:
            {{
                "verdict": "FAVORABLE" | "NEUTRAL" | "UNFAVORABLE",
                "score": float (0.0 to 10.0),
                "rationale": "Brief critique of valuation, debt burden, and growth profile."
            }}
            Do not add any markup or markdown wraps besides the raw JSON."""
            
            template = prompt_cfg.get("user_prompt_template", default_template)
            
            try:
                prompt = template.format(
                    symbol=symbol,
                    pe_ratio=pe_ratio,
                    forward_pe=forward_pe,
                    peg_ratio=peg_ratio,
                    debt_to_equity=debt_to_equity,
                    rev_growth=rev_growth,
                    margin=margin,
                    fcf=fcf,
                    learnings_str=learnings_str
                )
            except Exception as e:
                logger.error(f"Failed to format fundamental analysis prompt template: {e}. Falling back.")
                prompt = default_template.format(
                    symbol=symbol,
                    pe_ratio=pe_ratio,
                    forward_pe=forward_pe,
                    peg_ratio=peg_ratio,
                    debt_to_equity=debt_to_equity,
                    rev_growth=rev_growth,
                    margin=margin,
                    fcf=fcf,
                    learnings_str=learnings_str
                )
                
            response_text = self.llm.call(prompt, system_prompt=system_prompt)
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

    def execute(self, symbol: str, news_items: List[Dict[str, Any]], learnings_feedback: str = "") -> Dict[str, Any]:
        try:
            news_summary = ""
            for item in news_items:
                title = item.get("title", "")
                publisher = item.get("publisher", "")
                news_summary += f"- [{publisher}] {title}\n"

            if not news_summary:
                news_summary = "No recent news articles found."

            learnings_str = f"\nPortfolio learnings from past trades:\n{learnings_feedback}\n" if learnings_feedback else ""
            
            config = load_config()
            prompt_cfg = config.get("prompts", {}).get("news_sentiment", {})
            system_prompt = prompt_cfg.get("system_prompt", "You are a financial news intelligence analyst.")
            
            default_template = """Analyze the recent headlines for stock '{symbol}':
            {news_summary}
            {learnings_str}
            Identify any negative/positive binary events (lawsuits, product recalls, FDA approvals, executive departures).
            Provide a news sentiment verdict. Respond in valid JSON structure:
            {{
                "verdict": "POSITIVE" | "NEUTRAL" | "NEGATIVE",
                "binary_event_detected": boolean,
                "sentiment_score": float (0.0 to 10.0),
                "rationale": "Brief summary of news landscape."
            }}
            Do not add any markup or markdown wraps besides the raw JSON."""
            
            template = prompt_cfg.get("user_prompt_template", default_template)
            
            try:
                prompt = template.format(
                    symbol=symbol,
                    news_summary=news_summary,
                    learnings_str=learnings_str
                )
            except Exception as e:
                logger.error(f"Failed to format news sentiment prompt template: {e}. Falling back.")
                prompt = default_template.format(
                    symbol=symbol,
                    news_summary=news_summary,
                    learnings_str=learnings_str
                )
                
            response_text = self.llm.call(prompt, system_prompt=system_prompt)
            clean_text = response_text.replace("```json", "").replace("```", "").strip()
            return json.loads(clean_text)
        except Exception as e:
            logger.error(f"NewsSentimentSkill failed for {symbol}: {e}")
            return {"verdict": "NEUTRAL", "binary_event_detected": False, "sentiment_score": 5.0, "rationale": "Fallback: news sentiment failed."}

class GrowthRnDEvaluationSkill(Skill):
    def __init__(self, llm: LLMClient):
        super().__init__(
            name="GrowthRnDEvaluation",
            description="Evaluates if a company has high R&D intensity and strong revenue scaling despite weaker current profits."
        )
        self.llm = llm

    def execute(self, symbol: str, learnings_feedback: str = "") -> Dict[str, Any]:
        try:
            ticker_obj = yf.Ticker(symbol)
            financials = ticker_obj.financials
            info = ticker_obj.info
            
            # Extract values
            rnd_val = 0.0
            rev_val = 0.0
            net_income_val = 0.0
            
            if "Research And Development" in financials.index:
                s = financials.loc["Research And Development"].dropna()
                if not s.empty:
                    rnd_val = float(s.iloc[0])
            
            if "Total Revenue" in financials.index:
                s = financials.loc["Total Revenue"].dropna()
                if not s.empty:
                    rev_val = float(s.iloc[0])
                    
            if "Net Income" in financials.index:
                s = financials.loc["Net Income"].dropna()
                if not s.empty:
                    net_income_val = float(s.iloc[0])
            
            # Compute indicators
            rnd_intensity = (rnd_val / rev_val) if rev_val > 0 else 0.0
            net_margin = (net_income_val / rev_val) if rev_val > 0 else 0.0
            
            # Compute YoY Revenue Growth
            rev_growth_yoy = 0.0
            if "Total Revenue" in financials.index:
                s = financials.loc["Total Revenue"].dropna()
                if len(s) >= 2:
                    latest_rev = float(s.iloc[0])
                    prev_rev = float(s.iloc[1])
                    if prev_rev > 0:
                        rev_growth_yoy = (latest_rev - prev_rev) / prev_rev
            
            if rev_growth_yoy == 0.0:
                # Fallback to info
                rev_growth_yoy = info.get("revenueGrowth", 0.0)
                if rev_growth_yoy is None:
                    rev_growth_yoy = 0.0
            
            learnings_str = f"\nPortfolio learnings from past trades:\n{learnings_feedback}\n" if learnings_feedback else ""
            
            config = load_config()
            prompt_cfg = config.get("prompts", {}).get("growth_rnd_evaluation", {})
            system_prompt = prompt_cfg.get("system_prompt", "You are a growth investing specialist and corporate finance expert.")
            
            default_template = """Evaluate the growth reinvestment profile of company ticker '{symbol}':
            - Latest Annual Revenue: ${revenue:,.2f}
            - Latest Annual R&D Expenditure: ${rnd_exp:,.2f}
            - R&D Intensity (R&D / Revenue): {rnd_intensity:.1%}
            - Year-over-Year Revenue Growth: {revenue_growth:.1%}
            - Net Profit Margin: {net_margin:.1%}
            {learnings_str}
            Determine if this company represents a high-quality growth company that is deliberately trading short-term profitability for massive R&D reinvestment and market share scaling.
            Respond in a valid JSON structure:
            {{
                "verdict": "FAVORABLE" | "NEUTRAL" | "UNFAVORABLE",
                "score": float (0.0 to 10.0),
                "rationale": "Critique of R&D reinvestment efficiency, revenue growth momentum, and long-term scaling outlook."
            }}
            Do not add any markup or markdown wraps besides the raw JSON."""
            
            template = prompt_cfg.get("user_prompt_template", default_template)
            
            try:
                prompt = template.format(
                    symbol=symbol,
                    revenue=rev_val,
                    rnd_exp=rnd_val,
                    rnd_intensity=rnd_intensity,
                    revenue_growth=rev_growth_yoy,
                    net_margin=net_margin,
                    learnings_str=learnings_str
                )
            except Exception as e:
                logger.error(f"Failed to format growth evaluation prompt: {e}. Falling back.")
                prompt = default_template.format(
                    symbol=symbol,
                    revenue=rev_val,
                    rnd_exp=rnd_val,
                    rnd_intensity=rnd_intensity,
                    revenue_growth=rev_growth_yoy,
                    net_margin=net_margin,
                    learnings_str=learnings_str
                )
                
            response_text = self.llm.call(prompt, system_prompt=system_prompt)
            clean_text = response_text.replace("```json", "").replace("```", "").strip()
            res = json.loads(clean_text)
            
            # Inject raw values in result dict
            res["rnd_intensity_pct"] = rnd_intensity * 100
            res["revenue_growth_pct"] = rev_growth_yoy * 100
            res["net_margin_pct"] = net_margin * 100
            return res
        except Exception as e:
            logger.error(f"GrowthRnDEvaluationSkill failed for {symbol}: {e}")
            return {
                "verdict": "NEUTRAL", 
                "score": 5.0, 
                "rnd_intensity_pct": 0.0,
                "revenue_growth_pct": 0.0,
                "net_margin_pct": 0.0,
                "rationale": f"Fallback: growth R&D analysis failed due to error: {e}"
            }
