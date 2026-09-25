import asyncio
from ib_insync import IB
import json

async def main():
    ib = IB()
    await ib.connectAsync('127.0.0.1', 4001, clientId=55)
    
    positions = ib.positions()
    pos_list = []
    for p in positions:
        pos_list.append({
            'symbol': p.contract.symbol,
            'shares': p.position,
            'avgCost': p.avgCost
        })
    print('POSITIONS:', json.dumps(pos_list))
    
    # Get recent trades
    fills = ib.fills()
    fill_list = []
    for f in fills:
        fill_list.append({
            'symbol': f.contract.symbol,
            'action': f.execution.side,
            'shares': f.execution.shares,
            'price': f.execution.price
        })
    print('FILLS:', json.dumps(fill_list))
    
    ib.disconnect()

asyncio.run(main())
