
import asyncio
from ib_insync import *
async def check_orders():
    ib = IB()
    try:
        await ib.connectAsync('127.0.0.1', 4001, clientId=999)
        trades = ib.trades()
        for t in trades:
            if t.contract.symbol == 'WFC':
                print(f'WFC Trade Status: {t.orderStatus.status}')
        print('All Open Orders:', len(ib.openOrders()))
        ib.disconnect()
    except Exception as e:
        print('Error:', e)
asyncio.run(check_orders())
