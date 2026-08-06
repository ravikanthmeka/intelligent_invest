import logging
import yfinance as yf
import pandas as pd
import numpy as np
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
    _cached_av_news = None
    _av_last_fetch_time = 0
    _av_rate_limited = False

    def __init__(self):
        super().__init__(
            name="FetchRecentNews",
            description="Fetches recent headlines and article titles for a stock ticker symbol."
        )

    def execute(self, symbol: str) -> List[Dict[str, Any]]:
        import os
        import time
        import urllib.request
        import json
        
        news_results = []
        av_key = os.environ.get("ALPHAVANTAGE_API_KEY") or os.environ.get("ALPHA_VANTAGE_API_KEY")
        
        # 1. Try Alpha Vantage First
        if av_key and not self.__class__._av_rate_limited:
            current_time = time.time()
            # Refresh global cache if older than 15 minutes (900 seconds)
            if self.__class__._cached_av_news is None or (current_time - self.__class__._av_last_fetch_time > 900):
                try:
                    url = f"https://www.alphavantage.co/query?function=NEWS_SENTIMENT&limit=200&apikey={av_key}"
                    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
                    res = urllib.request.urlopen(req, timeout=10).read().decode('utf-8')
                    data = json.loads(res)
                    
                    if "Information" in data and "rate limit" in data["Information"].lower():
                        logger.warning("Alpha Vantage API rate limit hit. Falling back to yfinance.")
                        self.__class__._av_rate_limited = True
                    elif "Note" in data and "call frequency" in data["Note"].lower():
                        logger.warning("Alpha Vantage API rate limit hit (Note). Falling back to yfinance.")
                        self.__class__._av_rate_limited = True
                    elif "feed" in data:
                        self.__class__._cached_av_news = data["feed"]
                        self.__class__._av_last_fetch_time = current_time
                        # Optional: reset rate limited flag if it succeeds
                        self.__class__._av_rate_limited = False
                    else:
                        logger.warning(f"Alpha Vantage API returned unexpected response. Keys: {list(data.keys())}")
                except Exception as e:
                    logger.error(f"Error fetching Alpha Vantage news: {e}")
            
            # Filter from cache
            if self.__class__._cached_av_news:
                for article in self.__class__._cached_av_news:
                    # Check if symbol is in ticker_sentiment
                    tickers_mentioned = [t.get("ticker", "") for t in article.get("ticker_sentiment", [])]
                    if symbol in tickers_mentioned or symbol in article.get("title", ""):
                        news_results.append({
                            "title": article.get("title"),
                            "publisher": article.get("source"),
                            "link": article.get("url")
                        })
                        if len(news_results) >= 5:
                            break

        # If AV gave us news, return it and skip yfinance fallback
        if news_results:
            return news_results

        # 2. Fallback to yfinance (existing logic)
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

class FetchSocialSentimentSkill(Skill):
    def __init__(self):
        super().__init__(
            name="FetchSocialSentiment",
            description="Fetches recent mentions and sentiment from social platforms like Reddit and X (Twitter)."
        )

    def execute(self, symbol: str) -> List[Dict[str, Any]]:
        social_results = []
        import os
        import urllib.request
        import json
        
        # 1. Reddit Scraping (Fallback to public JSON if no API keys)
        reddit_client_id = os.environ.get("REDDIT_CLIENT_ID")
        reddit_client_secret = os.environ.get("REDDIT_CLIENT_SECRET")
        
        try:
            if reddit_client_id and reddit_client_secret:
                # Stub for authenticated PRAW if the user provides keys
                pass
            else:
                # Fallback to public JSON scraping
                subreddits = ["wallstreetbets", "stocks", "investing"]
                for sub in subreddits:
                    url = f"https://www.reddit.com/r/{sub}/search.json?q={symbol}&restrict_sr=1&sort=new&limit=3"
                    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'})
                    res = urllib.request.urlopen(req, timeout=5).read().decode('utf-8')
                    data = json.loads(res)
                    posts = data.get("data", {}).get("children", [])
                    for post in posts:
                        post_data = post.get("data", {})
                        title = post_data.get("title", "")
                        selftext = post_data.get("selftext", "")[:200]
                        social_results.append({
                            "platform": "Reddit",
                            "source": f"r/{sub}",
                            "content": f"{title} - {selftext}"
                        })
        except Exception as e:
            logger.error(f"Error fetching Reddit sentiment for {symbol}: {e}")

        # 2. X (Twitter) Scraping (Stub - X strictly requires API keys)
        x_bearer_token = os.environ.get("X_BEARER_TOKEN")
        try:
            if x_bearer_token:
                url = f"https://api.twitter.com/2/tweets/search/recent?query=%24{symbol}&max_results=10"
                req = urllib.request.Request(url, headers={'Authorization': f'Bearer {x_bearer_token}'})
                res = urllib.request.urlopen(req, timeout=5).read().decode('utf-8')
                data = json.loads(res)
                tweets = data.get("data", [])
                for t in tweets:
                    social_results.append({
                        "platform": "X",
                        "source": "Twitter",
                        "content": t.get("text", "")
                    })
            else:
                logger.info(f"Skipping X (Twitter) fetch for {symbol}: No X_BEARER_TOKEN in .env")
        except Exception as e:
            logger.error(f"Error fetching X sentiment for {symbol}: {e}")
            
        return social_results
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
            # Sort by strike difference to find the closest ones
            options_df = options_df.sort_values(by='strike_diff')
            atm_option = options_df.iloc[0]
            
            # Get up to 3 considered options
            considered = []
            for i in range(min(3, len(options_df))):
                opt = options_df.iloc[i]
                considered.append({
                    "strike": float(opt['strike']),
                    "lastPrice": float(opt['lastPrice']),
                    "ask": float(opt['ask']) if 'ask' in opt else 0.0,
                    "volume": int(opt['volume']) if not pd.isna(opt['volume']) else 0
                })
            
            return {
                "symbol": symbol,
                "expiration": best_exp,
                "strike": float(atm_option['strike']),
                "right": right,
                "lastPrice": float(atm_option['lastPrice']),
                "bid": float(atm_option['bid']) if 'bid' in atm_option else 0.0,
                "ask": float(atm_option['ask']) if 'ask' in atm_option else 0.0,
                "volume": int(atm_option['volume']) if not pd.isna(atm_option['volume']) else 0,
                "considered_options": considered
            }
        except Exception as e:
            logger.error(f"Error selecting option for {symbol}: {e}")
            return {}

