import logging
from neo4j import GraphDatabase
from datetime import datetime

logger = logging.getLogger(__name__)

class TemporalGraphDB:
    def __init__(self, uri, user, password):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
        
    def close(self):
        self.driver.close()
        
    def setup_schema(self):
        """
        Creates the constraints and indexes for the temporal graph.
        """
        queries = [
            "CREATE CONSTRAINT company_ticker IF NOT EXISTS FOR (c:Company) REQUIRE c.ticker IS UNIQUE",
            "CREATE CONSTRAINT event_id IF NOT EXISTS FOR (e:MarketEvent) REQUIRE e.event_id IS UNIQUE",
            "CREATE INDEX company_name IF NOT EXISTS FOR (c:Company) ON (c.name)",
            "CREATE INDEX date_index IF NOT EXISTS FOR ()-[r:CORRELATED_WITH]-() ON (r.date)",
            "CREATE INDEX supply_date IF NOT EXISTS FOR ()-[r:SUPPLIES_TO]-() ON (r.start_date, r.end_date)"
        ]
        
        with self.driver.session() as session:
            for query in queries:
                session.run(query)
        logger.info("Neo4j temporal schema configured successfully.")

    def add_company(self, ticker: str, name: str, sector: str):
        """
        Adds a Company node to the graph.
        """
        query = """
        MERGE (c:Company {ticker: $ticker})
        SET c.name = $name, c.sector = $sector
        RETURN c
        """
        with self.driver.session() as session:
            session.run(query, ticker=ticker, name=name, sector=sector)

    def record_correlation(self, ticker1: str, ticker2: str, date: str, correlation_score: float):
        """
        Creates a time-stamped CORRELATED_WITH edge between two companies.
        `date` should be ISO format YYYY-MM-DD.
        """
        query = """
        MATCH (c1:Company {ticker: $ticker1})
        MATCH (c2:Company {ticker: $ticker2})
        MERGE (c1)-[r:CORRELATED_WITH {date: date($date)}]->(c2)
        SET r.score = $score
        """
        with self.driver.session() as session:
            session.run(query, ticker1=ticker1, ticker2=ticker2, date=date, score=correlation_score)

    def record_supply_chain(self, supplier_ticker: str, buyer_ticker: str, start_date: str, end_date: str = None):
        """
        Records a temporal supply chain relationship.
        If end_date is None, the relationship is currently active.
        """
        query = """
        MATCH (s:Company {ticker: $supplier})
        MATCH (b:Company {ticker: $buyer})
        MERGE (s)-[r:SUPPLIES_TO {start_date: date($start_date)}]->(b)
        """
        params = {"supplier": supplier_ticker, "buyer": buyer_ticker, "start_date": start_date}
        
        if end_date:
            query += "SET r.end_date = date($end_date)"
            params["end_date"] = end_date
            
        with self.driver.session() as session:
            session.run(query, **params)

    def query_historical_correlation_shift(self, ticker: str, start_date: str, end_date: str):
        """
        Example GraphRAG retrieval query:
        Find how a company's correlation with other sectors shifted over a specific time window.
        """
        query = """
        MATCH (c:Company {ticker: $ticker})-[r:CORRELATED_WITH]->(other:Company)
        WHERE r.date >= date($start) AND r.date <= date($end)
        RETURN other.sector AS sector, avg(r.score) AS average_correlation
        ORDER BY average_correlation DESC
        """
        with self.driver.session() as session:
            result = session.run(query, ticker=ticker, start=start_date, end=end_date)
            return [{"sector": record["sector"], "correlation": record["average_correlation"]} for record in result]

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("Testing Neo4j connection stub...")
    # Example usage (will fail if Neo4j is not running):
    # db = TemporalGraphDB("bolt://localhost:7687", "neo4j", "invest1234")
    # db.setup_schema()
    # db.close()
