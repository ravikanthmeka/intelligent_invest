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
        Evaluate momentum and trend. If Current Price is above 50-day SMA or 50-day SMA is above 200-day SMA and RSI is between 45 and 70, this represents a healthy uptrend structure: respond with verdict 'BULLISH' and a score between 7.0 and 8.5.
        You must respond in a valid JSON structure:
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

class MacroEconomicAnalysisSkill(Skill):
    def __init__(self, llm: LLMClient):
        super().__init__(
            name="MacroEconomicAnalysis",
            description="Evaluates macro data to determine overall market risk posture."
        )
        self.llm = llm

    def execute(self, macro_data: Dict[str, Any]) -> Dict[str, Any]:
        prompt = f"""
        Analyze the following 1-month performance of key macroeconomic indicators:
        {json.dumps(macro_data, indent=2)}
        
        Indicators reference:
        - SPY: S&P 500 (Equities)
        - TLT: 20+ Year Treasury Bonds (Safe haven/Interest rate proxy)
        - GLD: Gold (Safe haven/Inflation hedge)
        - UUP: US Dollar Index (Safe haven/Currency strength)
        
        Determine the overall market risk posture.
        Respond in a valid JSON structure:
        {{
            "posture": "RISK_ON" | "RISK_OFF" | "NEUTRAL",
            "risk_multiplier": float (0.5 to 1.5, where <1 means tighten risk, >1 means relax risk),
            "suggested_themes": ["theme1", "theme2"],
            "rationale": "Brief macro rationale."
        }}
        Do not add any markup or markdown wraps besides the raw JSON.
        """
        try:
            response_text = self.llm.call(prompt, system_prompt="You are a global macro strategist.")
            clean_text = response_text.replace("```json", "").replace("```", "").strip()
            return json.loads(clean_text)
        except Exception as e:
            logger.error(f"MacroEconomicAnalysisSkill failed: {e}")
            return {"posture": "NEUTRAL", "risk_multiplier": 1.0, "suggested_themes": [], "rationale": "Fallback due to error."}

class GlobalSectorRotationSkill(Skill):
    def __init__(self, llm: LLMClient):
        super().__init__(
            name="GlobalSectorRotation",
            description="Evaluates sector ETFs to find where capital is flowing."
        )
        self.llm = llm

    def execute(self, sector_data: Dict[str, Any]) -> Dict[str, Any]:
        prompt = f"""
        Analyze the 1-month performance of the following sector ETFs:
        {json.dumps(sector_data, indent=2)}
        
        Identify the top 3 strongest sectors where capital is currently flowing.
        Respond in a valid JSON structure:
        {{
            "top_sectors": ["Sector1", "Sector2", "Sector3"],
            "rationale": "Brief reasoning for sector strength."
        }}
        Do not add any markup or markdown wraps besides the raw JSON.
        """
        try:
            response_text = self.llm.call(prompt, system_prompt="You are a sector rotation analyst.")
            clean_text = response_text.replace("```json", "").replace("```", "").strip()
            return json.loads(clean_text)
        except Exception as e:
            logger.error(f"GlobalSectorRotationSkill failed: {e}")
            return {"top_sectors": [], "rationale": "Fallback due to error."}

class QualitativeAnalysisSkill(Skill):
    def __init__(self, llm: LLMClient):
        super().__init__(
            name="QualitativeAnalysis",
            description="Evaluates company leadership and business moat."
        )
        self.llm = llm

    def execute(self, symbol: str, qual_data: Dict[str, Any]) -> Dict[str, Any]:
        prompt = f"""
        Evaluate the qualitative factors for {symbol}:
        Business Summary: {qual_data.get('business_summary', 'N/A')}
        Leadership: {', '.join(qual_data.get('leadership', []))}
        
        Score the business moat, clarity of business model, and apparent leadership strength.
        Respond in a valid JSON structure:
        {{
            "verdict": "STRONG" | "NEUTRAL" | "WEAK",
            "score": float (0.0 to 10.0),
            "rationale": "Brief qualitative evaluation."
        }}
        Do not add any markup or markdown wraps besides the raw JSON.
        """
        try:
            response_text = self.llm.call(prompt, system_prompt="You are an equity research analyst.")
            clean_text = response_text.replace("```json", "").replace("```", "").strip()
            return json.loads(clean_text)
        except Exception as e:
            logger.error(f"QualitativeAnalysisSkill failed: {e}")
            return {"verdict": "NEUTRAL", "score": 5.0, "rationale": "Fallback due to error."}

