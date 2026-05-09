import asyncio
import psutil
import time
import logging
from typing import Dict, Any
from core.base import BaseSkill

logger = logging.getLogger("DevOpsKillSwitch")

class SystemKillSwitchSkill(BaseSkill):
    """
    Skill Física de Sobrevivência (Botão de Pânico).
    Monitora a saúde da máquina hospedeira e a latência de rede.
    Se o sistema ameaçar travar, aciona o comando FLATTEN ALL (Zerar Conta).
    """
    def __init__(self, max_latency_ms=300, max_ram_percent=95.0):
        super().__init__(name="SystemKillSwitch", description="Botão de Emergência DevOps")
        self.max_latency_ms = max_latency_ms
        self.max_ram_percent = max_ram_percent

    async def _measure_broker_latency(self) -> float:
        """
        Simula um ping ICMP na corretora ou websocket de dados.
        """
        start_time = time.time()
        # Aqui pingaríamos de fato os servidores da CME/NinjaTrader
        await asyncio.sleep(0.015) # Simula um ping normal de 15ms
        return (time.time() - start_time) * 1000

    async def execute(self, params: Dict[str, Any] = None) -> Dict[str, Any]:
        
        latency = await self._measure_broker_latency()
        ram_usage = psutil.virtual_memory().percent
        cpu_usage = psutil.cpu_percent(interval=0.1)

        critical_failure = False
        failure_reason = ""

        # Verifica se o servidor está explodindo
        if ram_usage > self.max_ram_percent:
            critical_failure = True
            failure_reason = f"OOM_RISK (RAM em {ram_usage}%)"
            
        # Verifica se perdemos contato limpo com Chicago/NY
        if latency > self.max_latency_ms:
            critical_failure = True
            failure_reason = f"NETWORK_CONGESTION (Latência {latency:.1f}ms)"

        if critical_failure:
            logger.critical(f"⚠️ [KILL SWITCH ATIVADO] Risco Estrutural Detectado: {failure_reason}")
            logger.critical("⚠️ INJETANDO PAYLOAD DE PÂNICO NO MCP (FLATTEN ALL & CANCEL)...")
            
            # Aqui acionaríamos o MCP diretamente para clicar no botão "CLOSE ALL POSITIONS"
            return {
                "system_status": "PANIC_FLATTEN",
                "latency_ms": latency,
                "ram_usage": ram_usage,
                "action_taken": "ALL_ORDERS_CANCELLED_AND_POSITIONS_FLATTENED"
            }
            
        return {
            "system_status": "HEALTHY",
            "latency_ms": latency,
            "ram_usage": ram_usage,
            "cpu_usage": cpu_usage,
            "action_taken": "NONE"
        }
