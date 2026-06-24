import os
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

class Settings(BaseSettings):
    # Project Settings
    PROJECT_NAME: str = "AI Trading Decision Support System"
    VERSION: str = "1.0.0"
    ENVIRONMENT: str = "development"  # development, staging, production
    
    # Database Settings
    DB_USER: str = Field(default="postgres")
    DB_PASSWORD: str = Field(default="postgres")
    DB_HOST: str = Field(default="localhost")
    DB_PORT: int = Field(default=5432)
    DB_NAME: str = Field(default="trading_system")
    
    @property
    def DATABASE_URL(self) -> str:
        return f"postgresql://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

    # Redis Settings
    REDIS_HOST: str = Field(default="localhost")
    REDIS_PORT: int = Field(default=6379)
    REDIS_DB: int = Field(default=0)

    # MT5 Settings
    MT5_LOGIN: int = Field(default=0)
    MT5_PASSWORD: str = Field(default="")
    MT5_SERVER: str = Field(default="")
    MT5_PATH: str = Field(default="C:/Program Files/MetaTrader 5/terminal64.exe")
    
    # Trading Settings
    MONITORED_SYMBOLS: List[str] = Field(default=["EURUSD", "GBPUSD", "USDJPY", "XAUUSD"])
    DEFAULT_TIMEFRAME: str = Field(default="H1")
    
    # API Settings
    API_HOST: str = Field(default="0.0.0.0")
    API_PORT: int = Field(default=8000)

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()