class SelectWheelOptionSkill(Skill):
    def __init__(self):
        super().__init__(
            name="SelectWheelOption",
            description="Selects an OTM option for the Wheel strategy (CSP or CC) ~30-45 DTE."
        )

    def execute(self, symbol: str, current_price: float, phase: str = "CSP", assignment_price: float = 0.0) -> Dict[str, Any]:
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
            
            if phase == "CSP":
                options_df = chain.puts
                right = "P"
                # For CSP, we want an OTM Put (strike < current_price)
                options_df = options_df[options_df['strike'] < current_price]
            else: # CC
                options_df = chain.calls
                right = "C"
                # For CC, we want an OTM Call (strike > current_price AND strike > assignment_price)
                target_strike_min = max(current_price, assignment_price)
                options_df = options_df[options_df['strike'] > target_strike_min]
            
            if options_df.empty:
                return {}
                
            # Find strike roughly ~0.30 Delta. Without full Greeks from yfinance, 
            # we can approximate an OTM strike 5-10% away from current price.
            if phase == "CSP":
                # Find strike closest to 95% of current price
                target_strike = current_price * 0.95
            else:
                # Find strike closest to 105% of current price (or assignment price)
                target_strike_min = max(current_price, assignment_price)
                target_strike = target_strike_min * 1.05
                
            options_df['strike_diff'] = abs(options_df['strike'] - target_strike)
            options_df = options_df.sort_values(by='strike_diff')
            selected_option = options_df.iloc[0]
            
            return {
                "symbol": symbol,
                "expiration": best_exp,
                "strike": float(selected_option['strike']),
                "right": right,
                "lastPrice": float(selected_option['lastPrice']),
                "bid": float(selected_option['bid']) if 'bid' in selected_option else 0.0,
                "ask": float(selected_option['ask']) if 'ask' in selected_option else 0.0,
                "volume": int(selected_option['volume']) if not pd.isna(selected_option['volume']) else 0
            }
        except Exception as e:
            logger.error(f"Error selecting wheel option for {symbol}: {e}")
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

class FetchIVRankSkill(Skill):
    def __init__(self):
        super().__init__(
            name="FetchIVRank",
            description="Fetches the implied volatility data to approximate IV Rank."
        )

    def execute(self, symbol: str) -> Dict[str, Any]:
        try:
            ticker = yf.Ticker(symbol)
            # Use current implied volatility from option chain for near term
            exps = ticker.options
            if not exps:
                return {"iv_rank": 50, "implied_volatility": 0.0}
            
            # Fetch near term options chain
            chain = ticker.option_chain(exps[0])
            calls = chain.calls
            if calls.empty:
                return {"iv_rank": 50, "implied_volatility": 0.0}
                
            # Get atm implied volatility
            current_price = ticker.history(period="1d")['Close'].iloc[-1]
            atm_call = calls.iloc[(calls['strike'] - current_price).abs().argsort()[:1]]
            current_iv = atm_call['impliedVolatility'].values[0]
            
            # Very rough heuristic for IV rank without historical IV data
            # Typically 0.2 is low, 0.5 is high for normal stocks
            iv_rank = min(max((current_iv - 0.1) / 0.8 * 100, 0), 100)
            
            return {
                "iv_rank": iv_rank,
                "implied_volatility": current_iv
            }
        except Exception as e:
            logger.error(f"Error fetching IV data for {symbol}: {e}")
            return {"iv_rank": 50, "implied_volatility": 0.0}

