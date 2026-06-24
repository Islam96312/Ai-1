import numpy as np
import pickle
import os
import logging
from typing import Dict, Any, Tuple

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

MODEL_DIR = 'src/ai_layer/models'


class MLModelService:
    """
    Handles predictions using per-symbol Ensemble Models.
    """
    def __init__(self):
        self._models:  Dict[str, Any] = {}
        self._scalers: Dict[str, Any] = {}

    def _load(self, symbol: str, timeframe: str):
        key = f'{symbol}_{timeframe}'
        if key in self._models:
            return
        model_path  = os.path.join(MODEL_DIR, f'ensemble_{key}.pkl')
        scaler_path = os.path.join(MODEL_DIR, f'scaler_{key}.pkl')
        if os.path.exists(model_path):
            try:
                with open(model_path, 'rb')  as f: self._models[key]  = pickle.load(f)
                if os.path.exists(scaler_path):
                    with open(scaler_path, 'rb') as f: self._scalers[key] = pickle.load(f)
                logger.info(f'Model loaded for {key}')
            except Exception as e:
                logger.error(f'Error loading model {key}: {e}')

    def predict(self, symbol: str, timeframe: str, features_vector: np.ndarray) -> Tuple[str, float]:
        self._load(symbol, timeframe)
        key    = f'{symbol}_{timeframe}'
        model  = self._models.get(key)
        scaler = self._scalers.get(key)
        if model is None:
            return 'HOLD', 0.5
        try:
            if features_vector.ndim == 1:
                features_vector = features_vector.reshape(1, -1)
            if scaler:
                features_vector = scaler.transform(features_vector)
            probs      = model.predict_proba(features_vector)[0]
            prediction = int(np.argmax(probs))
            mapping    = {0: 'SELL', 1: 'HOLD', 2: 'BUY'}
            return mapping[prediction], float(probs[prediction])
        except Exception as e:
            logger.error(f'Prediction error {key}: {e}')
            return 'HOLD', 0.0

    def get_feature_importance(self, symbol: str, timeframe: str) -> Dict[str, float]:
        self._load(symbol, timeframe)
        key   = f'{symbol}_{timeframe}'
        model = self._models.get(key)
        if model is None: return {}
        try:
            importances = model.named_estimators_['rf'].feature_importances_
            names = ['ema_diff_20_50','ema_diff_50_200','rsi','macd_hist','adx','volatility','momentum']
            return dict(zip(names, importances.tolist()))
        except Exception as e:
            logger.error(f'Feature importance error {key}: {e}')
            return {}
