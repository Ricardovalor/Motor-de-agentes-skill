from core.base import BaseAgent
from core.engine import Message

class BrokerExecutionAgent(BaseAgent):
    """
    A Mão Invisível (Execution Bridge).
    Recebe o Veredito Final do Comitê e realiza a interação física (DOM/API) com a Corretora.
    """
    def __init__(self):
        super().__init__(name="Broker-Execution", role="Executor de Operações (Braço Robótico)")

    async def initialize(self):
        await super().initialize()
        # Ouve exclusivamente o sinal de 'execute_action' que vem do Committee
        self.bus.subscribe("execute_action", self)

    async def handle_message(self, message: Message):
        verdict = message.payload
        asset = verdict.get("asset")
        signal = verdict.get("signal")
        
        if signal == "NEUTRAL":
            self.logger.info(f"Sinal NEUTRO para {asset}. Omitindo execução de mercado.")
            return

        self.logger.info(f"Recebida ordem do Comitê para {asset} -> {signal}. Armando o Braço Robótico...")
        
        if "BrowserMCPExecution" in self.skills:
            # Envia a carga útil (Payload) para injeção no DOM
            receipt = await self.skills["BrowserMCPExecution"].execute(trade_payload=verdict)
            
            # Se executado com sucesso, repassa o recibo para o Forensic-Audit salvar
            if receipt.get("execution_status") == "SUCCESS":
                self.logger.info(f"✅ Trade de {signal} em {asset} EXECUTADO FISICAMENTE! Ticket: {receipt.get('broker_ticket_id')}")
                # Publica recibo para a telemetria final
                await self.bus.publish(Message(sender=self.name, topic="trade_receipt", payload=receipt))
        else:
            self.logger.error("Skill de execução MCP não equipada. Impossível operar.")