class FetchEarningsCatalystDataSkill(Skill):
    def __init__(self):
        super().__init__(
            name="FetchEarningsCatalystData",
            description="Fetches recent earnings surprises and upcoming earnings estimates."
        )

    def execute(self, symbol: str) -> Dict[str, Any]:
        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info
            earnings_history = ticker.earnings_history if hasattr(ticker, 'earnings_history') else pd.DataFrame()
            
            recent_surprise = 0.0
            if not earnings_history.empty and 'epsSurprisePercent' in earnings_history.columns:
                recent_surprise = earnings_history['epsSurprisePercent'].iloc[-1]
                
            return {
                "forward_eps": info.get("forwardEps", 0.0),
                "trailing_eps": info.get("trailingEps", 0.0),
                "recent_surprise_pct": recent_surprise,
                "earnings_growth": info.get("earningsGrowth", 0.0)
            }
        except Exception as e:
            logger.error(f"Error fetching earnings catalyst data for {symbol}: {e}")
            return {}


class FetchIntradayRelativeStrengthSkill(Skill):
    def __init__(self):
        super().__init__(name="FetchIntradayRelativeStrength", description="Compares a stock's intraday % return vs SPY.")
        
    def execute(self, symbol: str) -> Dict[str, Any]:
        try:
            stock = yf.Ticker(symbol)
            spy = yf.Ticker("SPY")
            
            # Fetch today's data (1m or 5m intervals)
            stock_data = stock.history(period="1d", interval="5m")
            spy_data = spy.history(period="1d", interval="5m")
            
            if stock_data.empty or spy_data.empty:
                return {"error": "Insufficient intraday data"}
                
            stock_open = stock_data['Open'].iloc[0]
            stock_last = stock_data['Close'].iloc[-1]
            stock_pct = ((stock_last - stock_open) / stock_open) * 100
            
            spy_open = spy_data['Open'].iloc[0]
            spy_last = spy_data['Close'].iloc[-1]
            spy_pct = ((spy_last - spy_open) / spy_open) * 100
            
            rs = stock_pct - spy_pct
            
            return {
                "symbol_intraday_return": round(stock_pct, 2),
                "spy_intraday_return": round(spy_pct, 2),
                "relative_strength": round(rs, 2)
            }
        except Exception as e:
            return {"error": f"Failed to fetch RS: {e}"}

class FetchGapAndVolumeSkill(Skill):
    def __init__(self):
        super().__init__(name="FetchGapAndVolume", description="Calculates the % gap from previous close and opening volume.")
        
    def execute(self, symbol: str) -> Dict[str, Any]:
        try:
            ticker = yf.Ticker(symbol)
            data = ticker.history(period="5d", interval="1d")
            if len(data) < 2:
                return {"error": "Not enough data for gap analysis"}
            
            prev_close = data['Close'].iloc[-2]
            today_open = data['Open'].iloc[-1]
            gap_pct = ((today_open - prev_close) / prev_close) * 100
            
            today_vol = data['Volume'].iloc[-1]
            prev_vol = data['Volume'].iloc[-2]
            
            return {
                "prev_close": round(prev_close, 2),
                "today_open": round(today_open, 2),
                "gap_pct": round(gap_pct, 2),
                "today_volume": today_vol,
                "prev_volume": prev_vol
            }
        except Exception as e:
            return {"error": f"Failed to fetch gap data: {e}"}

class CalculateVolumeProfileSkill(Skill):
    def __init__(self):
        super().__init__(name="CalculateVolumeProfile", description="Calculates the Point of Control (POC) price level.")
        
    def execute(self, symbol: str) -> Dict[str, Any]:
        try:
            ticker = yf.Ticker(symbol)
            data = ticker.history(period="1d", interval="5m")
            if data.empty:
                return {"error": "No intraday data available"}
                
            # Create price bins and sum volume
            min_price = data['Low'].min()
            max_price = data['High'].max()
            bins = np.linspace(min_price, max_price, num=20)
            
            # Simple approximation of volume at price
            data['PriceBin'] = pd.cut(data['Close'], bins)
            vol_profile = data.groupby('PriceBin')['Volume'].sum()
            
            if vol_profile.empty:
                 return {"error": "Failed to calculate volume profile"}
                 
            poc_bin = vol_profile.idxmax()
            poc_price = poc_bin.mid if pd.notna(poc_bin) else 0.0
            
            return {
                "poc_price": round(float(poc_price), 2),
                "poc_volume": int(vol_profile.max()),
                "total_volume": int(data['Volume'].sum())
            }
        except Exception as e:
            return {"error": f"Failed to calculate POC: {e}"}

