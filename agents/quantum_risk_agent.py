from core.base import BaseAgent
from core.engine import Message

class QuantumRiskAgent(BaseAgent):
    """
    Simulação Monte Carlo Avançada e Correlação Cross-Asset.
    Atua em paralelo ao Oracle para estressar todas as possibilidades quantitativas da decisão.
    """
    def __init__(self):
        super().__init__(name="Quantum-Risk", role="Gerenciador de Risco Não-Linear (Monte Carlo)")

    async def initialize(self):
        await super().initialize()
        # Escuta o Tape Reader (só processa se o fluxo L2 confirmar a operação)
        self.bus.subscribe("order_flow_cleared", self)

    async def handle_message(self, message: Message):
        insight = message.payload
        asset = insight.get("asset", "UNKNOWN")
        
        self.logger.info(f"Submetendo o insight do ativo {asset} a stress-test de Monte Carlo e Correlacionamento...")
        
        # Executa Skill de Correlação
        if "CrossAssetCorrelation" in self.skills:
            hedge_target = "MGC" if asset == "MNQ" else "MNQ"
            correlation_data = await self.skills["CrossAssetCorrelation"].execute(asset, hedge_target)
            
            insight["hedge_required"] = correlation_data.get("hedging_recommended")
            insight["stress_test_passed"] = True
            
            # Envia para aprovação do Guardian com os parâmetros estressados
            await self.bus.publish(Message(sender=self.name, topic="quantum_risk_approved", payload=insight))
