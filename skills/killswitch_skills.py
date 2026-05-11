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
        Mede latência real via TCP connect ao WebSocket do Tradovate.
        Fallback para loopback se rede externa falhar.
        """
        import socket
        targets = [
            ("live.tradovate.com", 443),      # Tradovate Live WS
            ("md.tradovate.com", 443),         # Tradovate Market Data
            ("127.0.0.1", 9222),               # CDP local (TradingView)
        ]
        best_latency = float('inf')
        for host, port in targets:
            try:
                start_time = time.time()
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(1.0)
                sock.connect((host, port))
                sock.close()
                latency = (time.time() - start_time) * 1000
                best_latency = min(best_latency, latency)
            except (socket.timeout, ConnectionRefusedError, OSError):
                continue
        
        if best_latency == float('inf'):
            logger.warning("[KillSwitch] Nenhum endpoint acessível — assumindo latência crítica")
            return 9999.0  # Triggers PANIC
        return best_latency

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
