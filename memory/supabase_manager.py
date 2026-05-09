import os
import logging
import uuid
import json
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger("SupabaseManager")

class SupabaseManager:
    """
    Integração Institucional com Banco de Dados Supabase (PostgreSQL na nuvem).
    Adaptado para o Schema V8.4 (Nexus Zenith) - Pipeline Log e Trade Journal.
    """
    def __init__(self):
        self.url = os.environ.get("SUPABASE_URL")
        self.key = os.environ.get("SUPABASE_KEY")
        self.client: Client = None
        
        if self.url and self.key and not self.key.endswith("(insira_a_sua_service_role_key_aqui)"):
            try:
                self.client = create_client(self.url, self.key)
                logger.info("✅ Conexão com Supabase Cloud estabelecida (Nexus Zenith V8.4 Schema).")
            except Exception as e:
                logger.error(f"❌ Erro ao conectar com Supabase: {e}")
        else:
            logger.warning("⚠️ SUPABASE_URL ou SUPABASE_KEY não configurados/inválidos no .env. Ignorando sincronização na nuvem.")

    def log_pipeline_execution(self, asset: str, signal: str, confidence: float, status: str, raw_data: dict):
        """ Registra TODO O FLUXO DE ORDEM na tabela pipeline_log (V8.0) """
        if not self.client:
            return
            
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
            
            data, count = self.client.table('pipeline_log').insert({
                "pipeline_id": pipeline_id,
                "session_id": "nexus_singularity_v16.1",
                "ticker": asset,
                "action": signal if signal in ['BUY', 'SELL'] else 'BUY', # Evita erro no Check
                "approved": approved,
                "rejection_stage": rejection_stage,
                "rejection_reason": rejection_reason,
                "committee_score": confidence,
                "mc_grade": mc_grade,
                "pattern": raw_data.get("fvg_type", "UNKNOWN"),
                "quality_score": quality_score,
                "stages_json": raw_data, # Salva o trace completo
                "version": "16.1.0"
            }).execute()
            
            logger.info(f"☁️ Pipeline Log (Supabase) OK: {asset} - {status}")
            
            # Se foi executado, registra no trade_journal também
            if "EXECUTED" in status:
                self.log_trade_journal(pipeline_id, asset, signal, confidence, mc_grade, raw_data)
                
        except Exception as e:
            logger.error(f"❌ Falha no Pipeline Log (Supabase): {e}")

    def log_trade_journal(self, pipeline_id: str, asset: str, signal: str, confidence: float, mc_grade: str, raw_data: dict):
        """ Registra apenas as operações FÍSICAS EXECUTADAS no trade_journal (V8.4) """
        if not self.client:
            return
            
        try:
            journal_id = str(uuid.uuid4())
            
            data, count = self.client.table('trade_journal').insert({
                "journal_id": journal_id,
                "session_id": "nexus_singularity_v16.1",
                "ticker": asset,
                "action": signal if signal in ['BUY', 'SELL'] else 'BUY',
                "pattern": raw_data.get("fvg_type", "UNKNOWN"),
                "kill_zone": "NY_OPEN", # Simulado do Chronos
                "committee_score": confidence,
                "mc_grade": mc_grade,
                "pipeline_id": pipeline_id,
                # Colunas V8.4 Quality
                "quality_score": raw_data.get("quality_score", 8.5),
                "squeeze_release": raw_data.get("squeeze_release", False),
                "kill_zone_type": "NY_OPEN"
            }).execute()
            
            logger.info(f"🏆 Trade Journal (Supabase) Salvo: {asset} - {signal}")
        except Exception as e:
            logger.error(f"❌ Falha no Trade Journal (Supabase): {e}")
