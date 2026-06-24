import logging
from datetime import datetime
from typing import List
from sqlalchemy.orm import Session
from src.data_layer.mt5_connector import mt5_connector
from database.schemas import MarketBar
from config.settings import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MarketDataPoller:
    """
    Polls market data from MT5 and stores it in the database.
    """
    def __init__(self, db_session: Session):
        self.db = db_session

    async def poll_symbol(self, symbol: str, timeframe: str = settings.DEFAULT_TIMEFRAME, count: int = 100):
        """
        Fetch latest bars for a symbol and save to DB.
        """
        logger.info(f"Polling data for {symbol} [{timeframe}]...")
        
        if not mt5_connector.is_connected():
            if not mt5_connector.connect():
                logger.error(f"Could not connect to MT5 to poll {symbol}")
                return False

        rates = mt5_connector.get_rates(symbol, timeframe, count)
        if not rates:
            logger.error(f"No rates received for {symbol}")
            return False

        saved_count = 0
        for rate in rates:
            # Convert timestamp to datetime
            dt_open = datetime.fromtimestamp(rate['time'])
            
            # Use merge to avoid duplicates (Upsert)
            bar = MarketBar(
                symbol=symbol,
                timeframe=timeframe,
                open_time=dt_open,
                open=rate['open'],
                high=rate['high'],
                low=rate['low'],
                close=rate['close'],
                volume=rate['tick_volume'],
                spread=rate['spread']
            )
            
            # Simple duplicate check based on unique constraint
            # In a production system, we'd use a proper UPSERT (ON CONFLICT DO UPDATE)
            # For the MVP, we'll check if it exists or just let DB unique constraint handle it.
            try:
                self.db.merge(bar)
                saved_count += 1
            except Exception as e:
                logger.debug(f"Bar already exists for {symbol} at {dt_open}: {e}")
        
        self.db.commit()
        logger.info(f"Successfully saved {saved_count} bars for {symbol}")
        return True

    async def poll_all_symbols(self):
        """
        Poll all symbols configured in settings.
        """
        results = {}
        for symbol in settings.MONITORED_SYMBOLS:
            results[symbol] = await self.poll_symbol(symbol)
        return results
