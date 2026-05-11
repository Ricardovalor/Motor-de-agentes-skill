from core.base import BaseAgent
from core.engine import Message

class MacroSentimentAgent(BaseAgent):
    """
    O Especialista Geopolítico e Macroeconômico.
    V10.0 Fase 2/3: Dupla camada de proteção macro:
    - Camada 1: MacroCalendarSkill (ForexFactory) → Blackout Window T-15/T+15
    - Camada 2: MacroNewsSkill (CNBC RSS) → Keyword shock detection
    """
    def __init__(self):
        super().__init__(name="Macro-Geopolitica", role="Especialista em Choque de Liquidez e Notícias")

    async def initialize(self):
        await super().initialize()
        # Escuta quando os dados de preço chegam (antes do Oracle)
        self.bus.subscribe("data_ready", self)

    async def handle_message(self, message: Message):
        market_data = message.payload
        self.logger.info(f"Fazendo varredura macroeconômica global para o ativo {market_data.get('asset')}...")

        # ===== CAMADA 1: Calendar Blackout (Fase 3) =====
        if "MacroCalendarSkill" in self.skills:
            calendar_result = await self.skills["MacroCalendarSkill"].execute()
            market_data["calendar_blackout"] = calendar_result.get("blackout_active", False)
            market_data["calendar_action"] = calendar_result.get("action", "CLEAR")
            market_data["next_macro_event"] = calendar_result.get("next_event")
            
            if calendar_result.get("blackout_active"):
                reason = calendar_result.get("reason", "Unknown macro event")
                self.logger.critical(f"⛔ BLACKOUT WINDOW ATIVO! {reason}")
                market_data["status"] = "REJECTED_BY_MACRO_CALENDAR"
                market_data["rejection_reason"] = f"Blackout Window: {reason}"
                market_data["macro_sentiment"] = "BLACKOUT"
                await self.bus.publish(Message(sender=self.name, topic="action_rejected", payload=market_data))
                return
        
        # ===== CAMADA 2: RSS Shock Detection (Original) =====
        if "MacroNewsSkill" in self.skills:
            macro_context = await self.skills["MacroNewsSkill"].execute()
            
            # Repassa os dados brutos de mercado AGORA COM O CONTEXTO MACRO ANEXADO
            market_data["macro_sentiment"] = macro_context["macro_sentiment"]
            market_data["news_headline"] = macro_context["last_headline"]
            market_data["red_folder_imminent"] = macro_context["red_folder_imminent"]
            market_data["news_volatility_multiplier"] = macro_context.get("news_volatility_multiplier", 1.0)
            
            if macro_context["red_folder_imminent"]:
                self.logger.critical(f"⛔ TRADE VETADO! Notícia de Alto Impacto (Red Folder) iminente. Bloqueando operações em {market_data.get('asset')}.")
                market_data["status"] = "REJECTED_BY_MACRO"
                market_data["rejection_reason"] = "Choque de Liquidez Macroeconômico (Notícia)"
                await self.bus.publish(Message(sender=self.name, topic="action_rejected", payload=market_data))
                return
            
            # Se não há notícias, repassa a bola para o Oráculo fazer análise gráfica
            await self.bus.publish(Message(sender=self.name, topic="macro_context_ready", payload=market_data))
        else:
            self.logger.error("Habilidade MacroNewsSkill não equipada!")
