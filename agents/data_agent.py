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
            market_data = await self.skills["MarketDataFetch"].execute(asset=asset)
            
            # Dispara o evento de dados prontos
            await self.bus.publish(Message(sender=self.name, topic="data_ready", payload=market_data))
        else:
            self.logger.error("Habilidade de busca de mercado ausente!")
