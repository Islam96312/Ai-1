import pandas as pd
import numpy as np
from typing import List, Dict, Any

class BacktestReporter:
    """
    Calculates performance metrics from backtest trades.
    """
    @staticmethod
    def generate_report(trades: List[Dict[str, Any]], initial_balance: float) -> Dict[str, Any]:
        if not trades:
            return {"error": "No trades executed during backtest"}
        
        df = pd.DataFrame(trades)
        final_balance = initial_balance + df['profit'].sum()
        
        win_rate = (len(df[df['profit'] > 0]) / len(df)) * 100
        total_profit = df['profit'].sum()
        
        # Profit Factor = Sum(Gains) / Sum(Losses)
        gains = df[df['profit'] > 0]['profit'].sum()
        losses = abs(df[df['profit'] < 0]['profit'].sum())
        profit_factor = gains / losses if losses != 0 else gains
        
        # Max Drawdown (Simplified)
        equity_curve = initial_balance + df['profit'].cumsum()
        peak = equity_curve.cummax()
        drawdown = (peak - equity_curve) / peak
        max_dd = drawdown.max() * 100
        
        return {
            "initial_balance": initial_balance,
            "final_balance": final_balance,
            "total_profit": total_profit,
            "total_trades": len(df),
            "win_rate": f"{win_rate:.2f}%",
            "profit_factor": f"{profit_factor:.2f}",
            "max_drawdown": f"{max_dd:.2f}%",
            "sharpe_ratio": "N/A (Needs daily returns)"
        }
