import pandas as pd
import numpy as np
import xgboost as xgb
import pickle
import os
import logging
from sklearn.ensemble import RandomForestClassifier, VotingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sqlalchemy.orm import Session
from database.schemas import TechnicalFeature, MarketBar

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

MODEL_DIR = 'src/ai_layer/models'
os.makedirs(MODEL_DIR, exist_ok=True)


class ModelTrainer:
    """
    Trains an Ensemble Model (XGBoost + Random Forest + Logistic Regression).
    """
    def __init__(self, db_session: Session):
        self.db = db_session

    def prepare_dataset(self, symbol: str, timeframe: str):
        """
        FIX: Labels are derived from real forward price movement,
        not random values.
        """
        features_list = self.db.query(TechnicalFeature).filter(
            TechnicalFeature.symbol == symbol,
            TechnicalFeature.timeframe == timeframe
        ).order_by(TechnicalFeature.bar_time).all()

        if len(features_list) < 100:
            logger.warning(f'Not enough data for {symbol}. Need 100+, got {len(features_list)}.')
            return None, None

        bars = self.db.query(MarketBar).filter(
            MarketBar.symbol == symbol,
            MarketBar.timeframe == timeframe
        ).order_by(MarketBar.open_time).all()

        bar_map = {b.open_time: float(b.close) for b in bars}

        data = []
        FORWARD_BARS   = 3
        THRESHOLD_PIPS = 0.0010

        for i, f in enumerate(features_list[:-FORWARD_BARS]):
            future_f = features_list[i + FORWARD_BARS]
            current_close = bar_map.get(f.bar_time)
            future_close  = bar_map.get(future_f.bar_time)
            if current_close is None or future_close is None:
                continue
            price_change = future_close - current_close
            label = 2 if price_change > THRESHOLD_PIPS else (0 if price_change < -THRESHOLD_PIPS else 1)
            data.append({
                'ema_diff_20_50':  (float(f.ema_20)  - float(f.ema_50))  if f.ema_20  and f.ema_50  else 0,
                'ema_diff_50_200': (float(f.ema_50)  - float(f.ema_200)) if f.ema_50  and f.ema_200 else 0,
                'rsi':             float(f.rsi_14)         if f.rsi_14         else 50,
                'macd_hist':       float(f.macd_histogram) if f.macd_histogram else 0,
                'adx':             float(f.adx_14)         if f.adx_14         else 0,
                'volatility':      float(f.volatility_score) if f.volatility_score else 0,
                'momentum':        float(f.momentum_score)   if f.momentum_score   else 0,
                'target': label
            })

        if not data:
            return None, None

        df = pd.DataFrame(data).dropna()
        logger.info(f'Dataset: {len(df)} samples | BUY={sum(df.target==2)}, HOLD={sum(df.target==1)}, SELL={sum(df.target==0)}')
        return df.drop('target', axis=1), df['target']

    def train_ensemble(self, symbol: str, timeframe: str) -> bool:
        X, y = self.prepare_dataset(symbol, timeframe)
        if X is None:
            return False

        scaler  = StandardScaler()
        X_scaled = scaler.fit_transform(X)

        clf1 = xgb.XGBClassifier(n_estimators=100, max_depth=5, learning_rate=0.1,
                                   use_label_encoder=False, eval_metric='mlogloss')
        clf2 = RandomForestClassifier(n_estimators=100, max_depth=5, random_state=42)
        clf3 = LogisticRegression(max_iter=1000, random_state=42)

        ensemble = VotingClassifier(
            estimators=[('xgb', clf1), ('rf', clf2), ('lr', clf3)],
            voting='soft'
        )

        X_train, X_test, y_train, y_test = train_test_split(
            X_scaled, y, test_size=0.2, random_state=42, stratify=y
        )
        ensemble.fit(X_train, y_train)
        accuracy = ensemble.score(X_test, y_test)
        logger.info(f'Ensemble trained for {symbol}. Accuracy: {accuracy:.4f}')

        key = f'{symbol}_{timeframe}'
        with open(os.path.join(MODEL_DIR, f'ensemble_{key}.pkl'), 'wb') as f:
            pickle.dump(ensemble, f)
        with open(os.path.join(MODEL_DIR, f'scaler_{key}.pkl'), 'wb') as f:
            pickle.dump(scaler, f)

        logger.info(f'Model saved: ensemble_{key}.pkl')
        return True
