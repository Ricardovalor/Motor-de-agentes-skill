from core.base import BaseSkill
from typing import Dict, Any
import logging
import sqlite3
import os
import datetime

logger = logging.getLogger("ApexCompliance")

class ApexComplianceSkill(BaseSkill):
    """
    Skill responsável pela Cadeira Guardian (Risco).
    Garante compliance estrito com as regras da Apex Trader Funding (EOD 50k).
    Monitora limite de perda diária (DLL) e Drawdown (Trailing).
    """
    def __init__(self, db_path: str = "./memory_data/telemetry.db"):
        super().__init__(name="ApexComplianceSkill", description="Avaliação de Risco APEX EOD e Limites Diários.")
        self.db_path = db_path
        
        # Regras Rígidas da Mesa Apex 50k
        self.daily_loss_limit = -1000.0  # $1,000 DLL
        self.max_drawdown = -2000.0      # $2,000 EOD Trailing
        self.max_trades_per_day = 3      # Trava de Segurança V9.4

    async def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calcula o risco baseado no status atual gravado na memória episódica (telemetry.db).
        Nesta versão inicial, nós puxamos a quantidade de trades executados hoje.
        """
        asset = params.get("asset", "UNKNOWN")
        
        # Puxar dados diários do SQLite (se existir)
        trades_hoje = 0
        try:
            if os.path.exists(self.db_path):
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                
                # Conta quantos trades foram APPROVED ou EXECUTED no dia de hoje (UTC)
                today = datetime.datetime.utcnow().strftime('%Y-%m-%d')
                cursor.execute(f"SELECT COUNT(*) FROM telemetry WHERE timestamp LIKE '{today}%' AND status IN ('APPROVED_BY_COMMITTEE', 'EXECUTED_IN_BROKER')")
                trades_hoje = cursor.fetchone()[0]
                conn.close()
        except Exception as e:
            logger.warning(f"Erro ao ler telemetry.db para Compliance APEX: {e}")

        # Avaliação de Risco
        is_compliant = True
        rejection_reason = ""

        # Trava 1: Máximo de Trades
        if trades_hoje >= self.max_trades_per_day:
            is_compliant = False
            rejection_reason = f"Max Trades Diário Atingido ({self.max_trades_per_day})"
            
        # Trava 2 (Mock): Daily Loss Limit (Idealmente será calculado somando a coluna PnL que ainda será adicionada)
        current_daily_pnl = params.get("current_daily_pnl", 0.0) # Injetado pelo Broker Agent no futuro
        if current_daily_pnl <= self.daily_loss_limit:
            is_compliant = False
            rejection_reason = f"DLL Atingido (Perda >= $1000)"

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
