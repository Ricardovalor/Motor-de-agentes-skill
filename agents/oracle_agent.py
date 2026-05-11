from core.base import BaseAgent
from core.engine import Message
from config.settings import settings
from memory.memory_manager import VectorMemory

class OracleAgent(BaseAgent):
    """
    Inteligência Analítica. Usa a skill de análise quantitativa.
    Possui RAG (Retrieval-Augmented Generation) acessando VectorMemory.
    """
    def __init__(self):
        super().__init__(name="Oracle-Prime", role="Especialista Analítico Quant")
        self.vector_db = VectorMemory(persist_dir=settings.CHROMA_DB_PATH)
        self._temporal_cache = {}  # Cache de insights fractais recebidos do TemporalAgent

    async def initialize(self):
        await super().initialize()
        # Escuta apenas DEPOIS que o Agente Macro validar que não há notícias bomba
        self.bus.subscribe("macro_context_ready", self)
        # L4 FIX: Também recebe insights temporais (fractais) do TemporalAgent
        self.bus.subscribe("temporal_insight_generated", self)

    async def handle_message(self, message: Message):
        # Diferencia o tópico: temporal é apenas enriquecimento, não dispara pipeline
        if message.topic == "temporal_insight_generated":
            asset = message.payload.get("asset", "UNKNOWN")
            self._temporal_cache[asset] = message.payload
            self.logger.info(f"Insight temporal (Hurst) recebido e cacheado para {asset}: H={message.payload.get('fractal_entropy')}")
            return

        # A partir daqui, é macro_context_ready → pipeline completo
        market_data = message.payload
        
        # BUG-2 FIX: Verifica se dados estão disponíveis antes de processar
        if not market_data.get("data_available", True) or market_data.get("source") == "UNAVAILABLE":
            self.logger.error(f"Dados de mercado indisponíveis para {market_data.get('asset')}. Abortando análise.")
            return
        
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
            
            # 2.3 Merge de dados Temporais (Fractais) se disponíveis
            asset = market_data.get("asset", "UNKNOWN")
            temporal_data = self._temporal_cache.pop(asset, None)
            if temporal_data:
                insight["fractal_entropy"] = temporal_data.get("fractal_entropy", 0.5)
                insight["fractal_bias"] = temporal_data.get("mathematical_bias", "NEUTRAL")
                if temporal_data.get("hidden_pattern_detected"):
                    insight["confidence"] += 0.05
                    self.logger.info(f"Padrão fractal detectado (H={temporal_data['fractal_entropy']:.3f}). Boost +0.05 na confiança.")
            
            # 2.5 RAG: Consulta memórias antigas (Machine Learning Loop)
            query = f"Ativo {market_data.get('asset')} com RSI {insight.get('rsi_14')} e FVG {insight['fvg_type']}"
            past_memories = self.vector_db.retrieve(query=query, n_results=2)
            memory_str = " | ".join(past_memories) if past_memories else "Nenhuma memória similar."
            
            # 3. Salto Cognitivo Generativo (LLM + RAG)
            ai_context = f"Ativo: {market_data.get('asset')} | RSI: {insight.get('rsi_14')} | SMC Bias: {insight['smc_bias']} | FVG: {insight['fvg_detected']} ({insight['fvg_type']}) | Macro Context: {market_data.get('macro_sentiment')} ({market_data.get('news_headline')}) | Base Insight: {insight['signal']} | Memória Passada: {memory_str}"
            ai_insight = await self.skills["GeminiInference"].execute(prompt_context=ai_context)
            
            # Fusão de Inteligências
            insight["asset"] = market_data.get("asset")
            insight["price"] = market_data.get("price")
            insight["news_headline"] = market_data.get("news_headline")
            insight["macro_sentiment"] = market_data.get("macro_sentiment")
            insight["cognitive_override"] = ai_insight["cognitive_decision"]
            insight["confidence"] = min((insight["confidence"] + ai_insight["ai_confidence"]) / 2, 1.0) # Média Bayesiana, cap em 1.0
            
            await self.bus.publish(Message(sender=self.name, topic="insight_generated", payload=insight))
        else:
            self.logger.error("Faltam habilidades analíticas no Oracle (SMC, Quant ou Gemini ausente)!")
