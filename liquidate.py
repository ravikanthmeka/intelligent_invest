import asyncio
from ib_insync import IB, Stock, MarketOrder

async def main():
    ib = IB()
    print("Connecting to IBKR...")
    await ib.connectAsync('127.0.0.1', 4001, clientId=890)
    print("Connected.")
    
    sym = 'CLX'
    shares_to_sell = 8
    
    print(f"Selling {shares_to_sell} shares of {sym}...")
    
    contract = Stock(sym, 'SMART', 'USD')
    await ib.qualifyContractsAsync(contract)
    
    order = MarketOrder("SELL", shares_to_sell)
    trade = ib.placeOrder(contract, order)
    
    # Wait for fill
    max_wait = 15
    elapsed = 0
    while not trade.isDone() and elapsed < max_wait:
        await asyncio.sleep(1)
        elapsed += 1
        
    if trade.orderStatus.status == 'Filled':
        print(f"SUCCESS: Sold {sym} at Avg Price {trade.orderStatus.avgFillPrice}")
    else:
        print(f"WARNING: Order for {sym} did not fill. Status: {trade.orderStatus.status}")
                
    ib.disconnect()

asyncio.run(main())
