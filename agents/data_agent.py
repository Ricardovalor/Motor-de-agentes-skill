from core.base import BaseAgent
from core.engine import Message
from config.settings import settings

class DataAgent(BaseAgent):
    """
    Agente responsável por coleta e estruturação de dados em tempo real.
    Invoca a MarketDataFetchSkill.
    """
    def __init__(self):
        super().__init__(name="Data-Ops", role="Coletor de Estrutura de Mercado")

    async def initialize(self):
        await super().initialize()
        self.bus.subscribe("data_request", self)

    async def handle_message(self, message: Message):
        asset = message.payload.get("asset", "MNQ")
        self.logger.info(f"Processando requisição de dados de {message.sender} para ativo: {asset}")
        
        # Executa a habilidade acoplada
        if "MarketDataFetch" in self.skills:
            # Puxa dados físicos da CLI
            market_data = await self.skills["MarketDataFetch"].execute(asset=asset)
            
            # BUG-2 FIX: Verifica se dados estão realmente disponíveis
            if not market_data.get("data_available", True) or market_data.get("source") == "UNAVAILABLE":
                self.logger.error(f"Dados indisponíveis para {asset} (TV MCP + Yahoo falharam). Pipeline abortado.")
                await self.bus.publish(Message(
                    sender=self.name, topic="action_rejected",
                    payload={"asset": asset, "status": "REJECTED_NO_DATA", "rejection_reason": "Fontes de dados indisponíveis"}
                ))
                return
            
            # UNIFICAÇÃO CRÍTICA: Mescla os dados recebidos via Webhook (Pine Script Alerts)
            # com os dados capturados via CLI, dando prioridade para alertas nativos
            # Protege contra campos nulos do webhook sobrescrevendo dados reais
            webhook_data = {k: v for k, v in message.payload.items() if v is not None and v != 0}
            unified_data = {**market_data, **webhook_data}
            
            self.logger.info(f"Dados unificados com sucesso para {asset}. Fonte: {market_data.get('source')}. Iniciando roteamento Macro...")
            
            # Dispara o evento de dados prontos
            await self.bus.publish(Message(sender=self.name, topic="data_ready", payload=unified_data))
        else:
            self.logger.error("Habilidade de busca de mercado ausente!")
