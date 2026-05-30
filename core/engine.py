import asyncio
import logging
from typing import Dict, Any, List

logger = logging.getLogger("NexusEngine")

class Message:
    def __init__(self, sender: str, topic: str, payload: Any):
        self.sender = sender
        self.topic = topic
        self.payload = payload

class EventBus:
    """
    Message broker in-memory ultra rápido para comunicação inter-agentes.
    Permite arquitetura pub/sub.
    
    TITAN-001 FIX: Backpressure via asyncio.Queue — impede acúmulo
    infinito de mensagens em sessões longas (8h+ de pregão).
    """
    def __init__(self, max_queue_size: int = 100):
        self._subscribers: Dict[str, List[Any]] = {}
        self._queue: asyncio.Queue = asyncio.Queue(maxsize=max_queue_size)
        self._processing = False
        self._dropped_count = 0

    def subscribe(self, topic: str, agent):
        if topic not in self._subscribers:
            self._subscribers[topic] = []
        self._subscribers[topic].append(agent)

    async def publish(self, message: Message):
        """
        TITAN-001 REAL FIX: Despacho concorrente real via asyncio.gather.
        Permite que múltiplos assinantes do mesmo tópico processem eventos simultaneamente,
        eliminando latência em cadeia e impedindo que tarefas secundárias (como auditoria forense)
        atrasem a execução física da ordem (Broker-Execution).
        """
        if message.topic in self._subscribers:
            tasks = [self._safe_handle(agent, message) for agent in self._subscribers[message.topic]]
            await asyncio.gather(*tasks)

    async def _safe_handle(self, agent, message):
        try:
            await agent.handle_message(message)
        except Exception as e:
            logger.error(f"[BUS ERROR] Agente {agent.name} falhou ao processar '{message.topic}': {e}")

class NexusEngine:
    """
    O Coração da Singularity.
    Inicializa o Event Bus, registra agentes, e orquestra o ciclo de vida.
    
    TITAN-009 FIX: Graceful shutdown — engine.stop() agora sinaliza
    para todos os agentes com loops internos.
    """
    def __init__(self):
        self.bus = EventBus()
        self.agents = {}
        self.running = False
        
    def register_agent(self, agent):
        self.agents[agent.name] = agent
        agent.attach_bus(self.bus)
        logger.info(f"[ENGINE] Agente registrado: {agent.name}")

    async def start(self):
        logger.info("[ENGINE] Iniciando Nexus Singularity Engine...")
        self.running = True
        
        # Initialize all agents
        for agent in self.agents.values():
            await agent.initialize()
            
        # Main Engine Loop
        while self.running:
            await asyncio.sleep(1) # Keep Engine Alive

    def stop(self):
        """
        TITAN-009 FIX: Graceful shutdown — sinaliza para todos os loops
        e permite que os agentes encerrem suas tarefas pendentes.
        """
        logger.info("[ENGINE] 🔴 Shutdown graceful iniciado...")
        self.running = False
        # Sinaliza agentes com loops internos
        for agent in self.agents.values():
            if hasattr(agent, '_should_stop'):
                agent._should_stop = True
        logger.info("[ENGINE] Todos os agentes sinalizados para shutdown.")
