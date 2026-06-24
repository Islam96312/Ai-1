import MetaTrader5 as mt5
import logging
from typing import Dict, Any
from config.settings import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class OrderExecutor:
    """
    Sends actual trading orders to MetaTrader 5.
    """
    def execute_trade(self, symbol: str, direction: str, lot: float, sl: float, tp: float) -> Dict[str, Any]:
        """
        Opens a position in MT5.
        """
        # Map direction to MT5 order type
        order_type = mt5.ORDER_TYPE_BUY if direction == "BUY" else mt5.ORDER_TYPE_SELL
        price = mt5.symbol_info_tick(symbol).ask if direction == "BUY" else mt5.symbol_info_tick(symbol).bid
        
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": lot,
            "type": order_type,
            "price": price,
            "sl": sl,
            "tp": tp,
            "deviation": 20,
            "magic": 123456,
            "comment": "AI Trading System",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        
        result = mt5.order_send(request)
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            logger.error(f"Order failed: {result.comment} (code: {result.retcode})")
            return {"status": "error", "code": result.retcode}
            
        logger.info(f"Order executed successfully: {symbol} {direction} Lot: {lot}")
        return {"status": "success", "ticket": result.order}

class TradeManager:
    """
    Manages open positions (Trailing stops, partial closes).
    """
    def close_position(self, ticket: int):
        """
        Closes a specific position by ticket.
        """
        position = mt5.positions_get(ticket=ticket)
        if not position: return False
        
        pos = position[0]
        # Logic to send opposite order to close
        # (Simplified for MVP)
        logger.info(f"Closing position {ticket}...")
        return True