class FetchUnusualOptionsFlowSkill(Skill):
    def __init__(self):
        super().__init__(name="FetchUnusualOptionsFlow", description="Scans options chain for volume exceeding open interest.")
        
    def execute(self, symbol: str) -> Dict[str, Any]:
        try:
            ticker = yf.Ticker(symbol)
            expirations = ticker.options
            if not expirations:
                return {"error": "No options available"}
                
            # Check near-term expiration
            exp = expirations[0]
            chain = ticker.option_chain(exp)
            
            unusual_calls = []
            for idx, row in chain.calls.iterrows():
                vol = row.get('volume', 0)
                oi = row.get('openInterest', 0)
                if pd.notna(vol) and pd.notna(oi) and oi > 0 and vol > oi * 2 and vol > 100:
                    unusual_calls.append({
                        "strike": row['strike'],
                        "volume": int(vol),
                        "open_interest": int(oi),
                        "type": "CALL"
                    })
            
            unusual_puts = []
            for idx, row in chain.puts.iterrows():
                vol = row.get('volume', 0)
                oi = row.get('openInterest', 0)
                if pd.notna(vol) and pd.notna(oi) and oi > 0 and vol > oi * 2 and vol > 100:
                    unusual_puts.append({
                        "strike": row['strike'],
                        "volume": int(vol),
                        "open_interest": int(oi),
                        "type": "PUT"
                    })
                    
            return {
                "expiration": exp,
                "unusual_calls": unusual_calls,
                "unusual_puts": unusual_puts
            }
        except Exception as e:
            return {"error": f"Failed to fetch unusual options flow: {e}"}

class FetchSectorRotationSkill(Skill):
    def __init__(self):
        super().__init__(name="FetchSectorRotation", description="Compares 1-month momentum of Sector ETFs vs SPY.")
        
    def execute(self) -> Dict[str, Any]:
        sectors = {
            "XLK": "Technology", "XLF": "Financials", "XLV": "Health Care",
            "XLE": "Energy", "XLY": "Consumer Discr", "XLP": "Consumer Staples",
            "XLI": "Industrials", "XLC": "Communication", "XLU": "Utilities",
            "XLRE": "Real Estate", "XLB": "Materials"
        }
        try:
            tickers = list(sectors.keys()) + ["SPY"]
            data = yf.download(tickers, period="1mo", interval="1d")['Close']
            
            returns = {}
            for t in tickers:
                if t in data.columns:
                    first = data[t].dropna().iloc[0]
                    last = data[t].dropna().iloc[-1]
                    returns[t] = ((last - first) / first) * 100
                    
            spy_return = returns.get("SPY", 0.0)
            
            outperforming = []
            underperforming = []
            for t, r in returns.items():
                if t == "SPY": continue
                if r > spy_return:
                    outperforming.append({"sector": sectors[t], "etf": t, "return": round(r, 2)})
                else:
                    underperforming.append({"sector": sectors[t], "etf": t, "return": round(r, 2)})
            
            outperforming.sort(key=lambda x: x["return"], reverse=True)
            underperforming.sort(key=lambda x: x["return"])
            
            return {
                "spy_return": round(spy_return, 2),
                "outperforming_sectors": outperforming,
                "underperforming_sectors": underperforming
            }
        except Exception as e:
            return {"error": f"Failed to fetch sector rotation: {e}"}

class FetchInsiderTradingSkill(Skill):
    def __init__(self):
        super().__init__(name="FetchInsiderTrading", description="Pulls recent insider purchases.")
        
    def execute(self, symbol: str) -> Dict[str, Any]:
        try:
            ticker = yf.Ticker(symbol)
            purchases = ticker.insider_purchases
            if purchases is None or (isinstance(purchases, pd.DataFrame) and purchases.empty):
                return {"recent_purchases": []}
                
            if isinstance(purchases, pd.DataFrame):
                # Clean up and return recent rows
                p_list = purchases.head(5).to_dict(orient="records")
                return {"recent_purchases": p_list}
            else:
                return {"recent_purchases": purchases}
        except Exception as e:
            return {"error": f"Failed to fetch insider trading data: {e}"}

