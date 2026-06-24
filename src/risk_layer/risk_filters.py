"""
RiskFilters
===========
Validates a proposed trade signal against a set of configurable rules
before it is sent to the execution layer.

Filters applied in order:
  1. Minimum confidence score
  2. Minimum Risk : Reward ratio
  3. Allowed trading session hours
  4. Maximum open trades
  5. Maximum risk per trade (% of balance)
  6. High-impact news block (event_risk_score penalty)
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ── Default thresholds (overridable via config YAML) ──────────────────
_DEFAULTS = {
    'min_confidence':        65.0,   # minimum final_score to consider trading
    'min_rr':                1.2,    # minimum risk:reward ratio
    'max_open_trades':       5,      # maximum simultaneous positions
    'max_risk_pct':          2.0,    # max % of balance at risk per trade
    'news_block_threshold': -70.0,   # block trade if event_risk_score < this
    # Session windows in UTC hours [open, close) — trades allowed inside
    'sessions': [
        {'name': 'London', 'open': 7,  'close': 16},
        {'name': 'NewYork', 'open': 13, 'close': 21},
    ],
}


class RiskFilters:
    """
    Validates a trade signal before execution.

    Usage::

        filters = RiskFilters()
        approved, reason = filters.validate_trade(
            signal_data, sentiment, open_trades, account_balance
        )
        if not approved:
            logger.info('Trade blocked: %s', reason)
    """

    def __init__(self, config_path: str = 'config/risk_config.yaml') -> None:
        # Deep copy defaults so instances are independent
        self.min_confidence       = _DEFAULTS['min_confidence']
        self.min_rr               = _DEFAULTS['min_rr']
        self.max_open_trades      = _DEFAULTS['max_open_trades']
        self.max_risk_pct         = _DEFAULTS['max_risk_pct']
        self.news_block_threshold = _DEFAULTS['news_block_threshold']
        self.sessions             = list(_DEFAULTS['sessions'])
        self._load_config(config_path)

    # ------------------------------------------------------------------ #
    #  Config loader                                                       #
    # ------------------------------------------------------------------ #
    def _load_config(self, path: str) -> None:
        if not os.path.exists(path):
            return
        try:
            import yaml
            with open(path) as f:
                cfg = yaml.safe_load(f) or {}
            rf = cfg.get('risk_filters', {})
            self.min_confidence       = float(rf.get('min_confidence',       self.min_confidence))
            self.min_rr               = float(rf.get('min_rr',               self.min_rr))
            self.max_open_trades      = int(rf.get('max_open_trades',        self.max_open_trades))
            self.max_risk_pct         = float(rf.get('max_risk_pct',         self.max_risk_pct))
            self.news_block_threshold = float(rf.get('news_block_threshold', self.news_block_threshold))
            if 'sessions' in rf:
                self.sessions = rf['sessions']
            logger.info('RiskFilters: loaded config from %s', path)
        except Exception as exc:
            logger.warning('RiskFilters: could not load config (%s). Using defaults.', exc)

    # ------------------------------------------------------------------ #
    #  Public API                                                          #
    # ------------------------------------------------------------------ #
    def validate_trade(
        self,
        signal: Dict[str, Any],
        sentiment: Any,
        open_trades: Optional[List[Dict]] = None,
        account_balance: float = 10_000.0,
    ) -> Tuple[bool, str]:
        """
        Run all filters sequentially.  Returns (approved, reason).

        Parameters
        ----------
        signal          : dict with keys: final_score, risk_reward, lot, risk_pips, symbol
        sentiment       : SentimentScore ORM object (must have .event_risk_score)
        open_trades     : list of open position dicts (or None -> treated as [])
        account_balance : current account equity in account currency
        """
        if open_trades is None:
            open_trades = []

        # ── Filter 1: Confidence ──────────────────────────────────────
        score = float(signal.get('final_score', 0))
        if score < self.min_confidence:
            return False, f'Confidence {score:.1f} < {self.min_confidence} (min)'

        # ── Filter 2: Risk : Reward ───────────────────────────────────
        rr = float(signal.get('risk_reward', 0))
        if rr < self.min_rr:
            return False, f'R:R {rr:.2f} < {self.min_rr} (min)'

        # ── Filter 3: Trading session ─────────────────────────────────
        now_hour = datetime.now(tz=timezone.utc).hour
        in_session = any(
            s['open'] <= now_hour < s['close'] for s in self.sessions
        )
        if not in_session:
            session_str = ', '.join(
                f"{s['name']} {s['open']:02d}-{s['close']:02d} UTC"
                for s in self.sessions
            )
            return False, f'Outside allowed trading hours ({session_str})'

        # ── Filter 4: Max open trades ─────────────────────────────────
        if len(open_trades) >= self.max_open_trades:
            return False, f'Max open trades reached ({len(open_trades)}/{self.max_open_trades})'

        # ── Filter 5: Max risk per trade ──────────────────────────────
        risk_pips = float(signal.get('risk_pips', 0))
        lot       = float(signal.get('lot', 0.01))
        symbol    = signal.get('symbol', '')
        pip_value = self._get_pip_value(symbol)
        trade_risk_usd = risk_pips * lot * pip_value * 10  # standard lot assumption
        max_risk_usd   = account_balance * (self.max_risk_pct / 100)
        if trade_risk_usd > max_risk_usd:
            return False, (
                f'Trade risk ${trade_risk_usd:.2f} exceeds max '
                f'{self.max_risk_pct}% (${max_risk_usd:.2f}) of balance'
            )

        # ── Filter 6: High-impact news ────────────────────────────────
        event_risk = float(getattr(sentiment, 'event_risk_score', 0) or 0)
        if event_risk < self.news_block_threshold:
            return False, (
                f'High-impact news block: event_risk_score={event_risk:.0f} '
                f'< threshold {self.news_block_threshold:.0f}'
            )

        return True, 'Approved'

    # ------------------------------------------------------------------ #
    #  Helpers                                                             #
    # ------------------------------------------------------------------ #
    def _get_currencies(self, symbol: str) -> Tuple[str, str]:
        """Split a 6-char FX symbol into (base, quote). e.g. 'EURUSD' -> ('EUR','USD')."""
        s = symbol.upper().replace('/', '')
        if len(s) == 6:
            return s[:3], s[3:]
        # Fallback for non-standard lengths
        return s[:3], s[3:] if len(s) > 3 else ''

    def _get_pip_value(self, symbol: str) -> float:
        """Approximate pip value in USD for common symbols (for risk % calc)."""
        s = symbol.upper()
        if 'JPY' in s:
            return 0.91    # ~$0.91 per pip per 0.01 lot
        if 'XAU' in s or 'GOLD' in s:
            return 1.0
        if 'GBP' in s:
            return 1.27
        if 'EUR' in s:
            return 1.08
        if 'AUD' in s or 'NZD' in s:
            return 0.65
        return 1.0         # USD pairs
