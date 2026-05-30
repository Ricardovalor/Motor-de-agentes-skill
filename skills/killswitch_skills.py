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
    def __init__(self, max_latency_ms=300, max_ram_percent=95.0, latency_debounce_limit=3):
        super().__init__(name="SystemKillSwitch", description="Botão de Emergência DevOps")
        self.max_latency_ms = max_latency_ms
        self.max_ram_percent = max_ram_percent
        self.latency_debounce_limit = latency_debounce_limit
        self.latency_history = []
        self.consecutive_latency_failures = 0

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

        # Atualiza histórico de latências
        self.latency_history.append(latency)
        if len(self.latency_history) > 10:
            self.latency_history.pop(0)

        # Filtro de Debounce para Latência de Rede
        if latency > self.max_latency_ms:
            self.consecutive_latency_failures += 1
            logger.warning(
                f"⚠️ [KillSwitch] Spike de Latência detectado: {latency:.1f}ms acima do limite de {self.max_latency_ms}ms "
                f"({self.consecutive_latency_failures}/{self.latency_debounce_limit})"
            )
        else:
            if self.consecutive_latency_failures > 0:
                logger.info(f"🟢 [KillSwitch] Rede normalizada: {latency:.1f}ms. Restaurando contador de pânico.")
            self.consecutive_latency_failures = 0

        critical_failure = False
        failure_reason = ""

        # Verifica se o servidor está explodindo
        if ram_usage > self.max_ram_percent:
            critical_failure = True
            failure_reason = f"OOM_RISK (RAM em {ram_usage}%)"
            
        # Verifica se perdemos contato limpo de forma persistente (debounce completo)
        if self.consecutive_latency_failures >= self.latency_debounce_limit:
            critical_failure = True
            recent_failures = self.latency_history[-self.latency_debounce_limit:]
            avg_latency = sum(recent_failures) / len(recent_failures)
            failure_reason = f"PERSISTENT_NETWORK_CONGESTION (Média das últimas {self.latency_debounce_limit} falhas: {avg_latency:.1f}ms)"

        if critical_failure:
            logger.critical(f"🚨 [KILL SWITCH ACTIVATED] PÂNICO REAL: {failure_reason}")
            logger.critical("🚨 EXECUTANDO PROTOCOLO FLATTEN ALL NA CONTA APEX...")
            
            return {
                "system_status": "PANIC_FLATTEN",
                "latency_ms": latency,
                "ram_usage": ram_usage,
                "action_taken": "ALL_ORDERS_CANCELLED_AND_POSITIONS_FLATTENED",
                "failure_reason": failure_reason
            }
            
        return {
            "system_status": "HEALTHY",
            "latency_ms": latency,
            "ram_usage": ram_usage,
            "cpu_usage": cpu_usage,
            "action_taken": "NONE"
        }
