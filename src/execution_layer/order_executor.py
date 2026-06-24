import MetaTrader5 as mt5
import logging
import time
from typing import Dict, Any

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

RETRYABLE_CODES = {
    mt5.TRADE_RETCODE_REQUOTE,
    mt5.TRADE_RETCODE_PRICE_CHANGED,
    mt5.TRADE_RETCODE_CONNECTION,
    mt5.TRADE_RETCODE_TIMEOUT,
}
MAX_RETRIES   = 3
RETRY_DELAY_S = 1.0


class OrderExecutor:
    """Sends actual trading orders to MT5 with retry logic."""

    def execute_trade(self, symbol: str, direction: str, lot: float,
                      sl: float, tp: float) -> Dict[str, Any]:
        order_type = mt5.ORDER_TYPE_BUY if direction == 'BUY' else mt5.ORDER_TYPE_SELL

        for attempt in range(1, MAX_RETRIES + 1):
            tick = mt5.symbol_info_tick(symbol)
            if tick is None:
                return {'status': 'error', 'reason': 'no_tick'}

            price   = tick.ask if direction == 'BUY' else tick.bid
            request = {
                'action':       mt5.TRADE_ACTION_DEAL,
                'symbol':       symbol,
                'volume':       lot,
                'type':         order_type,
                'price':        price,
                'sl':           sl,
                'tp':           tp,
                'deviation':    20,
                'magic':        123456,
                'comment':      'AI Trading System',
                'type_time':    mt5.ORDER_TIME_GTC,
                'type_filling': mt5.ORDER_FILLING_IOC,
            }

            result = mt5.order_send(request)

            if result.retcode == mt5.TRADE_RETCODE_DONE:
                logger.info(f'[Attempt {attempt}] Order executed: {symbol} {direction} Lot:{lot} Ticket:{result.order}')
                return {'status': 'success', 'ticket': result.order}

            if result.retcode in RETRYABLE_CODES and attempt < MAX_RETRIES:
                logger.warning(f'[Attempt {attempt}] Retryable error {result.retcode}. Retrying in {RETRY_DELAY_S}s...')
                time.sleep(RETRY_DELAY_S)
                continue

            logger.error(f'[Attempt {attempt}] Order failed: {result.comment} (code:{result.retcode})')
            return {'status': 'error', 'code': result.retcode, 'reason': result.comment}

        return {'status': 'error', 'reason': 'max_retries_exceeded'}
