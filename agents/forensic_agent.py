import asyncio
from core.base import BaseAgent
from core.engine import Message
from memory.memory_manager import VectorMemory, StateMemory
from memory.supabase_manager import SupabaseManager
from config.settings import settings

class ForensicAgent(BaseAgent):
    """
    Auditoria e Machine Learning Feedback.
    Salva TUDO no SQLite, Supabase e cria contexto vetorizado no ChromaDB para IA.
    """
    def __init__(self):
        super().__init__(name="Forensic-Audit", role="Log Institucional e Feedback ML")
        self.vector_db = VectorMemory(persist_dir=settings.CHROMA_DB_PATH)
        self.sql_db = StateMemory(db_path="memory_data/telemetry.db")
        self.supabase_db = SupabaseManager()

    async def initialize(self):
        await super().initialize()
        self.bus.subscribe("execute_action", self)
        self.bus.subscribe("action_rejected", self) # Grava o que foi rejeitado também
        self.bus.subscribe("trade_receipt", self) # Recibos físicos do Broker

    async def handle_message(self, message: Message):
        payload = message.payload
        topic = message.topic
        
        status = "UNKNOWN"
        asset = payload.get("asset", "UNKNOWN")
        signal = payload.get("signal", "UNKNOWN")
        confidence = payload.get("confidence", 0.0)

        if topic == "execute_action":
            status = "APPROVED_BY_COMMITTEE"
        elif topic == "action_rejected":
            # BUG-H05 FIX: Preserva o status real (MACRO, WATCHDOG, TAPE_READER, etc.)
            status = payload.get("status", "REJECTED_BY_GUARDIAN")
        elif topic == "trade_receipt":
            status = "EXECUTED_IN_BROKER"
            asset = payload.get("trade_payload", {}).get("asset", "UNKNOWN")
            signal = payload.get("trade_payload", {}).get("signal", "UNKNOWN")
            confidence = payload.get("trade_payload", {}).get("confidence", 0.0)

        # Salva em SQLite para dashboards clássicos - off-thread via asyncio.to_thread para não travar o Event Loop (TITAN-002 real fix)
        await asyncio.to_thread(
            self.sql_db.log_execution,
            asset=asset,
            signal=signal,
            confidence=confidence,
            status=status,
            raw_data=payload
        )
        
        # Envia para a nuvem no Supabase para Data Lake e integrações Web
        self.supabase_db.log_pipeline_execution(
            asset=asset,
            signal=signal,
            confidence=confidence,
            status=status,
            raw_data=payload
        )
        
        # Cria a descrição semântica
        semantic_context = (
            f"O motor operou o ativo {asset} com o sinal {signal}. "
            f"Convicção de {confidence:.2f}. "
            f"O status final foi {status}."
        )
        
        # Salva no VectorDB para o Oracle ler em execuções futuras
        self.vector_db.store(
            context=semantic_context, 
            metadata={"asset": asset, "signal": signal, "status": status}
        )
        
        self.logger.info(f"Auditoria concluída. Dados armazenados em SQLite e ChromaDB.")
