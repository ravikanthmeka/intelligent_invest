import sys
import os

sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from ib_insync import IB

if __name__ == "__main__":
    ib = IB()
    try:
        ib.connect('127.0.0.1', 4001, clientId=123)
        print("Connected successfully to Live Trading Port 4001!")
        print(f"Account: {ib.managedAccounts()}")
        ib.disconnect()
    except Exception as e:
        print(f"Failed to connect: {e}")
