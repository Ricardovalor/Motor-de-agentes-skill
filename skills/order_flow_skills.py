import logging
from typing import Dict, Any
from core.base import BaseSkill

logger = logging.getLogger("OrderFlow")

class LiquidityHeatmapSkill(BaseSkill):
    """
    Skill que lê o DOM (Depth of Market) Nível 2.
    Procura por anomalias de liquidez, como Spoofing ou Absorção Institucional.
    Usa dados reais do MarketDepthL2Skill (CDP) quando disponíveis.
    """
    def __init__(self):
        super().__init__(name="LiquidityHeatmapSkill", description="Análise de Fluxo (Tape Reading) Nível 2")

    async def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        asset = params.get("asset", "UNKNOWN")
        signal = params.get("signal", "NEUTRAL")
        
        logger.info(f"Escaneando Orderbook L2 (Tape Reading) para confirmar o fluxo direcional de {asset}...")
        
        # Tenta ler dados reais do DOM via CDP
        tape_bias = "NEUTRAL"
        institutional_absorption = False
        tape_score_modifier = 0.0
        data_available = False

        try:
            from skills.broker_skills import MarketDepthL2Skill
            l2_skill = MarketDepthL2Skill()
            l2_data = await l2_skill.execute({})
            data_available = l2_data.get("data_available", False)
            
            if data_available:
                imbalance = l2_data.get("l2_imbalance", 0)
                dominant = l2_data.get("dominant_force", "UNKNOWN")
                absorption = l2_data.get("absorption_detected", False)
                
                if absorption and dominant == "BUYERS":
                    tape_bias = "BULLISH_ABSORPTION"
                    institutional_absorption = signal in ["LONG", "BUY"]
                elif absorption and dominant == "SELLERS":
                    tape_bias = "BEARISH_ABSORPTION"
                    institutional_absorption = signal in ["SHORT", "SELL"]
                else:
                    tape_bias = "MIXED_FLOW"
        except Exception as e:
            logger.debug(f"Falha ao ler DOM L2 real: {e}")

        # Se não há dados reais, mantém NEUTRAL sem penalidade (decisão segura)
        if not data_available:
            logger.info("[TAPE] DOM L2 indisponível — aplicando viés NEUTRAL sem penalidade.")
            return {
                "tape_bias": "NEUTRAL",
                "institutional_absorption": False,
                "tape_score_modifier": 0.0,
                "data_available": False
            }
        
        if institutional_absorption:
            tape_score_modifier = 0.20
            logger.info("🔥 BALEIAS CONFIRMADAS! Lotes massivos absorvidos a favor da nossa direção.")
        else:
            if tape_bias != "MIXED_FLOW":
                tape_score_modifier = -0.30
                logger.warning(f"⚠️ DIVERGÊNCIA DE FLUXO! O algoritmo sugeriu {signal}, mas o fluxo está {tape_bias}.")
        
        return {
            "tape_bias": tape_bias,
            "institutional_absorption": institutional_absorption,
            "tape_score_modifier": tape_score_modifier,
            "data_available": True
        }
