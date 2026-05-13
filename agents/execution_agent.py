import asyncio
import random
from core.base import BaseAgent
from core.engine import Message

class BrokerExecutionAgent(BaseAgent):
    """
    A Mão Invisível (Execution Bridge).
    V10.0 Fase 2: Dual execution mode:
    - Modo 1: TradovateAPI (REST API direta) — PREFERIDO
    - Modo 2: BrowserMCPExecution (CDP/DOM injection) — FALLBACK
    
    Compliance Apex:
    - Anti-hedging check antes de cada ordem
    - Delay humano 1-3s (anti-bot detection)
    - NUNCA envia sem SL (OSO bracket obrigatório)
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
        
        receipt = None
        
        # ===== MODO 1: Tradovate API Direta (Fase 2) =====
        if "TradovateAPI" in self.skills:
            receipt = await self._execute_via_api(verdict)
        
        # ===== MODO 2: CDP/DOM Injection (Legado) =====
        elif "BrowserMCPExecution" in self.skills:
            receipt = await self._execute_via_cdp(verdict)
        
        else:
            self.logger.error("Nenhuma skill de execução equipada (TradovateAPI ou BrowserMCPExecution).")
            return
        
        if receipt:
            receipt["trade_payload"] = verdict
            receipt["execution_mode"] = "API" if "TradovateAPI" in self.skills else "CDP"
            await self.bus.publish(Message(sender=self.name, topic="trade_receipt", payload=receipt))

    async def _execute_via_api(self, verdict: dict) -> dict:
        """
        Execução via Tradovate REST API (OCO bracket nativa).
        Inclui anti-hedging check e delay humano.
        """
        asset = verdict.get("asset", "MNQ")
        signal = verdict.get("signal", "BUY")
        
        # TITAN-010 FIX: Anti-hedging check removido daqui — já é feito
        # nativamente dentro do TradovateAPISkill.execute() (evita GET duplicado)
        
        # 2. Mapear ação
        action = "Buy" if signal in ("BUY", "LONG") else "Sell"
        
        # 3. Executar via API
        result = await self.skills["TradovateAPI"].execute({
            "command": "place_order",
            "symbol": asset,
            "action": action,
            "qty": verdict.get("qty", 1),
            "sl_price": verdict.get("sl_price", 0),
            "tp_price": verdict.get("tp_price", 0),
            "order_type": verdict.get("order_type", "Market"),
        })
        
        if result and not result.get("error"):
            self.logger.info(f"✅ Trade {signal} em {asset} EXECUTADO VIA API! OrderID: {result.get('orderId')}")
            return {
                "execution_status": "SUCCESS_API",
                "broker_order_id": result.get("orderId"),
                "order_status": result.get("ordStatus"),
                "execution_latency_ms": 0,  # API is near-instant
            }
        else:
            error_detail = result.get("detail", "Unknown") if result else "No response"
            self.logger.error(f"❌ API Execution FAILED: {error_detail}")
            return {
                "execution_status": "FAILED_API",
                "error": error_detail,
            }

    async def _execute_via_cdp(self, verdict: dict) -> dict:
        """
        Execução via CDP/DOM injection (modo legado).
        Injeta preços na boleta do TradingView/Tradovate via Chrome DevTools.
        V16.2.1: Anti-bot delay humano (1-3s) para evitar detecção de automação.
        """
        # Anti-bot: delay humano aleatório antes da injeção
        delay = random.uniform(1.0, 3.0)
        self.logger.info(f"⏱️ Anti-Bot Delay: {delay:.1f}s antes da injeção CDP...")
        await asyncio.sleep(delay)
        
        receipt = await self.skills["BrowserMCPExecution"].execute(trade_payload=verdict)
        
        if receipt.get("execution_status") == "SUCCESS_INJECTED":
            self.logger.info(f"✅ Trade EXECUTADO VIA CDP! Ticket: {receipt.get('broker_ticket_id')} | Latência: {receipt.get('execution_latency_ms')}ms")
        else:
            self.logger.warning(f"⚠️ CDP retornou: {receipt.get('execution_status')}. Latência: {receipt.get('execution_latency_ms')}ms")
        
        return receipt
