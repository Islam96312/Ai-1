import yaml
import logging
from typing import Dict, Any
from database.schemas import TechnicalFeature, Signal

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class RiskEngine:
    """
    Calculates Entry, Stop Loss and Take Profit levels.
    """
    def __init__(self, config_path: str = "config/risk_config.yaml"):
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)

    def calculate_levels(self, symbol: str, direction: str, current_price: float, features: TechnicalFeature) -> Dict[str, Any]:
        """
        Determines SL and TP based on ATR and config.
        """
        atr = features.atr_14 if features.atr_14 else 0.001 # Fallback
        
        if direction == "BUY":
            sl = current_price - (atr * self.config['atr_multiplier_sl'])
            tp1 = current_price + (atr * self.config['atr_multiplier_tp1'])
            tp2 = current_price + (atr * self.config['atr_multiplier_tp2'])
        else: # SELL
            sl = current_price + (atr * self.config['atr_multiplier_sl'])
            tp1 = current_price - (atr * self.config['atr_multiplier_tp1'])
            tp2 = current_price - (atr * self.config['atr_multiplier_tp2'])

        # Calculate Risk:Reward Ratio
        risk = abs(current_price - sl)
        reward = abs(tp1 - current_price)
        rr_ratio = reward / risk if risk != 0 else 0

        return {
            "entry": current_price,
            "stop_loss": sl,
            "take_profit_1": tp1,
            "take_profit_2": tp2,
            "risk_reward": rr_ratio,
            "risk_pips": risk * 10000 # Simplified pips for 4-digit pairs
        }
