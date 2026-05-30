import logging
from typing import Dict, Any, List
import json
import sqlite3
import os
import asyncio
import threading
try:
    import chromadb
except ImportError:
    chromadb = None

logger = logging.getLogger("MemoryBank")


class VectorMemory:
    """
    Banco de dados vetorial para memórias de longo prazo (RAG).
    Usando ChromaDB para persistência real e busca semântica.
    
    TITAN-003 FIX: Lock com timeout para evitar deadlock se ChromaDB travar.
    """
    def __init__(self, persist_dir: str = "./memory_data/chroma_data"):
        self.persist_dir = persist_dir
        if chromadb:
            self.client = chromadb.PersistentClient(path=self.persist_dir)
            self.collection = self.client.get_or_create_collection(name="nexus_knowledge")
            logger.info(f"VectorMemory (ChromaDB) inicializado em {self.persist_dir}")
        else:
            self.client = None
            logger.warning("ChromaDB não encontrado. Rodando em modo mock (apenas lista local).")
            self.knowledge_base = []
            
        # BUG-H03 FIX: Inicializa doc_id a partir do count real do ChromaDB
        # para evitar colisão de IDs após reinicializações
        if self.client:
            try:
                self.doc_id = self.collection.count()
                logger.info(f"VectorMemory doc_id inicializado em {self.doc_id} (documentos existentes)")
            except Exception:
                self.doc_id = 0
        else:
            self.doc_id = 0
        self._lock = threading.Lock()

    def store(self, context: str, metadata: dict = None):
        if self.client:
            # TITAN-003 FIX: Timeout de 5s no lock para evitar deadlock permanente
            acquired = self._lock.acquire(timeout=5.0)
            if not acquired:
                logger.error("TITAN-003: ChromaDB lock timeout (5s) — gravação descartada para evitar deadlock.")
                return
            try:
                self.doc_id += 1
                doc_id = self.doc_id
                # BUG-H01 FIX: collection.add() agora DENTRO do lock (antes estava fora, race condition)
                meta = metadata or {}
                meta = {k: str(v) for k, v in meta.items()}
                self.collection.add(
                    documents=[context],
                    metadatas=[meta],
                    ids=[f"doc_{doc_id}"]
                )
                logger.info(f"Contexto armazenado no ChromaDB [ID doc_{doc_id}]")
            except Exception as e:
                logger.error(f"Erro ao gravar no ChromaDB: {e}")
            finally:
                self._lock.release()
        else:
            self.knowledge_base.append(context)

    def retrieve(self, query: str, n_results: int = 5) -> List[str]:
        if self.client:
            try:
                results = self.collection.query(
                    query_texts=[query],
                    n_results=n_results
                )
                if results['documents'] and len(results['documents']) > 0:
                    return results['documents'][0]
            except Exception as e:
                logger.error(f"Erro ao buscar no VectorMemory: {e}")
        
        return []


class StateMemory:
    """
    Memória de curto prazo (Episódica) e Telemetria em Banco Relacional (SQLite).
    
    TITAN-002 FIX: Usa conexão persistente + asyncio.to_thread para não
    bloquear o event loop. Antes abria/fechava conexão a cada chamada (~40x/min).
    """
    def __init__(self, db_path: str = "./memory_data/telemetry.db"):
        self.db_path = db_path
        self.state: Dict[str, Any] = {}
        self._conn = None
        self._lock = threading.Lock()
        self._init_db()

    def _init_db(self):
        try:
            os.makedirs(os.path.dirname(self.db_path) or ".", exist_ok=True)
            self._conn = sqlite3.connect(self.db_path, check_same_thread=False, timeout=30.0)
            cursor = self._conn.cursor()
            cursor.execute('PRAGMA journal_mode=WAL;')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS telemetry (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    asset TEXT,
                    signal TEXT,
                    confidence REAL,
                    status TEXT,
                    raw_data TEXT
                )
            ''')
            self._conn.commit()
            logger.info(f"StateMemory (SQLite) inicializado em WAL mode em {self.db_path}")
        except Exception as e:
            logger.error(f"Erro ao inicializar DB Relacional: {e}")

    def log_execution(self, asset: str, signal: str, confidence: float, status: str, raw_data: dict):
        """
        TITAN-002 FIX: Usa conexão persistente com lock em vez de abrir/fechar
        a cada chamada. Não bloqueia o event loop.
        """
        try:
            with self._lock:
                cursor = self._conn.cursor()
                cursor.execute('''
                    INSERT INTO telemetry (asset, signal, confidence, status, raw_data)
                    VALUES (?, ?, ?, ?, ?)
                ''', (asset, signal, confidence, status, json.dumps(raw_data)))
                self._conn.commit()
            logger.info(f"Execução registrada no SQLite: {asset} [{signal}]")
        except Exception as e:
            logger.error(f"Erro ao salvar telemetria: {e}")

    def update(self, key: str, value: Any):
        self.state[key] = value

    def get(self, key: str) -> Any:
        return self.state.get(key)

    def close(self):
        """Fecha a conexão persistente (chamado no shutdown graceful)."""
        if self._conn:
            self._conn.close()
            logger.info("StateMemory (SQLite) conexão fechada.")
