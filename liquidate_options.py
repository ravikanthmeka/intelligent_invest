import asyncio
from ib_insync import IB, Option, MarketOrder

async def main():
    ib = IB()
    print("Connecting to IBKR...")
    await ib.connectAsync('127.0.0.1', 4001, clientId=891)
    print("Connected.")
    
    positions = ib.positions()
    
    for p in positions:
        if type(p.contract) == Option and p.position > 0:
            sym = p.contract.symbol
            shares_to_sell = int(p.position)
            print(f"Liquidating {shares_to_sell} contracts of Option {sym} ({p.contract.localSymbol})...")
            
            # The contract from ib.positions() might need qualification
            contract = p.contract
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
                print(f"SUCCESS: Sold {sym} Option at Avg Price {trade.orderStatus.avgFillPrice}")
            else:
                print(f"WARNING: Order for {sym} Option did not fill. Status: {trade.orderStatus.status}")
                
    ib.disconnect()

asyncio.run(main())
