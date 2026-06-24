"""
MarketDataPoller
================
Polls OHLCV bars from MetaTrader 5 and upserts them into the database.

Fixes vs. original:
  1. datetime.fromtimestamp() now uses tz=timezone.utc — MT5 timestamps are
     Unix UTC; naive datetimes caused silent off-by-1h errors in DST regions.
  2. Bare ``except`` replaced with ``IntegrityError`` — only duplicate-key
     violations are silently skipped; all other DB errors now propagate.
  3. Removed module-level ``logging.basicConfig()`` call (belongs in app entry).
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from config.settings import settings
from database.schemas import MarketBar
from src.data_layer.mt5_connector import mt5_connector

logger = logging.getLogger(__name__)


class MarketDataPoller:
    """
    Polls market data from MT5 and stores it in the database.

    Usage::

        poller = MarketDataPoller(db_session)
        await poller.poll_symbol('EURUSD', 'H1', count=500)
    """

    def __init__(self, db_session: Session) -> None:
        self.db = db_session

    # ------------------------------------------------------------------ #
    #  Public API                                                          #
    # ------------------------------------------------------------------ #

    async def poll_symbol(
        self,
        symbol: str,
        timeframe: str = settings.DEFAULT_TIMEFRAME,
        count: int = 500,
    ) -> bool:
        """
        Fetch the latest ``count`` bars for *symbol* / *timeframe* from MT5
        and upsert them into the ``market_bars`` table.

        Returns
        -------
        True  – at least one bar was successfully saved.
        False – connection failed or no rates received.
        """
        logger.info("Polling %s [%s] — %d bars requested", symbol, timeframe, count)

        # ── 1. Ensure MT5 connection ──────────────────────────────────
        if not mt5_connector.is_connected():
            if not mt5_connector.connect():
                logger.error("Could not connect to MT5 for %s", symbol)
                return False

        # ── 2. Fetch rates ────────────────────────────────────────────
        rates = mt5_connector.get_rates(symbol, timeframe, count)
        if not rates:
            logger.error("No rates received for %s [%s]", symbol, timeframe)
            return False

        # ── 3. Upsert bars ────────────────────────────────────────────
        saved_count = 0
        for rate in rates:
            # FIX #1: Use timezone-aware UTC datetime
            dt_open = datetime.fromtimestamp(rate["time"], tz=timezone.utc)

            bar = MarketBar(
                symbol=symbol,
                timeframe=timeframe,
                open_time=dt_open,
                open=rate["open"],
                high=rate["high"],
                low=rate["low"],
                close=rate["close"],
                volume=rate["tick_volume"],
                spread=rate.get("spread", 0),
            )

            try:
                self.db.merge(bar)
                saved_count += 1
            except IntegrityError:
                # FIX #2: Only swallow duplicate-key violations
                self.db.rollback()
                logger.debug("Duplicate bar skipped: %s @ %s", symbol, dt_open)
            except Exception:
                # All other DB errors must surface — don't swallow them
                self.db.rollback()
                logger.exception("Unexpected error saving bar %s @ %s", symbol, dt_open)
                raise

        self.db.commit()
        logger.info("Saved %d/%d bars for %s [%s]", saved_count, len(rates), symbol, timeframe)
        return saved_count > 0

    async def poll_all_symbols(self) -> Dict[str, bool]:
        """
        Poll all symbols listed in ``settings.MONITORED_SYMBOLS``.

        Returns a dict mapping each symbol to its poll result (True/False).
        """
        results: Dict[str, bool] = {}
        for symbol in settings.MONITORED_SYMBOLS:
            results[symbol] = await self.poll_symbol(symbol)
        return results
