from core.base import BaseAgent
from core.engine import Message
import asyncio

class DevOpsWatchdogAgent(BaseAgent):
    """
    O Cão de Guarda da Infraestrutura HFT.
    V10.0 Fase 2: Upgrade com FLATTEN real via Tradovate API.
    
    Dupla proteção (belt-and-suspenders):
    - Camada 1: TradovateAPI.flatten_all() → liquida via API REST
    - Camada 2: KillSwitch log + abort pipeline → impede novas ordens
    """
    def __init__(self):
        super().__init__(name="DevOps-Watchdog", role="Protetor da Infraestrutura e Latência")
        self.health_loop_task = None

    async def initialize(self):
        await super().initialize()
        # Escuta qualquer pedido de trade. Se o watchdog notar falha de infra, 
        # ele grita "action_rejected" e veta a ordem na hora.
        self.bus.subscribe("insight_generated", self)

    async def handle_message(self, message: Message):
        if "SystemKillSwitch" not in self.skills:
            return

        insight = message.payload
        self.logger.info(f"Fazendo Check-up de Infraestrutura antes da ordem {insight.get('asset')} passar pro Guardião...")
        
        health_report = await self.skills["SystemKillSwitch"].execute()
        
        if health_report["system_status"] == "PANIC_FLATTEN":
            self.logger.critical(f"❌ INFRAESTRUTURA COMPROMETIDA! Abortando trade {insight.get('asset')} e isolando sistema!")
            insight["status"] = "REJECTED_BY_WATCHDOG"
            insight["rejection_reason"] = "Falha Crítica no Servidor/Rede (Ping ou RAM)"
            
            # === FASE 2: FLATTEN REAL VIA API ===
            if "TradovateAPI" in self.skills:
                self.logger.critical("🚨 KILL SWITCH: Executando FLATTEN ALL via Tradovate API...")
                try:
                    flatten_result = await self.skills["TradovateAPI"].flatten_all()
                    self.logger.critical(f"🚨 FLATTEN RESULT: {flatten_result}")
                except Exception as e:
                    self.logger.critical(f"🚨 FLATTEN API FAILED: {e}. Posições podem estar abertas!")
            
            # Cortamos as asas do Oracle antes mesmo do Guardião ver a ordem
            await self.bus.publish(Message(sender=self.name, topic="action_rejected", payload=insight))
        else:
            self.logger.info(f"Infraestrutura SAUDÁVEL. Ping: {health_report['latency_ms']:.1f}ms | RAM: {health_report['ram_usage']}%")
            # Libera a ordem para o fluxo normal do QuantumRisk
            await self.bus.publish(Message(sender=self.name, topic="watchdog_cleared", payload=insight))