class HistoricalAnalogSkill(Skill):
    def __init__(self, llm: LLMClient):
        super().__init__(
            name="HistoricalAnalog",
            description="Compares a stock's current technical setup with historical analogs to predict breakout probability."
        )
        self.llm = llm

    def execute(self, symbol: str, current_price: float, rsi: float, sma_50: float, sma_200: float) -> Dict[str, Any]:
        prompt = f"""
        Evaluate {symbol}'s current setup against historical market cycles and analogs.
        Current Setup:
        - Price: ${current_price:.2f}
        - RSI: {rsi:.1f}
        - SMA 50: ${sma_50:.2f}
        - SMA 200: ${sma_200:.2f}
        
        Based on historical precedent for similar technical profiles, what is the probability of a sustained breakout versus a false positive?
        Respond in a valid JSON structure:
        {{
            "verdict": "FAVORABLE" | "NEUTRAL" | "UNFAVORABLE",
            "score": float (0.0 to 10.0),
            "rationale": "Brief historical comparison."
        }}
        Do not add any markup or markdown wraps besides the raw JSON.
        """
        try:
            response_text = self.llm.call(prompt, system_prompt="You are a quantitative market historian.")
            clean_text = response_text.replace("```json", "").replace("```", "").strip()
            return json.loads(clean_text)
        except Exception as e:
            logger.error(f"HistoricalAnalogSkill failed for {symbol}: {e}")
            return {"verdict": "NEUTRAL", "historical_score": 5.0, "rationale": "Historical analog logic error."}

class OptionsFlowAnalysisSkill(Skill):
    def __init__(self, llm: LLMClient):
        super().__init__(name="OptionsFlowAnalysis", description="Evaluates options flow (put/call ratio).")
        self.llm = llm

    def execute(self, symbol: str, options_data: Dict[str, Any]) -> Dict[str, Any]:
        if not options_data:
            return {"verdict": "NEUTRAL", "score": 5.0, "rationale": "No options data available."}
        
        call_vol = options_data.get("call_volume", 0)
        put_vol = options_data.get("put_volume", 0)
        
        if call_vol == 0 and put_vol == 0:
            return {"verdict": "NEUTRAL", "score": 5.0, "rationale": "Zero options volume."}
            
        pc_ratio = put_vol / call_vol if call_vol > 0 else 999.0
        
        score = 5.0
        verdict = "NEUTRAL"
        if pc_ratio < 0.7:
            verdict = "BULLISH"
            score = 8.0
        elif pc_ratio > 1.2:
            verdict = "BEARISH"
            score = 3.0
            
        return {
            "verdict": verdict,
            "score": score,
            "rationale": f"Put/Call Ratio is {pc_ratio:.2f}."
        }

