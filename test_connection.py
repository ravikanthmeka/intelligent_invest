import sys
import os

sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from ib_insync import IB

if __name__ == "__main__":
    ib = IB()
    try:
        print("Connecting with clientId=88...")
        ib.connect('127.0.0.1', 4001, clientId=88)
        print("Connected successfully!")
        print(f"Managed Accounts: {ib.managedAccounts()}")
        
        print("Fetching positions...")
        positions = ib.positions()
        print(f"Positions count: {len(positions)}")
        
        print("Fetching account values...")
        vals = ib.accountValues()
        print(f"Account values count: {len(vals)}")
        
        ib.disconnect()
    except Exception as e:
        print(f"Connection/Query failed: {e}")
