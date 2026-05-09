from core.base import BaseAgent
from core.engine import Message
from config.settings import settings

class OracleAgent(BaseAgent):
    """
    Inteligência Analítica. Usa a skill de análise quantitativa.
    """
    def __init__(self):
        super().__init__(name="Oracle-Prime", role="Especialista Analítico Quant")

    async def initialize(self):
        await super().initialize()
        # Escuta apenas DEPOIS que o Agente Macro validar que não há notícias bomba
        self.bus.subscribe("macro_context_ready", self)

    async def handle_message(self, message: Message):
        market_data = message.payload
        self.logger.info(f"Dados recebidos. Analisando o fluxo estrutural de {market_data.get('asset')}...")
        
        if "StrategyAnalysis" in self.skills and "SmcTechnicalSkill" in self.skills and "GeminiInference" in self.skills:
            # 1. Análise Matemática Quantitativa (Quant Chair)
            insight = await self.skills["StrategyAnalysis"].execute(market_data=market_data)
            
            # 2. Análise Estrutural SMC (Técnico Chair)
            smc_insight = await self.skills["SmcTechnicalSkill"].execute(market_data=market_data)
            
            # Merge de dados Quant + SMC
            insight["smc_bias"] = smc_insight["smc_bias"]
            insight["fvg_detected"] = smc_insight["fvg_detected"]
            insight["fvg_type"] = smc_insight["fvg_type"]
            insight["confidence"] += smc_insight["confidence_boost"]
            
            # 3. Salto Cognitivo Generativo (LLM)
            ai_context = f"Ativo: {market_data.get('asset')} | RSI: {market_data.get('rsi_14')} | SMC Bias: {insight['smc_bias']} | FVG: {insight['fvg_detected']} ({insight['fvg_type']}) | Macro Context: {market_data.get('macro_sentiment')} ({market_data.get('news_headline')}) | Base Insight: {insight['signal']}"
            ai_insight = await self.skills["GeminiInference"].execute(prompt_context=ai_context)
            
            # Fusão de Inteligências
            insight["asset"] = market_data.get("asset")
            insight["price"] = market_data.get("price")
            insight["cognitive_override"] = ai_insight["cognitive_decision"]
            insight["confidence"] = min((insight["confidence"] + ai_insight["ai_confidence"]) / 2, 1.0) # Média Bayesiana, cap em 1.0
            
            await self.bus.publish(Message(sender=self.name, topic="insight_generated", payload=insight))
        else:
            self.logger.error("Faltam habilidades analíticas no Oracle (SMC, Quant ou Gemini ausente)!")
