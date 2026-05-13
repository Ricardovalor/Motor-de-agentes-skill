from pydantic_settings import BaseSettings
from typing import List, Dict, Any
import json
import os

def _load_rules() -> dict:
    """Carrega rules.json como fonte única de verdade para parâmetros Apex."""
    rules_paths = [
        os.path.join(os.path.dirname(__file__), "..", "rules.json"),
        "rules.json",
    ]
    for path in rules_paths:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
    return {}

class Settings(BaseSettings):
    PROJECT_NAME: str = "Nexus Singularity Engine"
    VERSION: str = "16.2.0"  # TITAN Hardened — synced with rules.json
    ENVIRONMENT: str = "development"
    
    # Parâmetros Institucionais Apex (V16.2 — Alinhados com rules.json)
    MAX_DRAWDOWN_PERCENT: float = 4.0       # $2,000 em conta de $50K = 4%
    RISK_REWARD_RATIO: float = 2.0          # TP1 MNQ = 2.0x ATR (rules.json)
    MAX_DAILY_TRADES: int = 3               # Apex 50K hard limit (rules.json)
    DAILY_LOSS_LIMIT: float = 1000.0        # $1,000 DLL Apex (rules.json)
    ACCOUNT_BALANCE: float = 50000.0        # Apex 50K evaluation
    
    # Configuração de Agentes (V16.2: aligned with Committee 60% threshold)
    ORACLE_CONFIDENCE_THRESHOLD: float = 0.65  # Alinhado com Committee gate (60%+)
    GUARDIAN_STRICT_MODE: bool = True
    
    # Persistência
    SQLITE_DB_PATH: str = "sqlite:///memory_data/telemetry.db"  # TITAN-013 FIX: Unificado com StateMemory path
    CHROMA_DB_PATH: str = "./memory_data/chroma_data"  # GAP-M05 FIX: Unificado com VectorMemory default
    
    # GAP-F09 FIX: Declaração explícita para o Pydantic V2 aceitar a injeção
    RULES: Dict[str, Any] = {}
    
    class Config:
        env_file = ".env"
        env_file_encoding = 'utf-8'
        extra = 'ignore'

settings = Settings()

# BUG-C04 FIX: Carrega rules.json como dict acessível via settings.RULES
# Usado por: committee_agent (SL/TP), guardian_agent (DLL), compliance_skills
settings.RULES = _load_rules()
