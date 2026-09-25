import asyncio
from ib_insync import IB

async def main():
    ib = IB()
    print("Connecting to IBKR...")
    await ib.connectAsync('127.0.0.1', 4001, clientId=888)
    
    acc_values = ib.accountValues()
    print("ACCOUNT VALUES:")
    keys = ['TotalCashValue', 'SettledCash', 'BuyingPower', 'AvailableFunds', 'MaintMarginReq', 'InitMarginReq', 'NetLiquidation']
    for v in acc_values:
        if v.tag in keys:
            print(f"{v.tag} [{v.currency}]: {v.value}")
                
    ib.disconnect()

asyncio.run(main())
