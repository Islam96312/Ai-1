import numpy as np
import pickle
import os
import logging
from typing import Dict, Any, Tuple

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MLModelService:
    """
    Handles predictions and interpretability using the Ensemble Model.
    """
    def __init__(self, model_path: str = "src/ai_layer/models/ensemble_model.pkl"):
        self.model_path = model_path
        self.model = self._load_model()

    def _load_model(self):
        if os.path.exists(self.model_path):
            try:
                with open(self.model_path, 'rb') as f:
                    return pickle.load(f)
            except Exception as e:
                logger.error(f"Error loading model: {e}")
                return None
        return None

    def predict(self, features_vector: np.ndarray) -> Tuple[str, float]:
        """
        Predicts direction and confidence using the ensemble.
        """
        if self.model is None:
            return "HOLD", 0.5

        try:
            # features_vector should be 2D: (1, n_features)
            if features_vector.ndim == 1:
                features_vector = features_vector.reshape(1, -1)
                
            probs = self.model.predict_proba(features_vector)[0]
            prediction = np.argmax(probs)
            confidence = probs[prediction]
            
            mapping = {0: "SELL", 1: "HOLD", 2: "BUY"}
            return mapping[prediction], confidence
        except Exception as e:
            logger.error(f"Prediction error: {e}")
            return "HOLD", 0.0

    def get_feature_importance(self) -> Dict[str, float]:
        """
        Extracts importance from the Random Forest component of the ensemble.
        """
        if self.model is None: return {}
        
        # Access the Random Forest model inside the VotingClassifier
        rf_model = self.model.named_estimators_['rf']
        importances = rf_model.feature_importances_
        
        # Feature names used in ModelTrainer
        names = ['ema_diff_20_50', 'ema_diff_50_200', 'rsi', 'macd_hist', 'adx', 'volatility', 'momentum']
        return dict(zip(names, importances))
