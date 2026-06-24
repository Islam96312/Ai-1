import yaml
import logging
from typing import Dict, Any, Tuple, List
from src.data_layer.symbol_mapper import SymbolMapper

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class RiskFilters:
    """
    Professional risk filters including Correlation and Currency Exposure limits.
    """
    def __init__(self, config_path: str = "config/risk_config.yaml"):
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)

    def validate_trade(self, signal: Dict[str, Any], sentiment: Any, 
                       open_trades: List[Dict[str, Any]], current_balance: float) -> Tuple[bool, str]:
        """
        Validates trade against advanced quant limits.
        """
        # 1. Standard Confidence & RR Checks
        if signal['confidence'] < self.config['min_confidence_to_execute']:
            return False, f"Confidence too low ({signal['confidence']:.2f})"
        
        if signal['risk_reward'] < self.config['min_risk_reward']:
            return False, f"R:R too low ({signal['risk_reward']:.2f})"

        # 2. Correlation & Currency Exposure Check
        symbol = signal['symbol']
        base, quote = SymbolMapper.get_currencies(symbol)
        
        # Calculate current exposure to base and quote currencies
        # Exposure = Sum of risk in dollars for all trades involving this currency
        base_exposure = 0.0
        quote_exposure = 0.0
        
        for trade in open_trades:
            t_base, t_quote = SymbolMapper.get_currencies(trade['symbol'])
            trade_risk = trade['lot'] * trade['sl_pips'] * 10.0 # Simplified
            
            if t_base == base: base_exposure += trade_risk
            if t_quote == base: base_exposure -= trade_risk # Opposite direction
            
            if t_base == quote: quote_exposure += trade_risk
            if t_quote == quote: quote_exposure -= trade_risk

        # Check if new trade exceeds max currency exposure
        new_trade_risk = signal['lot'] * signal['risk_pips'] * 10.0
        total_base_exp = abs(base_exposure + new_trade_risk) / current_balance
        
        if total_base_exp > self.config.get('max_currency_exposure', 0.03):
            return False, f"Excessive exposure to {base} ({total_base_exp*100:.2f}%)"

        # 3. Open Trades Limit
        if len(open_trades) >= self.config['max_open_trades']:
            return False, "Max open trades reached"

        return True, "Approved"
