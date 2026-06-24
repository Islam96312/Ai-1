import MetaTrader5 as mt5
import logging
from typing import Dict, Any

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TradeManager:
    """
    Dynamic Trade Management: Trailing Stops and Break-Even.
    """
    def __init__(self, atr_multiplier_sl: float = 1.5):
        self.atr_multiplier_sl = atr_multiplier_sl

    def update_active_trades(self):
        """
        Iterates through open positions and applies trailing stop logic.
        """
        positions = mt5.positions_get()
        if not positions: return

        for pos in positions:
            ticket = pos.ticket
            symbol = pos.symbol
            direction = "BUY" if pos.type == mt5.POSITION_TYPE_BUY else "SELL"
            current_price = pos.price_current
            entry_price = pos.price_open
            sl = pos.sl
            
            # 1. Break-Even Logic: Move SL to Entry if price reached TP1 (approx)
            # For simplicity, we use a fixed distance or check if profit > 20 pips
            profit_pips = (current_price - entry_price) * 10000 if direction == "BUY" else (entry_price - current_price) * 10000
            
            if profit_pips > 20 and (sl < entry_price if direction == "BUY" else sl > entry_price):
                self._modify_sl(ticket, entry_price)
                logger.info(f"Trade {ticket} moved to Break-Even")

            # 2. Trailing Stop Logic
            # Move SL up as price moves up (for BUY)
            if direction == "BUY":
                new_sl = current_price - (0.0020) # Trailing by 20 pips
                if new_sl > sl:
                    self._modify_sl(ticket, new_sl)
            else: # SELL
                new_sl = current_price + (0.0020)
                if new_sl < sl or sl == 0:
                    self._modify_sl(ticket, new_sl)

    def _modify_sl(self, ticket: int, new_sl: float):
        """
        Modifies the Stop Loss of a position in MT5.
        """
        position = mt5.positions_get(ticket=ticket)[0]
        request = {
            "action": mt5.TRADE_ACTION_SLTP,
            "position": ticket,
            "sl": new_sl,
            "tp": position.tp,
        }
        result = mt5.order_send(request)
        return result.retcode == mt5.TRADE_RETCODE_DONE
