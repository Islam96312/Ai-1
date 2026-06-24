import pandas as pd
import numpy as np
import xgboost as xgb
import pickle
import os
import logging
from sklearn.ensemble import RandomForestClassifier, VotingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sqlalchemy.orm import Session
from database.schemas import TechnicalFeature

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ModelTrainer:
    """
    Trains an Ensemble Model (XGBoost + Random Forest + Logistic Regression).
    """
    def __init__(self, db_session: Session):
        self.db = db_session

    def prepare_dataset(self, symbol: str, timeframe: str):
        """
        Creates a dataset for training with advanced feature scaling.
        """
        features_list = self.db.query(TechnicalFeature).filter(
            TechnicalFeature.symbol == symbol, 
            TechnicalFeature.timeframe == timeframe
        ).order_by(TechnicalFeature.bar_time).all()
        
        if len(features_list) < 100:
            logger.warning(f"Not enough data to train for {symbol}")
            return None, None

        # Advanced Feature Engineering for the ML model
        data = []
        for f in features_list:
            data.append({
                'ema_diff_20_50': (f.ema_20 - f.ema_50) if f.ema_20 and f.ema_50 else 0,
                'ema_diff_50_200': (f.ema_50 - f.ema_200) if f.ema_50 and f.ema_200 else 0,
                'rsi': f.rsi_14,
                'macd_hist': f.macd_histogram,
                'adx': f.adx_14,
                'volatility': f.volatility_score,
                'momentum': f.momentum_score
            })
        
        df = pd.DataFrame(data)
        
        # Simulate a target label based on price movement (Simplified for MVP)
        # In real production, we'd join with MarketBar to find if price went up/down
        df['target'] = np.random.choice([0, 1, 2], size=len(df)) # 0:Sell, 1:Hold, 2:Buy
        
        X = df.drop('target', axis=1)
        y = df['target']
        
        return X, y

    def train_ensemble(self, symbol: str, timeframe: str):
        """
        Trains an Ensemble of 3 models using a Voting Classifier.
        """
        X, y = self.prepare_dataset(symbol, timeframe)
        if X is None: return False
        
        # Model 1: XGBoost (Good for non-linear patterns)
        clf1 = xgb.XGBClassifier(n_estimators=100, max_depth=5, learning_rate=0.1)
        
        # Model 2: Random Forest (Good for stability/reducing variance)
        clf2 = RandomForestClassifier(n_estimators=100, max_depth=5)
        
        # Model 3: Logistic Regression (Good for linear baseline)
        clf3 = LogisticRegression(max_iter=1000)
        
        # Ensemble: Soft Voting (Average of probabilities)
        ensemble = VotingClassifier(
            estimators=[('xgb', clf1), ('rf', clf2), ('lr', clf3)],
            voting='soft'
        )
        
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
        ensemble.fit(X_train, y_train)
        
        # Save the ensemble model
        os.makedirs("src/ai_layer/models", exist_ok=True)
        with open("src/ai_layer/models/ensemble_model.pkl", 'wb') as f:
            pickle.dump(ensemble, f)
        
        logger.info(f"Ensemble model trained and saved for {symbol}. Accuracy: {ensemble.score(X_test, y_test):.2f}")
        return True
