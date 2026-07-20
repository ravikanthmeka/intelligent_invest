import asyncio
import logging
from typing import Dict, Any, List, Optional
from ib_insync import IB, Stock, Order, MarketOrder, StopOrder, LimitOrder, PortfolioItem

logger = logging.getLogger("BrokerAPI")

class BrokerAgent:
    def __init__(self, host: str = "127.0.0.1", port: int = 4002, client_id: int = 1, dry_run: bool = True):
        self.host = host
        self.port = port
        self.client_id = client_id
        self.dry_run = dry_run
        self.ib = IB() if not dry_run else None
        self.connected = False

    async def connect(self) -> bool:
        if self.dry_run:
            logger.info("BrokerAgent initialized in DRY RUN mode. No physical connection to IB Gateway.")
            self.connected = True
            return True

        for attempt in range(1, 4):
            try:
                logger.info(f"Connecting to IB Gateway at {self.host}:{self.port} (Attempt {attempt})...")
                await self.ib.connectAsync(self.host, self.port, clientId=self.client_id, timeout=15)
                self.connected = True
                logger.info("Successfully connected to IB Gateway.")
                return True
            except Exception as e:
                logger.warning(f"Connection attempt {attempt} failed: {e}")
                await asyncio.sleep(2)
        
        logger.error("Could not connect to IB Gateway after 3 attempts.")
        return False

    async def disconnect(self):
        if self.ib and self.ib.isConnected():
            self.ib.disconnect()
            self.connected = False
            logger.info("Disconnected from IB Gateway.")

    async def get_portfolio_value(self) -> Dict[str, float]:
        """
        Retrieves Net Liquidation Value and Cash Balance.
        """
        if self.dry_run:
            # Mock portfolio value for dry run
            return {"net_liquidation": 100000.0, "cash": 100000.0}

        try:
            # Refresh details
            account_values = self.ib.accountValues()
            net_liq = 0.0
            cash = 0.0
            for val in account_values:
                if val.tag == "NetLiquidation":
                    net_liq = float(val.value)
                elif val.tag == "CashBalance" and val.currency == "USD":
                    cash = float(val.value)
            
            # If CashBalance not found, fallback to TotalCashValue
            if cash == 0.0:
                for val in account_values:
                    if val.tag == "TotalCashValue":
                        cash = float(val.value)

            return {"net_liquidation": net_liq or 100000.0, "cash": cash or 100000.0}
        except Exception as e:
            logger.error(f"Error fetching account value: {e}")
            return {"net_liquidation": 100000.0, "cash": 100000.0}

    async def get_positions(self) -> List[Dict[str, Any]]:
        """
        Returns list of active positions in the portfolio.
        """
        if self.dry_run:
            # Mock position
            return []

        try:
            portfolio = self.ib.portfolio()
            positions_data = []
            for item in portfolio:
                # item: PortfolioItem
                positions_data.append({
                    "symbol": item.contract.symbol,
                    "shares": item.position,
                    "average_cost": item.marketPrice - (item.unrealizedPNL / item.position) if item.position != 0 else item.averageCost,
                    "market_price": item.marketPrice,
                    "market_value": item.marketValue,
                    "unrealized_pnl": item.unrealizedPNL,
                    "unrealized_pnl_pct": (item.unrealizedPNL / (item.averageCost * item.position)) if (item.averageCost * item.position) != 0 else 0.0,
                    "contract": item.contract
                })
            return positions_data
        except Exception as e:
            logger.error(f"Error fetching positions: {e}")
            return []

    async def execute_buy(self, symbol: str, quantity: int, stop_loss_price: float) -> Optional[str]:
        """
        Executes a Buy order with a linked Stop Loss order.
        """
        if self.dry_run:
            logger.info(f"[DRY RUN] Buy Order Executed: Buy {quantity} shares of {symbol} with Stop Loss at ${stop_loss_price:.2f}")
            return "dry-run-order-id-123"

        try:
            contract = Stock(symbol, "SMART", "USD")
            # Quality check on contract definition
            await self.ib.qualifyContractsAsync(contract)

            # Create parent Market Buy order with transmit=False so it links with stop-loss child
            parent = MarketOrder("BUY", quantity)
            parent.transmit = False
            parent_trade = self.ib.placeOrder(contract, parent)
            
            # Create child Stop Loss order with GTC Time-In-Force linked to parent orderId
            stop_order = StopOrder("SELL", quantity, stop_loss_price)
            stop_order.parentId = parent_trade.order.orderId
            stop_order.tif = "GTC"
            stop_order.transmit = True
            stop_trade = self.ib.placeOrder(contract, stop_order)
            
            logger.info(f"Placed Bracket Buy for {symbol}: Parent OrderId {parent_trade.order.orderId}, Stop Loss OrderId {stop_trade.order.orderId} at ${stop_loss_price:.2f}")
            return str(parent_trade.order.orderId)
        except Exception as e:
            logger.error(f"Error executing buy order for {symbol}: {e}")
            return None

    async def update_stop_loss(self, symbol: str, new_stop_price: float) -> bool:
        """
        Finds and updates the existing Stop Loss order for a symbol to a new price.
        """
        if self.dry_run:
            logger.info(f"[DRY RUN] Updated Stop Loss for {symbol} to new price: ${new_stop_price:.2f}")
            return True

        try:
            # Find open orders for this stock
            open_trades = self.ib.openTrades()
            for trade in open_trades:
                if trade.contract.symbol == symbol and trade.order.orderType == "STP":
                    # Update order price
                    old_price = trade.order.auxPrice
                    trade.order.auxPrice = new_stop_price
                    # Re-place order to modify it
                    self.ib.placeOrder(trade.contract, trade.order)
                    logger.info(f"Updated Stop Loss for {symbol} from ${old_price:.2f} to ${new_stop_price:.2f}")
                    return True
            
            # If no open stop order found, create a new one
            logger.warning(f"No open Stop Loss order found for {symbol}. Creating a new one.")
            positions = await self.get_positions()
            for pos in positions:
                if pos["symbol"] == symbol:
                    contract = pos["contract"]
                    shares = pos["shares"]
                    stop_order = StopOrder("SELL", shares, new_stop_price)
                    self.ib.placeOrder(contract, stop_order)
                    logger.info(f"Created new Stop Loss order for {symbol} of {shares} shares at ${new_stop_price:.2f}")
                    return True

            logger.error(f"Could not update stop loss. Position for {symbol} not found.")
            return False
        except Exception as e:
            logger.error(f"Error updating stop loss for {symbol}: {e}")
            return False

    async def execute_sell_all(self, symbol: str) -> bool:
        """
        Liquidates the entire position in a stock.
        """
        if self.dry_run:
            logger.info(f"[DRY RUN] Sell Order Executed: Sell all shares of {symbol}")
            return True

        try:
            positions = await self.get_positions()
            shares = 0
            contract = None
            for pos in positions:
                if pos["symbol"] == symbol:
                    shares = pos["shares"]
                    contract = pos["contract"]
                    break

            if shares == 0 or not contract:
                logger.warning(f"No position found for {symbol} to liquidate.")
                return False

            # Cancel open orders for this contract first (e.g. existing stop loss)
            for trade in self.ib.openTrades():
                if trade.contract.symbol == symbol:
                    self.ib.cancelOrder(trade.order)
                    logger.info(f"Cancelled open order {trade.order.orderId} for {symbol}")

            # Execute market sell
            sell_order = MarketOrder("SELL", shares)
            trade = self.ib.placeOrder(contract, sell_order)
            logger.info(f"Executed Market Sell for {shares} shares of {symbol}")
            return True
        except Exception as e:
            logger.error(f"Error executing sell for {symbol}: {e}")
            return False
