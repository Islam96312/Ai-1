import asyncio
import logging
import time
from src.data_layer.mt5_connector import mt5_connector
from config.settings import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SystemWatchdog:
    """
    Monitors system health and handles auto-recovery.
    """
    def __init__(self):
        self.check_interval = 60 # seconds
        self.is_running = True

    async def monitor_mt5(self):
        """
        Constantly checks MT5 connection and reconnects if needed.
        """
        logger.info("Watchdog: MT5 Monitoring started.")
        while self.is_running:
            if not mt5_connector.is_connected():
                logger.warning("Watchdog: MT5 connection lost! Attempting recovery...")
                success = mt5_connector.connect()
                if success:
                    logger.info("Watchdog: MT5 recovery successful.")
                else:
                    logger.error("Watchdog: MT5 recovery failed. Retrying in 30s...")
            
            await asyncio.sleep(self.check_interval)

    def stop(self):
        self.is_running = False
