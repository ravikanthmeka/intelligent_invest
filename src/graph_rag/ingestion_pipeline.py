import logging
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
import time
from .temporal_graph import TemporalGraphDB

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class GraphIngestionPipeline:
    def __init__(self, uri="bolt://localhost:7687", user="neo4j", password="invest1234"):
        self.db = TemporalGraphDB(uri, user, password)
        
    def setup(self):
        self.db.setup_schema()

    def ingest_companies(self, company_data):
        """
        company_data: list of dicts [{"ticker": "AAPL", "name": "Apple Inc", "sector": "Technology"}, ...]
        """
        for data in company_data:
            self.db.add_company(data["ticker"], data["name"], data["sector"])
            logger.info(f"Added company node: {data['ticker']}")

    def calculate_and_ingest_correlations(self, tickers, start_date, end_date, window_days=90):
        """
        Fetches historical price data and calculates rolling correlations,
        then ingests these edges into Neo4j with temporal tags.
        """
        logger.info(f"Fetching data for {tickers} from {start_date} to {end_date}")
        data = yf.download(tickers, start=start_date, end=end_date)['Close']
        
        # Calculate daily returns
        returns = data.pct_change().dropna()
        
        # We will step through time and calculate a 90-day rolling correlation
        # and ingest it periodically (e.g. at the end of every month)
        dates = returns.index
        
        for i in range(window_days, len(dates), 30): # step by roughly a month
            current_date = dates[i]
            window_returns = returns.iloc[i-window_days:i]
            
            corr_matrix = window_returns.corr()
            
            date_str = current_date.strftime('%Y-%m-%d')
            logger.info(f"Ingesting correlations for {date_str}")
            
            for t1 in tickers:
                for t2 in tickers:
                    if t1 != t2:
                        corr_val = corr_matrix.loc[t1, t2]
                        if not pd.isna(corr_val) and abs(corr_val) > 0.5: # only significant correlations
                            self.db.record_correlation(t1, t2, date_str, float(corr_val))

    def close(self):
        self.db.close()

if __name__ == "__main__":
    # Example Usage
    pipeline = GraphIngestionPipeline()
    try:
        pipeline.setup()
        
        companies = [
            {"ticker": "AAPL", "name": "Apple", "sector": "Technology"},
            {"ticker": "MSFT", "name": "Microsoft", "sector": "Technology"},
            {"ticker": "XOM", "name": "Exxon", "sector": "Energy"},
            {"ticker": "CVX", "name": "Chevron", "sector": "Energy"}
        ]
        
        pipeline.ingest_companies(companies)
        
        start = (datetime.now() - timedelta(days=5*365)).strftime('%Y-%m-%d')
        end = datetime.now().strftime('%Y-%m-%d')
        
        tickers = [c["ticker"] for c in companies]
        pipeline.calculate_and_ingest_correlations(tickers, start, end)
        
        logger.info("Ingestion complete.")
    finally:
        pipeline.close()
