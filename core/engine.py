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
    """
    def __init__(self):
        self._subscribers: Dict[str, List[Any]] = {}

    def subscribe(self, topic: str, agent):
        if topic not in self._subscribers:
            self._subscribers[topic] = []
        self._subscribers[topic].append(agent)

    async def publish(self, message: Message):
        """
        V16.2 FIX: Sequential dispatch — subscribers are processed IN ORDER.
        This prevents race conditions where ExecutionAgent fires before Guardian validates.
        """
        if message.topic in self._subscribers:
            for agent in self._subscribers[message.topic]:
                await self._safe_handle(agent, message)

    async def _safe_handle(self, agent, message):
        try:
            await agent.handle_message(message)
        except Exception as e:
            logger.error(f"[BUS ERROR] Agente {agent.name} falhou ao processar '{message.topic}': {e}")

class NexusEngine:
    """
    O Coração da Singularity.
    Inicializa o Event Bus, registra agentes, e orquestra o ciclo de vida.
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
        logger.info("[ENGINE] Parando o Motor...")
        self.running = False
