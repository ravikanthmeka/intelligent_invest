import logging
import yfinance as yf
import pandas as pd
from datetime import datetime
from typing import Dict, Any, Tuple, Optional, List
from src.skills.base import Skill

logger = logging.getLogger("MarketDataSkills")

class CalculateIndicatorsSkill(Skill):
    def __init__(self):
        super().__init__(
            name="CalculateIndicators",
            description="Computes technical indicators such as SMA_50, SMA_200, RSI, and ATR on a pandas DataFrame of historical stock prices."
        )

    def execute(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        # SMAs
        df['SMA_50'] = df['Close'].rolling(window=50).mean()
        df['SMA_200'] = df['Close'].rolling(window=200).mean()

        # RSI (14)
        delta = df['Close'].diff()
        gain = delta.where(delta > 0, 0.0)
        loss = -delta.where(delta < 0, 0.0)
        
        avg_gain = gain.rolling(window=14).mean()
        avg_loss = loss.rolling(window=14).mean()
        
        # Avoid division by zero
        rs = avg_gain / avg_loss.replace(0.0, 0.00001)
        df['RSI'] = 100.0 - (100.0 / (1.0 + rs))

        # ATR (14)
        high_low = df['High'] - df['Low']
        high_close = (df['High'] - df['Close'].shift()).abs()
        low_close = (df['Low'] - df['Close'].shift()).abs()
        
        ranges = pd.concat([high_low, high_close, low_close], axis=1)
        true_range = ranges.max(axis=1)
        df['ATR'] = true_range.rolling(window=14).mean()
        
        return df

class FetchEarningsCalendarSkill(Skill):
    def __init__(self):
        super().__init__(
            name="FetchEarningsCalendar",
            description="Checks if an earnings report is scheduled within +/- 3 days for a given stock symbol."
        )

    def execute(self, symbol: str, days_range: int = 3) -> Tuple[bool, Optional[str]]:
        try:
            ticker_obj = yf.Ticker(symbol)
            calendar = ticker_obj.calendar
            if not calendar or len(calendar) == 0:
                return True, None

            # Look up next earnings date
            earnings_dates = calendar.get("Earnings Date")
            if not earnings_dates:
                return True, None
            
            next_earnings = earnings_dates[0]
            if hasattr(next_earnings, 'date'):
                next_earnings = next_earnings.date()
            elif isinstance(next_earnings, pd.Timestamp):
                next_earnings = next_earnings.to_pydatetime().date()
            elif isinstance(next_earnings, datetime):
                next_earnings = next_earnings.date()
            
            today = datetime.now().date()
            days_diff = (next_earnings - today).days

            if -days_range <= days_diff <= days_range:
                reason = f"Upcoming earnings on {next_earnings.strftime('%Y-%m-%d')} ({days_diff} days away)"
                return False, reason
            
            return True, None
        except Exception as e:
            logger.warning(f"Earnings calendar check failed for {symbol}: {e}")
            return True, None

class FetchRecentNewsSkill(Skill):
    def __init__(self):
        super().__init__(
            name="FetchRecentNews",
            description="Fetches recent headlines and article titles for a stock ticker symbol."
        )

    def execute(self, symbol: str) -> List[Dict[str, Any]]:
        news_results = []
        try:
            ticker_obj = yf.Ticker(symbol)
            news = ticker_obj.news
            if news:
                for item in news[:5]:
                    # Handle new yfinance nested structure vs old flat structure
                    content = item.get("content", item)
                    title = content.get("title")
                    provider = content.get("provider", {})
                    publisher = provider.get("displayName") if isinstance(provider, dict) else item.get("publisher")
                    
                    link_obj = content.get("clickThroughUrl", {})
                    link = link_obj.get("url") if isinstance(link_obj, dict) else item.get("link")
                    
                    news_results.append({
                        "title": title,
                        "publisher": publisher,
                        "link": link
                    })
        except Exception as e:
            logger.error(f"Error fetching Yahoo Finance news for {symbol}: {e}")
            
        import os
        import urllib.request
        import json
        newsapi_key = os.environ.get("NEWSAPI_KEY")
        if newsapi_key:
            try:
                url = f"https://newsapi.org/v2/everything?q={symbol}&sortBy=publishedAt&apiKey={newsapi_key}"
                req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
                res = urllib.request.urlopen(req, timeout=5).read().decode('utf-8')
                data = json.loads(res)
                if data.get("status") == "ok":
                    articles = data.get("articles", [])[:3]
                    for a in articles:
                        news_results.append({
                            "title": a.get("title"),
                            "publisher": a.get("source", {}).get("name", "NewsAPI"),
                            "link": a.get("url")
                        })
            except Exception as e:
                logger.error(f"Error fetching NewsAPI for {symbol}: {e}")
                
        return news_results

class FetchMacroDataSkill(Skill):
    def __init__(self):
        super().__init__(
            name="FetchMacroData",
            description="Fetches performance of major macro indicators (SPY, TLT, GLD, UUP) over the past month."
        )

    def execute(self) -> Dict[str, Any]:
        macro_tickers = ["SPY", "TLT", "GLD", "UUP"]
        macro_data = {}
        for ticker in macro_tickers:
            try:
                t = yf.Ticker(ticker)
                hist = t.history(period="1mo")
                if len(hist) > 0:
                    start_price = hist['Close'].iloc[0]
                    end_price = hist['Close'].iloc[-1]
                    perf_pct = (end_price - start_price) / start_price * 100
                    macro_data[ticker] = {
                        "performance_1mo_pct": perf_pct,
                        "current_price": end_price
                    }
            except Exception as e:
                logger.error(f"Error fetching macro data for {ticker}: {e}")
        return macro_data

class FetchSectorETFDataSkill(Skill):
    def __init__(self):
        super().__init__(
            name="FetchSectorETFData",
            description="Fetches performance of major sector ETFs over the past month."
        )

    def execute(self) -> Dict[str, Any]:
        sector_etfs = ["XLK", "XLF", "XLE", "XLV", "XLY", "XLP", "XLI", "XLB", "XLU", "XLRE", "XLC"]
        sector_data = {}
        for ticker in sector_etfs:
            try:
                t = yf.Ticker(ticker)
                hist = t.history(period="1mo")
                if len(hist) > 0:
                    start_price = hist['Close'].iloc[0]
                    end_price = hist['Close'].iloc[-1]
                    perf_pct = (end_price - start_price) / start_price * 100
                    sector_data[ticker] = {
                        "performance_1mo_pct": perf_pct
                    }
            except Exception as e:
                logger.error(f"Error fetching sector data for {ticker}: {e}")
        return sector_data

class FetchQualitativeDataSkill(Skill):
    def __init__(self):
        super().__init__(
            name="FetchQualitativeData",
            description="Fetches business summary and key officers for qualitative analysis."
        )

    def execute(self, symbol: str) -> Dict[str, Any]:
        try:
            ticker_obj = yf.Ticker(symbol)
            info = ticker_obj.info
            summary = info.get("longBusinessSummary", "No business summary available.")
            officers = info.get("companyOfficers", [])
            leadership = []
            for officer in officers[:3]:
                name = officer.get("name", "")
                title = officer.get("title", "")
                if name and title:
                    leadership.append(f"{name} ({title})")
            
            return {
                "business_summary": summary,
                "leadership": leadership
            }
        except Exception as e:
            logger.error(f"Error fetching qualitative data for {symbol}: {e}")
            return {"business_summary": "Error fetching data.", "leadership": []}

class FetchOptionsChainSkill(Skill):
    def __init__(self):
        super().__init__(
            name="FetchOptionsChain",
            description="Fetches near-term options chain data to calculate put/call ratio and volume."
        )

    def execute(self, symbol: str) -> Dict[str, Any]:
        try:
            ticker = yf.Ticker(symbol)
            expirations = ticker.options
            if not expirations:
                return {}
            
            # Fetch the nearest expiration
            chain = ticker.option_chain(expirations[0])
            calls = chain.calls
            puts = chain.puts
            
            return {
                "expiration": expirations[0],
                "call_volume": int(calls['volume'].sum()) if 'volume' in calls else 0,
                "put_volume": int(puts['volume'].sum()) if 'volume' in puts else 0,
                "call_oi": int(calls['openInterest'].sum()) if 'openInterest' in calls else 0,
                "put_oi": int(puts['openInterest'].sum()) if 'openInterest' in puts else 0,
            }
        except Exception as e:
            logger.error(f"Error fetching options for {symbol}: {e}")
            return {}

class SelectSpeculativeOptionSkill(Skill):
    def __init__(self):
        super().__init__(
            name="SelectSpeculativeOption",
            description="Selects a speculative ATM option contract 30-45 DTE based on directional bias."
        )

    def execute(self, symbol: str, current_price: float, bias: str = "bullish") -> Dict[str, Any]:
        try:
            ticker = yf.Ticker(symbol)
            expirations = ticker.options
            if not expirations:
                return {}
            
            from datetime import datetime, timedelta
            target_date = datetime.now() + timedelta(days=35)
            
            # Find closest expiration to 35 days
            best_exp = expirations[0]
            min_diff = 9999
            for exp in expirations:
                exp_date = datetime.strptime(exp, "%Y-%m-%d")
                diff = abs((exp_date - target_date).days)
                if diff < min_diff:
                    min_diff = diff
                    best_exp = exp
            
            chain = ticker.option_chain(best_exp)
            options_df = chain.calls if bias == "bullish" else chain.puts
            right = "C" if bias == "bullish" else "P"
            
            if options_df.empty:
                return {}
                
            # Find strike closest to current price (ATM)
            options_df['strike_diff'] = abs(options_df['strike'] - current_price)
            atm_option = options_df.loc[options_df['strike_diff'].idxmin()]
            
            return {
                "symbol": symbol,
                "expiration": best_exp,
                "strike": float(atm_option['strike']),
                "right": right,
                "lastPrice": float(atm_option['lastPrice']),
                "bid": float(atm_option['bid']) if 'bid' in atm_option else 0.0,
                "ask": float(atm_option['ask']) if 'ask' in atm_option else 0.0,
                "volume": int(atm_option['volume']) if not pd.isna(atm_option['volume']) else 0
            }
        except Exception as e:
            logger.error(f"Error selecting option for {symbol}: {e}")
            return {}


class FetchInsiderTradingSkill(Skill):
    def __init__(self):
        super().__init__(
            name="FetchInsiderTrading",
            description="Fetches insider net purchases/sales over the last 6 months."
        )

    def execute(self, symbol: str) -> Dict[str, Any]:
        try:
            ticker = yf.Ticker(symbol)
            insider = ticker.insider_purchases
            if insider is None or insider.empty:
                return {}
            
            return insider.to_dict('records')
        except Exception as e:
            logger.error(f"Error fetching insider trading for {symbol}: {e}")
            return {}

class FetchDividendDataSkill(Skill):
    def __init__(self):
        super().__init__(
            name="FetchDividendData",
            description="Fetches dividend yield and payout ratio."
        )

    def execute(self, symbol: str) -> Dict[str, Any]:
        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info
            return {
                "dividend_yield": info.get('dividendYield', 0.0),
                "payout_ratio": info.get('payoutRatio', 0.0),
                "five_year_avg_yield": info.get('fiveYearAvgDividendYield', 0.0)
            }
        except Exception as e:
            logger.error(f"Error fetching dividend data for {symbol}: {e}")
            return {}

class CalculateCorrelationSkill(Skill):
    def __init__(self):
        super().__init__(
            name="CalculateCorrelation",
            description="Calculates Pearson correlation between a candidate and the active portfolio over 3 months."
        )

    def execute(self, candidate: str, active_symbols: List[str]) -> Dict[str, float]:
        if not active_symbols:
            return {}
        try:
            symbols = [candidate] + active_symbols
            data = yf.download(symbols, period="3mo", interval="1d")['Close']
            
            if data.empty:
                return {}
                
            # If only one symbol was found, yfinance returns a Series instead of DataFrame
            if isinstance(data, pd.Series):
                return {}
                
            returns = data.pct_change().dropna()
            corr_matrix = returns.corr()
            
            if candidate not in corr_matrix.columns:
                return {}
                
            correlations = {}
            for sym in active_symbols:
                if sym in corr_matrix.columns:
                    correlations[sym] = float(corr_matrix.loc[candidate, sym])
                    
            return correlations
        except Exception as e:
            logger.error(f"Error calculating correlation for {candidate}: {e}")
            return {}
