from sqlalchemy import Column, Integer, String, Float, DateTime, BigInteger, Boolean, ForeignKey, ARRAY, Numeric, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, relationship
from sqlalchemy.sql import func
from datetime import datetime

class Base(DeclarativeBase):
    pass

class MarketBar(Base):
    __tablename__ = "market_bars"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    symbol = Column(String(20), nullable=False)
    timeframe = Column(String(10), nullable=False)
    open_time = Column(DateTime, nullable=False)
    open = Column(Numeric(18, 6))
    high = Column(Numeric(18, 6))
    low = Column(Numeric(18, 6))
    close = Column(Numeric(18, 6))
    volume = Column(BigInteger)
    spread = Column(Integer)
    created_at = Column(DateTime, server_default=func.now())
    
    __table_args__ = (UniqueConstraint('symbol', 'timeframe', 'open_time'),)

class TechnicalFeature(Base):
    __tablename__ = "technical_features"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    symbol = Column(String(20), nullable=False)
    timeframe = Column(String(10), nullable=False)
    bar_time = Column(DateTime, nullable=False)
    ema_20 = Column(Numeric(18, 6))
    ema_50 = Column(Numeric(18, 6))
    ema_200 = Column(Numeric(18, 6))
    rsi_14 = Column(Numeric(8, 4))
    macd_line = Column(Numeric(18, 6))
    macd_signal = Column(Numeric(18, 6))
    macd_histogram = Column(Numeric(18, 6))
    atr_14 = Column(Numeric(18, 6))
    adx_14 = Column(Numeric(8, 4))
    trend_state = Column(String(20))
    momentum_score = Column(Numeric(5, 2))
    volatility_score = Column(Numeric(5, 2))
    regime = Column(String(20))
    created_at = Column(DateTime, server_default=func.now())

class NewsEvent(Base):
    __tablename__ = "news_events"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    event_time = Column(DateTime, nullable=False)
    currency = Column(String(10), nullable=False)
    event_title = Column(Text)
    impact_level = Column(String(10))
    actual_value = Column(String(50))
    forecast_value = Column(String(50))
    previous_value = Column(String(50))
    sentiment_raw = Column(Text)
    sentiment_score = Column(Numeric(5, 2))
    source = Column(String(50))
    fetched_at = Column(DateTime, server_default=func.now())

class SentimentScore(Base):
    __tablename__ = "sentiment_scores"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    symbol = Column(String(20), nullable=False)
    timestamp = Column(DateTime, nullable=False)
    base_currency_sentiment = Column(Numeric(5, 2))
    quote_currency_sentiment = Column(Numeric(5, 2))
    combined_sentiment = Column(Numeric(5, 2))
    event_risk_score = Column(Numeric(5, 2))
    next_high_impact_minutes = Column(Integer)
    created_at = Column(DateTime, server_default=func.now())

class Signal(Base):
    __tablename__ = "signals"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    symbol = Column(String(20), nullable=False)
    timeframe = Column(String(10), nullable=False)
    signal_time = Column(DateTime, nullable=False)
    direction = Column(String(10)) # buy, sell
    confidence = Column(Numeric(5, 2))
    technical_score = Column(Numeric(5, 2))
    higher_tf_score = Column(Numeric(5, 2))
    news_score = Column(Numeric(5, 2))
    risk_filter_score = Column(Numeric(5, 2))
    final_decision = Column(String(20)) # EXECUTE, ALERT, HOLD
    reason_codes = Column(ARRAY(String))
    explanation = Column(Text)
    model_version = Column(String(50))
    entry_price = Column(Numeric(18, 6))
    stop_loss = Column(Numeric(18, 6))
    take_profit_1 = Column(Numeric(18, 6))
    take_profit_2 = Column(Numeric(18, 6))
    lot_size = Column(Numeric(10, 4))
    status = Column(String(20), default="pending")
    created_at = Column(DateTime, server_default=func.now())

class ExecutedTrade(Base):
    __tablename__ = "executed_trades"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    signal_id = Column(BigInteger, ForeignKey("signals.id"))
    mt5_ticket = Column(BigInteger)
    symbol = Column(String(20), nullable=False)
    direction = Column(String(10))
    entry_price = Column(Numeric(18, 6))
    stop_loss = Column(Numeric(18, 6))
    take_profit = Column(Numeric(18, 6))
    lot_size = Column(Numeric(10, 4))
    open_time = Column(DateTime)
    close_time = Column(DateTime)
    close_price = Column(Numeric(18, 6))
    profit_loss = Column(Numeric(18, 2))
    profit_pips = Column(Numeric(10, 2))
    close_reason = Column(String(50))
    commission = Column(Numeric(10, 2))
    swap = Column(Numeric(10, 2))
    slippage_pips = Column(Numeric(5, 2))
    created_at = Column(DateTime, server_default=func.now())

class RiskEvent(Base):
    __tablename__ = "risk_events"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    event_type = Column(String(50))
    signal_id = Column(BigInteger)
    description = Column(Text)
    action_taken = Column(String(50))
    timestamp = Column(DateTime, server_default=func.now())

class ModelVersion(Base):
    __tablename__ = "model_versions"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    model_name = Column(String(100))
    version = Column(String(50))
    accuracy = Column(Numeric(5, 4))
    precision_score = Column(Numeric(5, 4))
    recall_score = Column(Numeric(5, 4))
    f1_score = Column(Numeric(5, 4))
    training_period = Column(String(100))
    features_used = Column(ARRAY(String))
    file_path = Column(Text)
    is_active = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now())

class BacktestResult(Base):
    __tablename__ = "backtest_results"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    model_version_id = Column(Integer, ForeignKey("model_versions.id"))
    symbol = Column(String(20))
    timeframe = Column(String(10))
    start_date = Column(DateTime)
    end_date = Column(DateTime)
    total_trades = Column(Integer)
    win_rate = Column(Numeric(5, 2))
    profit_factor = Column(Numeric(8, 2))
    max_drawdown = Column(Numeric(5, 2))
    sharpe_ratio = Column(Numeric(8, 4))
    total_return = Column(Numeric(10, 2))
    avg_risk_reward = Column(Numeric(5, 2))
    config_snapshot = Column(Text) # Simplified JSONB as Text for simplicity in this step
    created_at = Column(DateTime, server_default=func.now())
