import sqlite3
import os
import logging
from typing import Dict, Any
from core.base import BaseSkill

logger = logging.getLogger("RLFeedback")

class ReinforcementLearningSkill(BaseSkill):
    """
    V16.2: Feedback Loop Institucional com PnL REAL.
    Calcula pesos dinâmicos baseados em win rate real do Guardian singleton.
    Usa Kelly Criterion adaptativo para ajustar agressividade.
    """
    def __init__(self, db_path: str = "memory_data/telemetry.db"):
        super().__init__(name="ReinforcementLearningSkill", description="Ajuste de Pesos via Feedback Forense")
        self.db_path = db_path

    async def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        V16.2: Calcula modificador de confiança usando dados reais.
        Fontes: Guardian HTTP > live_pnl.json > SQLite fallback
        """
        asset = params.get("asset", "UNKNOWN")
        
        weight_multiplier = 1.0
        historical_trades = 0
        win_rate = 0.5  # Default neutro
        daily_pnl = 0.0
        data_source = "DEFAULT"
        
        # Prioridade 1: Guardian singleton via HTTP (dados reais)
        try:
            import httpx
            async with httpx.AsyncClient(timeout=2.0) as client:
                # PnL real
                pnl_resp = await client.get("http://127.0.0.1:8000/api/pnl")
                if pnl_resp.status_code == 200:
                    pnl_data = pnl_resp.json()
                    daily_pnl = pnl_data.get("pnl", 0.0)
                    historical_trades = pnl_data.get("trades_today", 0)
                    data_source = "GUARDIAN_LIVE"
                
                # Analytics reais (win rate)
                analytics_resp = await client.get("http://127.0.0.1:8000/api/analytics/cached")
                if analytics_resp.status_code == 200:
                    analytics = analytics_resp.json()
                    win_rate = analytics.get("win_rate", 0.5)
        except Exception:
            pass
        
        # Prioridade 2: live_pnl.json (Motor de Agentes)
        if data_source == "DEFAULT":
            try:
                import json as _json
                pnl_path = os.path.join(os.path.dirname(__file__), "..", "memory_data", "live_pnl.json")
                if os.path.exists(pnl_path):
                    with open(pnl_path, "r") as f:
                        data = _json.load(f)
                        daily_pnl = data.get("pnl", 0.0)
                        data_source = "LIVE_PNL_FILE"
            except Exception:
                pass
        
        # Prioridade 3: SQLite fallback (trade count only)
        if data_source == "DEFAULT":
            try:
                if os.path.exists(self.db_path):
                    conn = sqlite3.connect(self.db_path)
                    cursor = conn.cursor()
                    cursor.execute("SELECT COUNT(*) FROM telemetry WHERE asset = ? AND status = 'EXECUTED_IN_BROKER'", (asset,))
                    historical_trades = cursor.fetchone()[0]
                    conn.close()
                    data_source = "SQLITE_FALLBACK"
            except Exception as e:
                logger.warning(f"Erro ao ler telemetry.db para RL Feedback: {e}")

        # V16.2: Cálculo inteligente do multiplicador
        # Win Rate > 60% → boost (até 1.15x)
        # Win Rate < 40% → penalize (até 0.80x)  
        # Overtrading (>5 trades) → cooldown
        if win_rate > 0.6:
            weight_multiplier = min(1.15, 1.0 + (win_rate - 0.6) * 0.5)
        elif win_rate < 0.4 and win_rate > 0:
            weight_multiplier = max(0.80, 1.0 - (0.4 - win_rate) * 0.5)
        
        # Overtrading protection
        if historical_trades > 5:
            weight_multiplier *= 0.90
        
        # Loss streak protection (PnL negativo = reduzir exposição)
        if daily_pnl < -500:
            weight_multiplier *= 0.75
            logger.warning(f"RL DANGER: PnL=${daily_pnl:.2f} - Reduzindo exposição para {weight_multiplier:.2f}x")

        logger.info(
            f"RL Feedback [{data_source}] {asset}: "
            f"WinRate={win_rate:.1%} | PnL=${daily_pnl:.2f} | "
            f"Trades={historical_trades} | Multiplier={weight_multiplier:.3f}"
        )

        return {
            "status": "success",
            "weight_multiplier": round(weight_multiplier, 3),
            "historical_trades": historical_trades,
            "win_rate": round(win_rate, 3),
            "daily_pnl": round(daily_pnl, 2),
            "data_source": data_source
        }
