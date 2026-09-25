import asyncio
from ib_insync import IB
import json

async def main():
    ib = IB()
    print("Connecting to IBKR...")
    try:
        await ib.connectAsync('127.0.0.1', 4001, clientId=777)
    except Exception as e:
        print(f"Connection failed: {e}")
        return
        
    print("ACCOUNT VALUES:")
    acc_values = ib.accountValues()
    keys = ['NetLiquidation', 'TotalCashValue']
    for v in acc_values:
        if v.tag in keys:
            print(f"{v.tag}: {v.value}")
            
    print("\nPOSITIONS:")
    for p in ib.positions():
        print(f"SYMBOL: {p.contract.symbol} | POS: {p.position} | AVG COST: {p.avgCost}")
        
    print("\nRECENT TRADES:")
    for t in ib.trades():
        print(f"TRADE: {t.contract.symbol} {t.order.action} {t.order.totalQuantity} | STATUS: {t.orderStatus.status}")
        
    ib.disconnect()

asyncio.run(main())
