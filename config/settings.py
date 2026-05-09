from pydantic_settings import BaseSettings
from typing import List

class Settings(BaseSettings):
    PROJECT_NAME: str = "Nexus Singularity Engine"
    VERSION: str = "10.0.0"
    ENVIRONMENT: str = "development"
    
    # Parâmetros Institucionais e Apex
    MAX_DRAWDOWN_PERCENT: float = 2.0
    RISK_REWARD_RATIO: float = 1.5
    MAX_DAILY_TRADES: int = 5
    
    # Configuração de Agentes
    ORACLE_CONFIDENCE_THRESHOLD: float = 0.85
    GUARDIAN_STRICT_MODE: bool = True
    
    # Persistência
    SQLITE_DB_PATH: str = "sqlite:///telemetry.db"
    CHROMA_DB_PATH: str = "./chroma_data"
    
    class Config:
        env_file = ".env"
        env_file_encoding = 'utf-8'
        extra = 'ignore'

settings = Settings()
