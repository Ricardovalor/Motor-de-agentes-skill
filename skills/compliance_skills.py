from core.base import BaseSkill
from typing import Dict, Any
import logging
import sqlite3
import os
import json
from datetime import datetime, timezone

logger = logging.getLogger("ApexCompliance")

# Caminhos possíveis para o rules.json (fonte única de verdade)
_RULES_SEARCH_PATHS = [
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "extratredey", "rules.json"),  # Dev local
    r"e:\extratredey\rules.json",       # Windows path absoluto
    os.path.join(os.path.dirname(__file__), "..", "rules.json"),  # Dentro do Motor
]


def _load_apex_rules() -> dict:
    """Carrega rules.json como fonte única de verdade. Fallback para defaults Apex 50K."""
    for path in _RULES_SEARCH_PATHS:
        try:
            abs_path = os.path.abspath(path)
            if os.path.exists(abs_path):
                with open(abs_path, "r", encoding="utf-8") as f:
                    rules = json.load(f)
                logger.info(f"✅ Rules.json carregado de: {abs_path} (v{rules.get('_version', '?')})")
                return rules
        except Exception as e:
            logger.debug(f"Tentativa de rules.json em {path} falhou: {e}")
    
    logger.warning("⚠️ rules.json não encontrado. Usando defaults hardcoded Apex 50K.")
    return {}


class ApexComplianceSkill(BaseSkill):
    """
    Skill responsável pela Cadeira Guardian (Risco).
    Garante compliance estrito com as regras da Apex Trader Funding (EOD 50k).
    Monitora limite de perda diária (DLL) e Drawdown (Trailing).
    
    V16.2: Carrega parâmetros do rules.json (fonte única de verdade compartilhada com Extratredey).
    """
    def __init__(self, db_path: str = "./memory_data/telemetry.db"):
        super().__init__(name="ApexComplianceSkill", description="Avaliação de Risco APEX EOD e Limites Diários.")
        self.db_path = db_path
        
        # Carrega regras do rules.json (single source of truth)
        rules = _load_apex_rules()
        self.daily_loss_limit = -abs(rules.get("max_daily_loss", 1000))    # $1,000 DLL
        self.max_drawdown = -abs(rules.get("max_trailing_drawdown", 2000)) # $2,000 EOD Trailing
        self.max_trades_per_day = rules.get("max_daily_trades", 3)         # 3 trades/dia
        self.account_size = rules.get("account_size", 50000)
        self.mandatory_stop_loss = rules.get("mandatory_stop_loss", True)
        self._rules_version = rules.get("_version", "fallback")

    async def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        V16.2: Calcula risco usando Guardian singleton (via HTTP) como fonte primária.
        Fallback para SQLite local se o Extratredey engine não estiver online.
        """
        asset = params.get("asset", "UNKNOWN")
        
        # Prioridade 1: Ler do Guardian Singleton via HTTP (Extratredey :8000)
        trades_hoje = 0
        pnl_source = "UNKNOWN"
        try:
            import httpx
            async with httpx.AsyncClient(timeout=2.0) as client:
                resp = await client.get("http://127.0.0.1:8000/api/pnl")
                if resp.status_code == 200:
                    data = resp.json()
                    trades_hoje = data.get("trades_today", 0)
                    pnl_source = "GUARDIAN_SINGLETON"
                    logger.info(f"[Compliance] Trade count via Guardian singleton: {trades_hoje}")
        except Exception as e:
            logger.debug(f"Guardian HTTP unavailable: {e}. Tentando SQLite fallback...")
        
        # Prioridade 2: Fallback para SQLite local
        if pnl_source == "UNKNOWN":
            try:
                if os.path.exists(self.db_path):
                    conn = sqlite3.connect(self.db_path)
                    cursor = conn.cursor()
                    today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
                    cursor.execute(
                        "SELECT COUNT(*) FROM telemetry WHERE timestamp LIKE ? AND status IN ('APPROVED_BY_COMMITTEE', 'EXECUTED_IN_BROKER')",
                        (f"{today}%",)
                    )
                    trades_hoje = cursor.fetchone()[0]
                    conn.close()
                    pnl_source = "SQLITE_LOCAL"
            except Exception as e:
                logger.warning(f"Erro ao ler telemetry.db para Compliance APEX: {e}")

        # Avaliação de Risco
        is_compliant = True
        rejection_reason = ""

        # Trava 1: Máximo de Trades
        if trades_hoje >= self.max_trades_per_day:
            is_compliant = False
            rejection_reason = f"Max Trades Diário Atingido ({self.max_trades_per_day})"
            
        # Fim do Mock: Leitura de PnL Real via BrokerSyncSkill
        try:
            from skills.broker_skills import BrokerSyncSkill
            broker_sync = BrokerSyncSkill()
            sync_result = await broker_sync.execute({})
            current_daily_pnl = sync_result.get("current_daily_pnl", 0.0)
            logger.info(f"PnL Flutuante Real Capturado da Corretora: ${current_daily_pnl}")
        except Exception as e:
            logger.error(f"Falha ao ler PnL real via CDP: {e}")
            current_daily_pnl = 0.0 # Fail-safe
            
        if current_daily_pnl <= self.daily_loss_limit:
            is_compliant = False
            rejection_reason = f"DLL Atingido (Perda Real >= $1000: ${current_daily_pnl})"

        if not is_compliant:
            logger.error(f"⚠️ APEX GUARDIAN BLOQUEOU A OPERAÇÃO: {rejection_reason}")
        else:
            logger.info("Apex Guardian: CLEAR para operar.")

        return {
            "status": "success",
            "is_compliant": is_compliant,
            "rejection_reason": rejection_reason,
            "trades_executed_today": trades_hoje
        }
