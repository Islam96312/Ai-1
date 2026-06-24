import pandas as pd
import numpy as np
import logging
from typing import List, Dict, Any
from src.ai_layer.signal_aggregator import SignalAggregator
from src.risk_layer.risk_engine import RiskEngine
from src.risk_layer.risk_filters import RiskFilters

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class BacktestEngine:
    """
    Advanced Backtest Engine with Walk-Forward Validation.
    """
    def __init__(self, initial_balance: float = 10000.0):
        self.balance = initial_balance
        self.equity = initial_balance
        self.trades = []
        self.aggregator = SignalAggregator()
        self.risk_engine = RiskEngine()
        self.filters = RiskFilters()

    def run_walk_forward(self, symbol: str, timeframe: str, bars_df: pd.DataFrame, train_window=100, test_window=20):
        """
        Implements Walk-Forward Analysis.
        1. Train on 'train_window' bars.
        2. Test on next 'test_window' bars.
        3. Shift window and repeat.
        """
        logger.info(f"Starting Walk-Forward Backtest for {symbol}...")
        
        active_trade = None
        current_idx = train_window
        
        while current_idx + test_window < len(bars_df):
            # 1. Simulated Training Phase
            # In a real system, we would call ModelTrainer.train_ensemble() here 
            # using bars_df.iloc[current_idx - train_window : current_idx]
            
            # 2. Testing Phase
            for i in range(current_idx, current_idx + test_window):
                current_bar = bars_df.iloc[i]
                current_price = current_bar['close']
                
                # Manage active trade
                if active_trade:
                    if active_trade['direction'] == "BUY":
                        if current_bar['low'] <= active_trade['sl']:
                            self._close_trade(active_trade, active_trade['sl'], "SL")
                            active_trade = None
                        elif current_bar['high'] >= active_trade['tp1']:
                            self._close_trade(active_trade, active_trade['tp1'], "TP")
                            active_trade = None
                    else: # SELL
                        if current_bar['high'] >= active_trade['sl']:
                            self._close_trade(active_trade, active_trade['sl'], "SL")
                            active_trade = None
                        elif current_bar['low'] <= active_trade['tp1']:
                            self._close_trade(active_trade, active_trade['tp1'], "TP")
                            active_trade = None
                    continue

                # Signal Generation
                from database.schemas import TechnicalFeature, SentimentScore
                mock_features = TechnicalFeature(
                    ema_20=current_bar.get('ema_20'),
                    ema_50=current_bar.get('ema_50'),
                    ema_200=current_bar.get('ema_200'),
                    rsi_14=current_bar.get('rsi_14'),
                    atr_14=current_bar.get('atr_14'),
                    adx_14=current_bar.get('adx_14'),
                    regime=current_bar.get('regime', 'NEUTRAL')
                )
                mock_sentiment = SentimentScore(combined_sentiment=0.0, event_risk_score=0.0)
                
                res = self.aggregator.aggregate(mock_features, mock_sentiment)
                
                if res['decision'] == "EXECUTE":
                    levels = self.risk_engine.calculate_levels(symbol, res['direction'], current_price, mock_features)
                    signal_data = {**res, **levels}
                    approved, _ = self.filters.validate_trade(signal_data, mock_sentiment, 0)
                    
                    if approved:
                        active_trade = {
                            "symbol": symbol,
                            "direction": res['direction'],
                            "entry": current_price,
                            "sl": levels['stop_loss'],
                            "tp1": levels['take_profit_1'],
                            "time": current_bar['open_time']
                        }
            
            # Shift window
            current_idx += test_window

        return self.trades

    def _close_trade(self, trade, close_price, reason):
        pips = (close_price - trade['entry']) * 10000 if trade['direction'] == "BUY" else (trade['entry'] - close_price) * 10000
        profit = pips * 1.0 
        self.balance += profit
        self.trades.append({**trade, "close_price": close_price, "profit": profit, "reason": reason})
