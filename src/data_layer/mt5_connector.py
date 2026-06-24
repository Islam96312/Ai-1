import MetaTrader5 as mt5
import logging
from config.settings import settings
from typing import Optional, List

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MT5Connector:
    """
    Handles the connection lifecycle and basic communication with MetaTrader 5.
    """
    def __init__(self):
        self._is_connected = False

    def connect(self) -> bool:
        """
        Initializes connection to MT5 terminal.
        """
        try:
            # Attempt to initialize MT5
            if not mt5.initialize(
                login=settings.MT5_LOGIN,
                password=settings.MT5_PASSWORD,
                server=settings.MT5_SERVER,
                path=settings.MT5_PATH
            ):
                logger.error(f"MT5 initialize() failed: {mt5.last_error()}")
                return False
            
            self._is_connected = True
            logger.info("Successfully connected to MetaTrader 5")
            return True
        except Exception as e:
            logger.exception(f"Unexpected error connecting to MT5: {e}")
            return False

    def disconnect(self):
        """
        Shuts down the MT5 connection.
        """
        if self._is_connected:
            mt5.shutdown()
            self._is_connected = False
            logger.info("Disconnected from MetaTrader 5")

    def is_connected(self) -> bool:
        return self._is_connected

    def get_symbol_info(self, symbol: str) -> Optional[dict]:
        """
        Get detailed information about a specific symbol.
        """
        if not self.is_connected():
            logger.warning("Attempted to get symbol info while disconnected.")
            return None
            
        info = mt5.symbol_info(symbol)
        if info is None:
            logger.error(f"Symbol {symbol} not found in MT5.")
            return None
        return info._asdict()

    def get_rates(self, symbol: str, timeframe: str, count: int = 1000) -> Optional[List[dict]]:
        """
        Fetch historical bars/rates for a symbol.
        """
        if not self.is_connected():
            return None

        # Map string timeframe to MT5 constants
        tf_map = {
            "M1": mt5.TIMEFRAME_M1,
            "M5": mt5.TIMEFRAME_M5,
            "M15": mt5.TIMEFRAME_M15,
            "M30": mt5.TIMEFRAME_M30,
            "H1": mt5.TIMEFRAME_H1,
            "H4": mt5.TIMEFRAME_H4,
            "D1": mt5.TIMEFRAME_D1,
        }
        
        mt5_tf = tf_map.get(timeframe.upper())
        if mt5_tf is None:
            logger.error(f"Unsupported timeframe: {timeframe}")
            return None

        rates = mt5.copy_rates_from_pos(symbol, mt5_tf, 0, count)
        if rates is None:
            logger.error(f"Failed to get rates for {symbol}: {mt5.last_error()}")
            return None
            
        # Convert numpy structured array to list of dicts
        return [dict(zip(rates.dtype.names, row)) for row in rates]

# Singleton instance
mt5_connector = MT5Connector()
