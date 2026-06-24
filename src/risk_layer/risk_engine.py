import os
import yaml
import logging
from typing import Dict, Any
from database.schemas import TechnicalFeature

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Default config used when risk_config.yaml is not found
DEFAULT_CONFIG = {
    'atr_multiplier_sl':  1.5,
    'atr_multiplier_tp1': 2.0,
    'atr_multiplier_tp2': 3.5,
    'pip_sizes': {'default': 0.0001},
}


class RiskEngine:
    """
    Calculates Entry, Stop Loss, and Take Profit levels using ATR.
    """

    def __init__(self, config_path: str = 'config/risk_config.yaml'):
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                self.config = yaml.safe_load(f)
            logger.info('RiskEngine: loaded config from %s', config_path)
        else:
            self.config = DEFAULT_CONFIG
            logger.warning('RiskEngine: config file not found, using defaults')

    def _pip_size(self, symbol: str) -> float:
        pip_sizes = self.config.get('pip_sizes', {})
        return pip_sizes.get(symbol, pip_sizes.get('default', 0.0001))

    def calculate_levels(
        self,
        symbol: str,
        direction: str,
        current_price: float,
        features: TechnicalFeature,
    ) -> Dict[str, Any]:
        """
        Returns entry, SL, TP1, TP2, R:R, and risk in pips.
        """
        # FIX: explicit float cast — atr_14 may be Decimal from DB
        atr = float(features.atr_14) if features.atr_14 else self._pip_size(symbol) * 10

        sl_mult  = self.config.get('atr_multiplier_sl',  1.5)
        tp1_mult = self.config.get('atr_multiplier_tp1', 2.0)
        tp2_mult = self.config.get('atr_multiplier_tp2', 3.5)

        if direction == 'BUY':
            sl  = current_price - (atr * sl_mult)
            tp1 = current_price + (atr * tp1_mult)
            tp2 = current_price + (atr * tp2_mult)
        else:  # SELL
            sl  = current_price + (atr * sl_mult)
            tp1 = current_price - (atr * tp1_mult)
            tp2 = current_price - (atr * tp2_mult)

        risk   = abs(current_price - sl)
        reward = abs(tp1 - current_price)

        # Guard: avoid division by zero
        rr_ratio   = round(reward / risk, 2) if risk > 0 else 0.0
        pip_size   = self._pip_size(symbol)
        risk_pips  = round(risk / pip_size, 1) if pip_size > 0 else 0.0

        return {
            'entry':        round(current_price, 5),
            'stop_loss':    round(sl,  5),
            'take_profit_1': round(tp1, 5),
            'take_profit_2': round(tp2, 5),
            'risk_reward':  rr_ratio,
            'risk_pips':    risk_pips,
            'atr_used':     round(atr, 5),
        }
