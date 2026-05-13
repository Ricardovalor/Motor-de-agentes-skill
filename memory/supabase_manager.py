import os
import logging
import uuid
import json
import asyncio
from supabase import create_client, Client
from dotenv import load_dotenv
from memory.circuit_breaker import CircuitBreaker

load_dotenv()
logger = logging.getLogger("SupabaseManager")

class SupabaseManager:
    """
    Integração Institucional com Banco de Dados Supabase (PostgreSQL na nuvem).
    Adaptado para o Schema V16.2 (Nexus Zenith) - Pipeline Log e Trade Journal.
    """
    def __init__(self):
        self.url = os.environ.get("SUPABASE_URL")
        self.key = os.environ.get("SUPABASE_KEY")
        self.client: Client = None
        self.circuit_breaker = CircuitBreaker(
            name="supabase", failure_threshold=3, recovery_timeout=30
        )
        
        if self.url and self.key and not self.key.endswith("(insira_a_sua_service_role_key_aqui)"):
            try:
                self.client = create_client(self.url, self.key)
                logger.info("✅ Conexão com Supabase Cloud estabelecida (Nexus Zenith V16.2 TITAN Schema).")
            except Exception as e:
                logger.error(f"❌ Erro ao conectar com Supabase: {e}")
        else:
            logger.warning("⚠️ SUPABASE_URL ou SUPABASE_KEY não configurados/inválidos no .env. Ignorando sincronização na nuvem.")

    def log_pipeline_execution(self, asset: str, signal: str, confidence: float, status: str, raw_data: dict):
        """ Registra TODO O FLUXO DE ORDEM na tabela pipeline_log (V10.0) """
        if not self.client:
            return

        # V10.0: Skip HOLD/NEUTRAL — Supabase constraint only accepts BUY/SELL
        mapped_action = self._map_action(signal)
        if mapped_action not in ("BUY", "SELL"):
            logger.debug(f"Pipeline skip: {asset} action={mapped_action} (not BUY/SELL)")
            return
            
        async def _run():
            try:
                # Extrair valores do raw_data para casar com o schema
                approved = "APPROVED" in status or "EXECUTED" in status
                rejection_stage = None
                rejection_reason = None
                
                if not approved:
                    if "GUARDIAN" in status:
                        rejection_stage = "GUARDIAN_PROTOCOL"
                    elif "WATCHDOG" in status:
                        rejection_stage = "DEVOPS_WATCHDOG"
                    else:
                        rejection_stage = "UNKNOWN_REJECTION"
                    rejection_reason = status
                
                pipeline_id = str(uuid.uuid4())
                
                # Adiciona colunas do V8.4
                quality_score = raw_data.get("quality_score", 0.0)
                mc_grade = "A" if confidence > 0.9 else ("B" if confidence > 0.7 else "C")
                
                # === CIRCUIT BREAKER CHECK ===
                if not self.circuit_breaker.can_execute():
                    logger.warning(f"⚡ CircuitBreaker OPEN — Pipeline Log para {asset} salvo apenas localmente (SQLite)")
                    return
                
                # Executa insert em thread separada para não bloquear Event Loop
                def _insert_pipeline():
                    self.client.table('pipeline_log').insert({
                        "pipeline_id": pipeline_id,
                        "session_id": "nexus_zenith_v16.2",
                        "ticker": asset,
                        "action": mapped_action,
                        "approved": approved,
                        "rejection_stage": rejection_stage,
                        "rejection_reason": rejection_reason,
                        "committee_score": confidence,
                        "mc_grade": mc_grade,
                        "pattern": raw_data.get("fvg_type", "UNKNOWN"),
                        "quality_score": quality_score,
                        "stages_json": raw_data,
                        "version": "10.5.0",
                        # V10.0 fields
                        "micro_trend": raw_data.get("micro_trend", "ALIGNED"),
                        "sweep_confirmed": raw_data.get("sweep_confirmed", False),
                        "vol_regime": raw_data.get("vol_regime", 1.0),
                        "engine_version": "10.5"
                    }).execute()
                
                await asyncio.to_thread(_insert_pipeline)
                self.circuit_breaker.record_success()
                logger.info(f"\u2601\ufe0f Pipeline Log (Supabase) OK: {asset} - {status}")
                
                # Se foi executado, registra no trade_journal também
                if "EXECUTED" in status:
                    await self._log_trade_journal_async(pipeline_id, asset, signal, confidence, mc_grade, raw_data)
                    
            except Exception as e:
                self.circuit_breaker.record_failure()
                logger.error(f"\u274c Falha no Pipeline Log (Supabase): {e} | CB State: {self.circuit_breaker.state}")

        def _on_task_done(task):
            """BUG-C03 FIX: Captura exceções de tasks fire-and-forget."""
            if not task.cancelled() and task.exception():
                logger.error(f"❌ Pipeline Log task falhou silenciosamente: {task.exception()}")

        task = asyncio.create_task(_run())
        task.add_done_callback(_on_task_done)

    async def _log_trade_journal_async(self, pipeline_id: str, asset: str, signal: str, confidence: float, mc_grade: str, raw_data: dict):
        """ Registra apenas as operações FÍSICAS EXECUTADAS no trade_journal (V8.4) """
        if not self.client:
            return
            
        def _insert_journal():
            try:
                journal_id = str(uuid.uuid4())
                
                self.client.table('trade_journal').insert({
                    "journal_id": journal_id,
                    "session_id": "nexus_singularity_v16.2",
                    "ticker": asset,
                    "action": self._map_action(signal),
                    "pattern": raw_data.get("fvg_type", "UNKNOWN"),
                    "kill_zone": raw_data.get("kill_zone_status", "UNKNOWN"),
                    "committee_score": confidence,
                    "mc_grade": mc_grade,
                    "pipeline_id": pipeline_id,
                    "quality_score": raw_data.get("quality_score", 8.5),
                    "squeeze_release": raw_data.get("squeeze_release", False),
                    "kill_zone_type": raw_data.get("kill_zone_status", "UNKNOWN"),
                    # V10.0 fields
                    "micro_trend": raw_data.get("micro_trend", "ALIGNED"),
                    "sweep_confirmed": raw_data.get("sweep_confirmed", False),
                    "vol_regime": raw_data.get("vol_regime", 1.0)
                }).execute()
                
                logger.info(f"\U0001f3c6 Trade Journal (Supabase) Salvo: {asset} - {signal}")
            except Exception as e:
                logger.error(f"\u274c Falha no Trade Journal (Supabase): {e}")

        await asyncio.to_thread(_insert_journal)

    def _map_action(self, signal: str) -> str:
        """Mapeia sinais do Motor para ações do Supabase de forma precisa."""
        mapping = {
            "LONG": "BUY",
            "BUY": "BUY",
            "SHORT": "SELL",
            "SELL": "SELL",
            "NEUTRAL": "HOLD",
            "UNKNOWN": "HOLD"
        }
        return mapping.get(signal, "HOLD")
