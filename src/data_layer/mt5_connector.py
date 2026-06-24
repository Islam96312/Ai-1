import logging
from config.settings import settings
from typing import Optional, List, Dict, Any

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

try:
    import MetaTrader5 as mt5
    MT5_AVAILABLE = True
except ImportError:
    MT5_AVAILABLE = False
    logger.warning('MetaTrader5 library not installed (Linux/Mac). MT5 functions will be disabled.')


class MT5Connector:
    """
    Handles the connection lifecycle and basic communication with MetaTrader 5.
    NOTE: MetaTrader5 Python library requires Windows.
    """

    def __init__(self):
        self._is_connected = False

    def connect(self) -> bool:
        if not MT5_AVAILABLE:
            logger.error('MT5 not available on this platform.')
            return False
        try:
            if not mt5.initialize(
                login=settings.MT5_LOGIN,
                password=settings.MT5_PASSWORD,
                server=settings.MT5_SERVER,
                path=settings.MT5_PATH,
            ):
                logger.error('MT5 initialize() failed: %s', mt5.last_error())
                return False
            self._is_connected = True
            info = mt5.account_info()
            logger.info('Connected to MT5 | Account: %s | Balance: %.2f %s',
                        info.login, info.balance, info.currency)
            return True
        except Exception as e:
            logger.exception('Unexpected error connecting to MT5: %s', e)
            return False

    def disconnect(self):
        if self._is_connected and MT5_AVAILABLE:
            mt5.shutdown()
            self._is_connected = False
            logger.info('Disconnected from MetaTrader 5')

    def is_connected(self) -> bool:
        return self._is_connected and MT5_AVAILABLE

    # ------------------------------------------------------------------ #
    #  Account Info                                                        #
    # ------------------------------------------------------------------ #
    def get_account_info(self) -> Optional[Dict[str, Any]]:
        """Returns account balance, equity, margin, etc."""
        if not self.is_connected():
            return None
        try:
            info = mt5.account_info()
            if info is None:
                return None
            return {
                'login':        info.login,
                'balance':      info.balance,
                'equity':       info.equity,
                'margin':       info.margin,
                'free_margin':  info.margin_free,
                'margin_level': info.margin_level,
                'currency':     info.currency,
                'leverage':     info.leverage,
                'profit':       info.profit,
            }
        except Exception as e:
            logger.error('get_account_info error: %s', e)
            return None

    # ------------------------------------------------------------------ #
    #  Open Trades                                                         #
    # ------------------------------------------------------------------ #
    def get_open_trades(self) -> List[Dict[str, Any]]:
        """Returns all currently open positions."""
        if not self.is_connected():
            return []
        try:
            positions = mt5.positions_get()
            if positions is None:
                return []
            result = []
            for p in positions:
                d = p._asdict()
                result.append({
                    'ticket':  d['ticket'],
                    'symbol':  d['symbol'],
                    'lot':     d['volume'],
                    'type':    'BUY' if d['type'] == 0 else 'SELL',
                    'profit':  d['profit'],
                    'sl':      d['sl'],
                    'tp':      d['tp'],
                    'price_open': d['price_open'],
                    'risk_pips':  abs(d['price_open'] - d['sl']) / 0.0001 if d['sl'] else 0,
                })
            return result
        except Exception as e:
            logger.error('get_open_trades error: %s', e)
            return []

    # ------------------------------------------------------------------ #
    #  Symbol Info & Rates                                                #
    # ------------------------------------------------------------------ #
    def get_symbol_info(self, symbol: str) -> Optional[Dict[str, Any]]:
        if not self.is_connected():
            return None
        info = mt5.symbol_info(symbol)
        if info is None:
            logger.error('Symbol %s not found in MT5', symbol)
            return None
        return info._asdict()

    def get_rates(self, symbol: str, timeframe: str, count: int = 1000) -> Optional[List[dict]]:
        if not self.is_connected():
            return None
        tf_map = {
            'M1':  mt5.TIMEFRAME_M1,  'M5':  mt5.TIMEFRAME_M5,
            'M15': mt5.TIMEFRAME_M15, 'M30': mt5.TIMEFRAME_M30,
            'H1':  mt5.TIMEFRAME_H1,  'H4':  mt5.TIMEFRAME_H4,
            'D1':  mt5.TIMEFRAME_D1,
        }
        mt5_tf = tf_map.get(timeframe.upper())
        if mt5_tf is None:
            logger.error('Unsupported timeframe: %s', timeframe)
            return None
        rates = mt5.copy_rates_from_pos(symbol, mt5_tf, 0, count)
        if rates is None:
            logger.error('Failed to get rates for %s: %s', symbol, mt5.last_error())
            return None
        return [dict(zip(rates.dtype.names, row)) for row in rates]


# Singleton instance
mt5_connector = MT5Connector()
