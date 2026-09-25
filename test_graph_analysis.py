import sys
import logging
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from src.llm import LLMClient
from src.agents.specialized import FundamentalAgent

def run_test():
    llm = LLMClient(provider="bedrock") # Use bedrock since we might not have OPENAI_API_KEY
    agent = FundamentalAgent(llm)
    
    ticker = "AAPL"
    logger.info(f"Running FundamentalAgent analysis for {ticker}...")
    
    result = agent.analyze(ticker, include_context=True)
    
    logger.info(f"Final Score: {result.get('score')}")
    logger.info(f"Rationale: {result.get('rationale')}")
    
if __name__ == "__main__":
    run_test()
