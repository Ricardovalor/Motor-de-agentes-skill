import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Dict, Any

class BaseSkill(ABC):
    """
    Habilidade Genérica que pode ser acoplada a qualquer agente.
    """
    def __init__(self, name: str):
        self.name = name
        self.logger = logging.getLogger(f"Skill_{name}")

    @abstractmethod
    async def execute(self, **kwargs) -> Any:
        """ Execução principal da skill. """
        pass

class BaseAgent(ABC):
    """
    Agente Autônomo Base equipado com capacidade de comunicação e Habilidades (Skills).
    """
    def __init__(self, name: str, role: str):
        self.name = name
        self.role = role
        self.bus = None
        self.skills: Dict[str, BaseSkill] = {}
        self.logger = logging.getLogger(f"Agent_{name}")

    def attach_bus(self, bus):
        self.bus = bus

    def equip_skill(self, skill: BaseSkill):
        self.skills[skill.name] = skill
        self.logger.info(f"Equipado com a skill: {skill.name}")

    async def initialize(self):
        self.logger.info(f"Agente {self.name} ({self.role}) online e operante.")

    @abstractmethod
    async def handle_message(self, message):
        """
        Define como o agente reage aos eventos do Event Bus.
        """
        pass
