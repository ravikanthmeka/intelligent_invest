import logging
import json
from src.skills.base import Skill
from .temporal_graph import TemporalGraphDB

logger = logging.getLogger(__name__)

class TemporalGraphSkill(Skill):
    """
    Skill for Trading Agents to query the Temporal GraphRAG Database.
    This integrates with the trading agent intelligence engine.
    """
    
    def __init__(self, uri="bolt://localhost:7687", user="neo4j", password="invest1234"):
        super().__init__(
            name="query_temporal_market_graph",
            description="Queries the Temporal Knowledge Graph to analyze how a stock's relationships (correlations, supply chain) with other sectors/companies evolved over a historical period."
        )
        self.uri = uri
        self.user = user
        self.password = password

    def execute(self, ticker: str, start_date: str, end_date: str) -> str:
        """
        Executes the query against the Neo4j database and returns a structured response.
        """
        logger.info(f"TemporalGraphSkill querying {ticker} from {start_date} to {end_date}")
        
        db = None
        try:
            db = TemporalGraphDB(self.uri, self.user, self.password)
            results = db.query_historical_correlation_shift(ticker, start_date, end_date)
            
            if not results:
                return json.dumps({
                    "status": "success",
                    "data": [],
                    "message": f"No correlation data found for {ticker} in the specified timeframe."
                })
                
            return json.dumps({
                "status": "success",
                "data": results,
                "message": f"Successfully retrieved correlation shifts for {ticker}."
            })
            
        except Exception as e:
            logger.error(f"Failed to query temporal graph: {e}")
            return json.dumps({
                "status": "error",
                "message": str(e)
            })
        finally:
            if db:
                db.close()
