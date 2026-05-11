from core.base import BaseAgent
from core.engine import Message

class TemporalAgent(BaseAgent):
    """
    Agente Mestre do Tempo (Temporal Agent).
    Focado em detectar padrões cíclicos e temporais nos dados usando Fractais e Cadeias de Markov.
    """
    def __init__(self):
        super().__init__(name="Temporal-Chronos", role="Analista de Assimetria Temporal")

    async def initialize(self):
        await super().initialize()
        self.bus.subscribe("data_ready", self)

    async def handle_message(self, message: Message):
        market_data = message.payload
        self.logger.info(f"Dados temporais recebidos. Procurando distorções fractais no tempo...")
        
        if "FractalPattern" in self.skills:
            # Envia dados históricos REAIS do ativo (DataFrame de preços)
            historical = market_data.get("history")
            if historical is None:
                self.logger.warning("Sem dados históricos para análise fractal. Pulando.")
                return
            
            fractal_insight = await self.skills["FractalPattern"].execute(historical_data=historical)
            
            # Incorpora os dados originais
            fractal_insight["asset"] = market_data.get("asset")
            fractal_insight["source"] = self.name
            
            await self.bus.publish(Message(sender=self.name, topic="temporal_insight_generated", payload=fractal_insight))
