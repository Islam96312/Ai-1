"""
RiskEngine
==========
Calculates SL, TP1, TP2, R:R and pip risk for a proposed trade.

Logic:
  - Uses ATR-based dynamic stops (configurable multipliers).
  - Falls back to a fixed pip_size multiple if ATR is unavailable.
  - Handles Decimal values from SQLAlchemy without TypeError.
  - pip_size is symbol-aware (JPY pairs, metals, crypto).
"""

from __future__ import annotations

import logging
import os
from decimal import Decimal
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# Default multipliers (overridable via config YAML)
_DEFAULT_SL_ATR_MULT  = 1.5
_DEFAULT_TP1_ATR_MULT = 2.0
_DEFAULT_TP2_ATR_MULT = 3.5

# Pip sizes by symbol (fallback map)
_PIP_SIZES: Dict[str, float] = {
    'default': 0.0001,
    'JPY':     0.01,      # any pair containing JPY
    'XAUUSD':  0.1,       # Gold
    'XAGUSD':  0.001,     # Silver
    'BTCUSD':  1.0,       # Bitcoin
    'ETHUSD':  0.1,       # Ethereum
    'USDJPY':  0.01,
    'EURJPY':  0.01,
    'GBPJPY':  0.01,
    'CADJPY':  0.01,
    'AUDJPY':  0.01,
    'CHFJPY':  0.01,
    'NZDJPY':  0.01,
}


class RiskEngine:
    """
    Calculates trade levels for a given symbol, direction, and price.

    Usage::

        engine = RiskEngine()
        levels = engine.calculate_levels('EURUSD', 'BUY', 1.09000, features)
        # levels = {'entry', 'stop_loss', 'take_profit_1', 'take_profit_2',
        #           'risk_pips', 'risk_reward'}
    """

    def __init__(self, config_path: str = 'config/risk_config.yaml') -> None:
        self.sl_mult  = _DEFAULT_SL_ATR_MULT
        self.tp1_mult = _DEFAULT_TP1_ATR_MULT
        self.tp2_mult = _DEFAULT_TP2_ATR_MULT
        self._load_config(config_path)

    # ------------------------------------------------------------------ #
    #  Config loader                                                       #
    # ------------------------------------------------------------------ #
    def _load_config(self, path: str) -> None:
        if not os.path.exists(path):
            return
        try:
            import yaml  # optional — only needed if config file exists
            with open(path) as f:
                cfg = yaml.safe_load(f) or {}
            re_cfg = cfg.get('risk_engine', {})
            self.sl_mult  = float(re_cfg.get('sl_atr_mult',  self.sl_mult))
            self.tp1_mult = float(re_cfg.get('tp1_atr_mult', self.tp1_mult))
            self.tp2_mult = float(re_cfg.get('tp2_atr_mult', self.tp2_mult))
            logger.info('RiskEngine: loaded config from %s', path)
        except Exception as exc:
            logger.warning('RiskEngine: could not load config (%s). Using defaults.', exc)

    # ------------------------------------------------------------------ #
    #  Public API                                                          #
    # ------------------------------------------------------------------ #
    def calculate_levels(
        self,
        symbol: str,
        direction: str,
        entry_price: float,
        features: Any,
    ) -> Dict[str, float]:
        """
        Return a dict with SL, TP1, TP2, risk_pips, and risk_reward.

        Parameters
        ----------
        symbol      : e.g. 'EURUSD', 'XAUUSD'
        direction   : 'BUY' or 'SELL'
        entry_price : current ask/bid price (float)
        features    : TechnicalFeature ORM object (must have .atr_14 attribute)
        """
        direction = direction.upper()
        pip_size  = self._get_pip_size(symbol)

        # --- Resolve ATR (Decimal-safe) --------------------------------
        atr_raw = getattr(features, 'atr_14', None)
        if atr_raw is not None:
            try:
                atr = float(atr_raw)
            except (TypeError, ValueError):
                atr = None
        else:
            atr = None

        # --- Fallback if ATR missing or zero ---------------------------
        if not atr:
            atr = pip_size * 15  # 15-pip default
            logger.debug('%s: ATR unavailable, using fallback ATR=%.6f', symbol, atr)

        # --- SL distance -----------------------------------------------
        sl_distance  = round(atr * self.sl_mult,  6)
        tp1_distance = round(atr * self.tp1_mult, 6)
        tp2_distance = round(atr * self.tp2_mult, 6)

        # --- Calculate levels ------------------------------------------
        if direction == 'BUY':
            stop_loss     = round(entry_price - sl_distance,  6)
            take_profit_1 = round(entry_price + tp1_distance, 6)
            take_profit_2 = round(entry_price + tp2_distance, 6)
        else:  # SELL
            stop_loss     = round(entry_price + sl_distance,  6)
            take_profit_1 = round(entry_price - tp1_distance, 6)
            take_profit_2 = round(entry_price - tp2_distance, 6)

        # --- pip risk & R:R --------------------------------------------
        risk_pips    = round(sl_distance  / pip_size, 1)
        reward_pips  = round(tp1_distance / pip_size, 1)
        risk_reward  = round(reward_pips / risk_pips, 2) if risk_pips > 0 else 0.0

        result = {
            'entry':        round(entry_price, 6),
            'stop_loss':    stop_loss,
            'take_profit_1': take_profit_1,
            'take_profit_2': take_profit_2,
            'risk_pips':    risk_pips,
            'reward_pips':  reward_pips,
            'risk_reward':  float(risk_reward),
        }

        logger.debug(
            '%s %s | entry=%.5f SL=%.5f TP1=%.5f TP2=%.5f R:R=%.2f',
            direction, symbol,
            result['entry'], result['stop_loss'],
            result['take_profit_1'], result['take_profit_2'],
            result['risk_reward'],
        )
        return result

    # ------------------------------------------------------------------ #
    #  Helpers                                                             #
    # ------------------------------------------------------------------ #
    def _get_pip_size(self, symbol: str) -> float:
        """Return the pip/tick size for a given symbol."""
        symbol_upper = symbol.upper()
        if symbol_upper in _PIP_SIZES:
            return _PIP_SIZES[symbol_upper]
        if 'JPY' in symbol_upper:
            return _PIP_SIZES['JPY']
        if 'XAU' in symbol_upper or 'GOLD' in symbol_upper:
            return _PIP_SIZES['XAUUSD']
        if 'BTC' in symbol_upper:
            return _PIP_SIZES['BTCUSD']
        if 'ETH' in symbol_upper:
            return _PIP_SIZES['ETHUSD']
        return _PIP_SIZES['default']
