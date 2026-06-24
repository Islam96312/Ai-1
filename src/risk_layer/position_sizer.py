import yaml
import logging
from typing import Dict, Any
import numpy as np

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class PositionSizer:
    """
    Advanced Position Sizing using Kelly Criterion and Equity Curve Protection.
    """
    def __init__(self, config_path: str = "config/risk_config.yaml"):
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)

    def calculate_lot_size(self, balance: float, sl_pips: float, symbol: str, 
                          win_rate: float = 0.5, avg_win_pips: float = 20.0, 
                          avg_loss_pips: float = 15.0, current_drawdown: float = 0.0) -> float:
        """
        Calculates lot size based on Kelly Criterion and equity health.
        """
        # 1. Base Risk Percentage
        risk_pct = self.config['max_risk_per_trade']
        
        # 2. Kelly Criterion Adjustment
        if self.config.get('use_kelly_criterion', False):
            # Kelly Formula: f* = (p*b - q) / b
            # p = win rate, q = loss rate, b = avg win / avg loss
            p = win_rate
            q = 1 - win_rate
            b = avg_win_pips / avg_loss_pips if avg_loss_pips != 0 else 1.0
            
            kelly_f = (p * b - q) / b if b != 0 else 0.0
            # Use a fractional Kelly to be conservative
            fractional_kelly = kelly_f * self.config.get('kelly_fraction', 0.2)
            
            # Constrain Kelly between 0.1% and 2% to avoid extreme bets
            risk_pct = max(0.001, min(0.02, fractional_kelly))
            logger.info(f"Kelly Adjusted Risk: {risk_pct*100:.2f}%")

        # 3. Equity Curve Protection
        if self.config.get('equity_curve_protection', False):
            if current_drawdown >= self.config.get('drawdown_threshold', 0.05):
                risk_pct *= self.config.get('risk_reduction_factor', 0.25)
                logger.warning(f"Equity Protection Active: Risk reduced to {risk_pct*100:.2f}%")

        # 4. Convert Risk % to Lot Size
        # Standard: 1 pip = $10 for 1.0 lot on EURUSD
        pip_value_standard = 10.0
        risk_amount = balance * risk_pct
        
        if sl_pips <= 0:
            return 0.0
            
        lot_size = risk_amount / (sl_pips * pip_value_standard)
        return round(lot_size, 2)
