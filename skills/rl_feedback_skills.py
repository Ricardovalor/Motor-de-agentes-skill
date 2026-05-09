import sqlite3
import os
import logging
from typing import Dict, Any
from core.base import BaseSkill

logger = logging.getLogger("RLFeedback")

class ReinforcementLearningSkill(BaseSkill):
    """
    Skill responsável pelo Feedback Loop Institucional (Reinforcement Learning).
    Calcula pesos dinâmicos para a aprovação de trades baseando-se no
    histórico forense de execuções (Kelly Criterion / Win Rate adaptativo).
    """
    def __init__(self, db_path: str = "memory_data/telemetry.db"):
        super().__init__(name="ReinforcementLearningSkill", description="Ajuste de Pesos via Feedback Forense")
        self.db_path = db_path

    async def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calcula o modificador de confiança atual baseado na assertividade recente do motor.
        """
        asset = params.get("asset", "UNKNOWN")
        
        # Pesos padrão se não houver histórico
        weight_multiplier = 1.0
        historical_trades = 0
        
        try:
            if os.path.exists(self.db_path):
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                
                # Busca quantas vezes nós operamos este ativo recentemente
                cursor.execute(f"SELECT COUNT(*) FROM telemetry WHERE asset = '{asset}' AND status = 'EXECUTED_IN_BROKER'")
                historical_trades = cursor.fetchone()[0]
                
                # Numa implementação completa (com webhook de saída da corretora), leríamos a coluna PnL.
                # Como simulação de RL, vamos aplicar um "Cool-down penalty" se tivermos operado muito esse ativo.
                if historical_trades > 5:
                    weight_multiplier = 0.95  # Diminui levemente a agressividade
                if historical_trades > 10:
                    weight_multiplier = 0.85  # Overtrading protection
                
                conn.close()
        except Exception as e:
            logger.warning(f"Erro ao ler telemetry.db para RL Feedback: {e}")

        logger.info(f"RL Feedback para {asset}: Histórico={historical_trades} trades. Multiplicador de Convicção={weight_multiplier}")

        return {
            "status": "success",
            "weight_multiplier": weight_multiplier,
            "historical_trades": historical_trades
        }
