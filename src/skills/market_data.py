import logging
import pandas as pd
import yfinance as yf
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
        try:
            ticker_obj = yf.Ticker(symbol)
            # yfinance returns list of dicts for news
            news = ticker_obj.news
            return news[:5] if news else []
        except Exception as e:
            logger.error(f"Error fetching news for {symbol}: {e}")
            return []
