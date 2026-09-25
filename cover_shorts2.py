import asyncio
from ib_insync import IB, Stock, MarketOrder

async def main():
    ib = IB()
    print("Connecting to IBKR...")
    await ib.connectAsync('127.0.0.1', 4001, clientId=887)
    print("Connected.")
    
    positions = ib.positions()
    print("ALL POSITIONS:")
    for p in positions:
        print(f"SYMBOL: {p.contract.symbol} | POS: {p.position} | AVG COST: {p.avgCost}")
                
    ib.disconnect()

asyncio.run(main())