class InsiderTradingAnalysisSkill(Skill):
    def __init__(self, llm: LLMClient):
        super().__init__(name="InsiderTradingAnalysis", description="Evaluates insider purchasing data.")
        self.llm = llm

    def execute(self, symbol: str, insider_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        if not insider_data:
            return {"verdict": "NEUTRAL", "score": 5.0, "rationale": "No insider data available."}
            
        purchases = 0
        sales = 0
        for row in insider_data:
            if row.get("Insider Purchases Last 6m") == "Purchases":
                purchases = float(row.get("Shares", 0))
            elif row.get("Insider Purchases Last 6m") == "Sales":
                sales = float(row.get("Shares", 0))
                
        if purchases > sales * 2:
            return {"verdict": "BULLISH", "score": 8.0, "rationale": "Significant net insider buying."}
        elif sales > purchases * 2:
            return {"verdict": "BEARISH", "score": 3.0, "rationale": "Significant net insider selling."}
            
        return {"verdict": "NEUTRAL", "score": 5.0, "rationale": "Mixed or neutral insider activity."}

class RetailSentimentAnalysisSkill(Skill):
    def __init__(self, llm: LLMClient):
        super().__init__(name="RetailSentimentAnalysis", description="Evaluates retail sentiment/momentum.")
        self.llm = llm

    def execute(self, symbol: str, news_items: List[Dict[str, Any]], social_items: List[Dict[str, Any]], volume: float, avg_volume: float) -> Dict[str, Any]:
        vol_spike = (volume / avg_volume) if avg_volume > 0 else 1.0
        
        news_summary = "\n".join([f"- {n.get('title')}" for n in news_items]) if news_items else "No news."
        social_summary = "\n".join([f"- [{s.get('platform')}] {s.get('content')}" for s in social_items]) if social_items else "No social mentions found."
        
        prompt = f"""Evaluate the retail/meme stock sentiment for '{symbol}'.
        Today's Volume Spike vs Average: {vol_spike:.1f}x
        
        Recent Headlines: 
        {news_summary}
        
        Recent Social Media Posts (Reddit/X):
        {social_summary}
        
        Is this stock currently driven by high retail FOMO or social momentum? Factor in retail hype, emojis (🚀, 💎🙌), and social momentum alongside the volume spike data.
        Respond in JSON:
        {{
            "verdict": "HIGH_MOMENTUM" | "NEUTRAL" | "LOW_MOMENTUM",
            "score": float (0-10, higher means more retail hype),
            "rationale": "Brief explanation"
        }}"""
        
        try:
            res = self.llm.call(prompt, system_prompt="You are a retail sentiment tracker.")
            return json.loads(res.replace("```json", "").replace("```", "").strip())
        except:
            # Fallback algorithmic
            score = 5.0
            verdict = "NEUTRAL"
            if vol_spike > 2.5 or (social_items and vol_spike > 1.5):
                score = 8.5
                verdict = "HIGH_MOMENTUM"
            return {"verdict": verdict, "score": score, "rationale": f"Volume spike {vol_spike:.1f}x (with social={bool(social_items)})."}

class DividendIncomeAnalysisSkill(Skill):
    def __init__(self, llm: LLMClient):
        super().__init__(name="DividendIncomeAnalysis", description="Evaluates dividend yield safety.")
        self.llm = llm

    def execute(self, symbol: str, div_data: Dict[str, Any]) -> Dict[str, Any]:
        if not div_data or div_data.get("dividend_yield", 0) == 0:
            return {"verdict": "NO_YIELD", "score": 0.0, "rationale": "Company pays no dividend."}
            
        yield_pct = div_data.get("dividend_yield", 0)
        payout = div_data.get("payout_ratio", 0)
        
        if yield_pct > 0.02 and payout < 0.70:
            return {"verdict": "SAFE_YIELD", "score": 9.0, "rationale": f"Safe {yield_pct*100:.1f}% yield with {payout*100:.1f}% payout."}
        elif yield_pct > 0.05 and payout > 0.90:
            return {"verdict": "YIELD_TRAP", "score": 3.0, "rationale": f"High {yield_pct*100:.1f}% yield but unsafe {payout*100:.1f}% payout."}
            
        return {"verdict": "MODERATE_YIELD", "score": 6.0, "rationale": "Average dividend metrics."}

class PortfolioCorrelationSkill(Skill):
    def __init__(self, llm: LLMClient):
        super().__init__(name="PortfolioCorrelation", description="Evaluates diversification matrix.")
        self.llm = llm

    def execute(self, symbol: str, correlations: Dict[str, float], max_threshold: float = 0.75) -> Dict[str, Any]:
        if not correlations:
            return {"verdict": "UNCORRELATED", "score": 10.0, "rationale": "No active positions to correlate with."}
            
        high_corr = [sym for sym, corr in correlations.items() if corr > max_threshold]
        
        if high_corr:
            return {
                "verdict": "HIGHLY_CORRELATED", 
                "score": 2.0, 
                "rationale": f"Highly correlated with existing positions: {high_corr}."
            }
            
        return {"verdict": "UNCORRELATED", "score": 9.0, "rationale": "Provides good diversification benefits."}

class VolatilityArbitrageSkill(Skill):
    def __init__(self, llm: LLMClient):
        super().__init__(name="VolatilityArbitrage", description="Evaluates IV Rank for options strategies.")
        self.llm = llm

    def execute(self, symbol: str, iv_data: Dict[str, Any], direction_bias: str = "BULLISH") -> Dict[str, Any]:
        iv_rank = iv_data.get("iv_rank", 50)
        
        # User constraint: ONLY debit strategies allowed.
        # So if IV Rank is high, options are expensive, we might avoid buying.
        # If IV Rank is low, options are cheap, great for buying.
        if iv_rank > 70:
            return {
                "verdict": "IV_TOO_HIGH",
                "score": 3.0,
                "rationale": f"IV Rank is {iv_rank:.1f}. Options are too expensive for debit strategies. Avoid buying.",
                "recommended_strategy": "NONE"
            }
        else:
            strategy = "LONG_CALL" if direction_bias == "BULLISH" else "LONG_PUT"
            return {
                "verdict": "FAVORABLE_IV",
                "score": 9.0 if iv_rank < 30 else 7.0,
                "rationale": f"IV Rank is {iv_rank:.1f}. Premium is relatively cheap. Favor {strategy}.",
                "recommended_strategy": strategy
            }

class EarningsCatalystSkill(Skill):
    def __init__(self, llm: LLMClient):
        super().__init__(name="EarningsCatalyst", description="Evaluates potential earnings moves.")
        self.llm = llm

    def execute(self, symbol: str, earnings_data: Dict[str, Any]) -> Dict[str, Any]:
        if not earnings_data:
            return {"verdict": "UNKNOWN", "score": 5.0, "rationale": "No earnings data."}
            
        growth = earnings_data.get("earnings_growth", 0.0)
        surprise = earnings_data.get("recent_surprise_pct", 0.0)
        
        score = 5.0
        verdict = "NEUTRAL"
        if growth > 0.15 and surprise > 0.05:
            score = 9.0
            verdict = "BULLISH_CATALYST"
        elif growth < 0 and surprise < -0.05:
            score = 2.0
            verdict = "BEARISH_CATALYST"
            
        return {
            "verdict": verdict,
            "score": score,
            "rationale": f"Earnings growth: {growth*100:.1f}%. Recent surprise: {surprise*100:.1f}%."
        }

class PortfolioHedgingSkill(Skill):
    def __init__(self, llm: LLMClient):
        super().__init__(name="PortfolioHedging", description="Evaluates portfolio hedging needs.")
        self.llm = llm

    def execute(self, macro_posture: str, active_exposure_pct: float) -> Dict[str, Any]:
        if macro_posture in ["BEARISH", "CRASH_WARNING"] and active_exposure_pct > 0.40:
            return {
                "needs_hedge": True,
                "hedge_target": "SPY",
                "hedge_type": "LONG_PUT",
                "rationale": f"Macro is {macro_posture} and active exposure is {active_exposure_pct*100:.1f}%. Hedge recommended."
            }
        
        return {
            "needs_hedge": False,
            "hedge_target": "NONE",
            "hedge_type": "NONE",
            "rationale": f"Macro is {macro_posture} with {active_exposure_pct*100:.1f}% exposure. No macro hedge needed."
        }
