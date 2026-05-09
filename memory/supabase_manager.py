import os
import logging
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger("SupabaseManager")

class SupabaseManager:
    """
    Integração Institucional com Banco de Dados Supabase (PostgreSQL na nuvem).
    Usado para telemetria em tempo real, dashboards unificados e automação externa.
    """
    def __init__(self):
        self.url = os.environ.get("SUPABASE_URL")
        self.key = os.environ.get("SUPABASE_KEY")
        self.client: Client = None
        
        if self.url and self.key:
            try:
                self.client = create_client(self.url, self.key)
                logger.info("✅ Conexão com Supabase Cloud estabelecida.")
            except Exception as e:
                logger.error(f"❌ Erro ao conectar com Supabase: {e}")
        else:
            logger.warning("⚠️ SUPABASE_URL ou SUPABASE_KEY não configurados no .env. Ignorando sincronização na nuvem.")

    def log_execution(self, asset: str, signal: str, confidence: float, status: str, raw_data: dict):
        if not self.client:
            return
            
        try:
            # Assumindo que criamos uma tabela 'telemetry' no Supabase
            data, count = self.client.table('telemetry').insert({
                "asset": asset,
                "signal": signal,
                "confidence": confidence,
                "status": status,
                "raw_data": raw_data
            }).execute()
            logger.info(f"☁️ Supabase Cloud Sync OK: {asset} - {status}")
        except Exception as e:
            logger.error(f"❌ Falha no Supabase Cloud Sync: {e}")
