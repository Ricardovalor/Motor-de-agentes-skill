from core.base import BaseAgent
from core.engine import Message

class TapeReaderAgent(BaseAgent):
    """
    O Analista de Fluxo (Tape Reader).
    Avalia a profundidade de mercado (DOM L2) antes da ordem
    chegar ao QuantumRisk. Se houver divergência no fluxo (Spoofing), 
    ele veta o trade.
    """
    def __init__(self):
        super().__init__(name="TapeReader-Flow", role="Especialista em Fluxo de Ordens e DOM")

    async def initialize(self):
        await super().initialize()
        # Escuta depois que o servidor estiver limpo pelo DevOps
        self.bus.subscribe("watchdog_cleared", self)

    async def handle_message(self, message: Message):
        insight = message.payload
        self.logger.info(f"Lendo a Fita (Tape) para validar a convicção do Oráculo em {insight.get('asset')}...")

        if "LiquidityHeatmapSkill" in self.skills:
            tape_eval = await self.skills["LiquidityHeatmapSkill"].execute(insight)
            
            insight["tape_bias"] = tape_eval["tape_bias"]
            old_confidence = insight.get("confidence", 0.0)
            insight["confidence"] += tape_eval["tape_score_modifier"]
            
            if tape_eval["tape_score_modifier"] < 0:
                self.logger.warning(f"Tape Reader derrubou a convicção de {old_confidence:.2f} para {insight['confidence']:.2f} devido a divergência no DOM.")
                
            if insight["confidence"] < 0.5:
                self.logger.critical(f"⛔ TRADE VETADO! Tape Reader detectou contra-fluxo institucional. Fique de fora de {insight.get('asset')}.")
                insight["status"] = "REJECTED_BY_TAPE_READER"
                insight["rejection_reason"] = "Fluxo de Ordens (Tape) Divergente"
                await self.bus.publish(Message(sender=self.name, topic="action_rejected", payload=insight))
                return
            
            # Se sobreviveu à fita, manda para o risco Quant
            await self.bus.publish(Message(sender=self.name, topic="order_flow_cleared", payload=insight))
        else:
            # GAP-F06 FIX: Sem LiquidityHeatmapSkill, faz pass-through em vez de morrer silenciosamente
            self.logger.warning("LiquidityHeatmapSkill não equipada — forward direto para QuantumRisk.")
            insight["tape_bias"] = "UNKNOWN"
            await self.bus.publish(Message(sender=self.name, topic="order_flow_cleared", payload=insight))
