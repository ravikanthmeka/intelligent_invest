import asyncio
from ib_insync import IB, Stock, MarketOrder

async def main():
    ib = IB()
    print("Connecting to IBKR...")
    await ib.connectAsync('127.0.0.1', 4001, clientId=889)
    print("Connected.")
    
    positions = ib.positions()
    short_symbols = ['AAPL', 'MU']
    
    for p in positions:
        sym = p.contract.symbol
        if sym in short_symbols and p.position < 0:
            shares_to_buy = abs(p.position)
            print(f"Found SHORT position for {sym}: {p.position} shares. Buying to cover {shares_to_buy} shares...")
            
            contract = Stock(sym, 'SMART', 'USD')
            await ib.qualifyContractsAsync(contract)
            
            order = MarketOrder("BUY", shares_to_buy)
            trade = ib.placeOrder(contract, order)
            
            # Wait for fill
            max_wait = 15
            elapsed = 0
            while not trade.isDone() and elapsed < max_wait:
                await asyncio.sleep(1)
                elapsed += 1
                
            if trade.orderStatus.status == 'Filled':
                print(f"SUCCESS: Covered {sym} at Avg Price {trade.orderStatus.avgFillPrice}")
            else:
                print(f"WARNING: Order for {sym} did not fill. Status: {trade.orderStatus.status}")
                
    ib.disconnect()

asyncio.run(main())
