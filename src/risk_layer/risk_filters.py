import os
import yaml
import logging
from typing import Dict, Any, Tuple, List
from datetime import datetime, timezone

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DEFAULT_CONFIG = {
    'min_confidence_to_execute': 65.0,
    'min_risk_reward':           1.2,
    'max_open_trades':           5,
    'max_currency_exposure':     0.03,
    'max_spread_pips':           3.0,
    'allowed_trading_hours':     {'start': 7, 'end': 20},
}


class RiskFilters:
    """
    Professional risk filters: confidence, R:R, session, spread,
    open trade limit, and currency exposure.
    """

    def __init__(self, config_path: str = 'config/risk_config.yaml'):
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                self.config = yaml.safe_load(f)
            logger.info('RiskFilters: loaded config from %s', config_path)
        else:
            self.config = DEFAULT_CONFIG
            logger.warning('RiskFilters: config file not found, using defaults')

    @staticmethod
    def _get_currencies(symbol: str):
        """Extract base and quote currency from a symbol string."""
        # Standard 6-char forex pairs
        if len(symbol) == 6 and symbol.isalpha():
            return symbol[:3].upper(), symbol[3:].upper()
        # Metals: XAUUSD, XAGUSD
        if symbol.upper().startswith(('XAU', 'XAG')):
            return symbol[:3].upper(), symbol[3:6].upper()
        return symbol[:3].upper(), symbol[3:6].upper()

    def validate_trade(
        self,
        signal: Dict[str, Any],
        sentiment: Any,
        open_trades: List[Dict[str, Any]] = None,   # FIX: default to empty list
        current_balance: float = 10_000.0,
    ) -> Tuple[bool, str]:
        """
        Validates a signal against all risk rules.
        Returns (approved: bool, reason: str).
        """
        if open_trades is None:
            open_trades = []

        symbol = signal.get('symbol', '')

        # 1. Confidence threshold
        confidence = signal.get('final_score', signal.get('confidence', 0))
        min_conf   = self.config.get('min_confidence_to_execute', 65.0)
        if confidence < min_conf:
            return False, f'Confidence too low ({confidence:.1f} < {min_conf})'

        # 2. Risk:Reward ratio
        rr       = signal.get('risk_reward', 0)
        min_rr   = self.config.get('min_risk_reward', 1.2)
        if rr < min_rr:
            return False, f'R:R too low ({rr:.2f} < {min_rr})'

        # 3. Trading session filter (UTC)
        now_utc   = datetime.now(timezone.utc)
        hours_cfg = self.config.get('allowed_trading_hours', {})
        h_start   = hours_cfg.get('start', 0)
        h_end     = hours_cfg.get('end', 24)
        if not (h_start <= now_utc.hour < h_end):
            return False, f'Outside trading hours (UTC {now_utc.hour:02d}:xx — allowed {h_start}–{h_end})'

        # 4. Open trades limit
        max_trades = self.config.get('max_open_trades', 5)
        if len(open_trades) >= max_trades:
            return False, f'Max open trades reached ({len(open_trades)}/{max_trades})'

        # 5. Currency exposure check
        if symbol and current_balance > 0:
            base, quote = self._get_currencies(symbol)
            base_exp = 0.0
            for trade in open_trades:
                t_sym             = trade.get('symbol', '')
                t_base, t_quote   = self._get_currencies(t_sym)
                trade_risk_usd    = trade.get('lot', 0) * trade.get('risk_pips', 0) * 10.0
                if t_base  == base:  base_exp += trade_risk_usd
                if t_quote == base:  base_exp -= trade_risk_usd  # hedged

            new_risk      = signal.get('lot', 0.01) * signal.get('risk_pips', 0) * 10.0
            total_exp_pct = abs(base_exp + new_risk) / current_balance
            max_exp       = self.config.get('max_currency_exposure', 0.03)
            if total_exp_pct > max_exp:
                return False, f'Excessive {base} exposure ({total_exp_pct*100:.1f}% > {max_exp*100:.0f}%)'

        return True, 'Approved'
