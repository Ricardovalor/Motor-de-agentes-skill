from core.base import BaseSkill
from typing import Dict, Any
import logging
import sqlite3
import os
import json
from datetime import datetime, timezone

logger = logging.getLogger("ApexCompliance")

# Caminhos possíveis para o rules.json (fonte única de verdade)
_RULES_SEARCH_PATHS = [
    os.path.join(os.path.dirname(__file__), "..", "rules.json"),  # Dentro do Motor (prioridade)
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "extratredey", "rules.json"),  # Dev local
    # GAP-M04 FIX: Path cross-platform em vez de hardcoded Windows
    os.path.join(os.path.expanduser("~"), "extratredey", "rules.json"),
]


def _load_apex_rules() -> dict:
    """Carrega rules.json como fonte única de verdade. Fallback para defaults Apex 50K."""
    for path in _RULES_SEARCH_PATHS:
        try:
            abs_path = os.path.abspath(path)
            if os.path.exists(abs_path):
                with open(abs_path, "r", encoding="utf-8") as f:
                    rules = json.load(f)
                logger.info(f"✅ Rules.json carregado de: {abs_path} (v{rules.get('_version', '?')})")
                return rules
        except Exception as e:
            logger.debug(f"Tentativa de rules.json em {path} falhou: {e}")
    
    logger.warning("⚠️ rules.json não encontrado. Usando defaults hardcoded Apex 50K.")
    return {}


class ApexComplianceSkill(BaseSkill):
    """
    Skill responsável pela Cadeira Guardian (Risco).
    Garante compliance estrito com as regras da Apex Trader Funding (EOD 50k).
    Monitora limite de perda diária (DLL) e Drawdown (Trailing).
    
    V16.2.1: Carrega parâmetros do rules.json + detecção automática de fase EVAL/PA
    para aplicar limites corretos de contratos (6 mini EVAL vs 4 mini PA).
    """
    def __init__(self, db_path: str = "./memory_data/telemetry.db"):
        super().__init__(name="ApexComplianceSkill", description="Avaliação de Risco APEX EOD e Limites Diários.")
        self.db_path = db_path
        
        # Carrega regras do rules.json (single source of truth)
        rules = _load_apex_rules()
        self.daily_loss_limit = -abs(rules.get("max_daily_loss", 1000))    # $1,000 DLL
        self.max_drawdown = -abs(rules.get("max_trailing_drawdown", 2000)) # $2,000 EOD Trailing
        self.max_trades_per_day = rules.get("max_daily_trades", 3)         # 3 trades/dia
        self.account_size = rules.get("account_size", 50000)
        self.mandatory_stop_loss = rules.get("mandatory_stop_loss", True)
        self._rules_version = rules.get("_version", "fallback")
        
        # V10.1: Detecção de Fase (EVAL vs PA) e Modelo (EOD vs Legacy)
        self.phase = os.environ.get("APEX_PHASE", rules.get("phase", "EVALUATION")).upper()
        self.model_type = os.environ.get("APEX_MODEL", rules.get("model_type", "EOD")).upper()
        
        if self.phase == "PA":
            if self.model_type == "LEGACY":
                # Legacy PA: 30% consistency, fixed contracts, real-time trailing drawdown
                legacy = rules.get("legacy_pa_rules", {})
                self.consistency_rule_pct = legacy.get("consistency_rule_percent", 30)
                self.max_contracts_mini = legacy.get("max_contracts_mini_50k", 10)
                self.max_drawdown = -abs(legacy.get("max_drawdown", 2500))
                self.scaling_tiers = None  # Legacy has NO scaling tiers
                logger.info(f"⚖️ Fase PA LEGACY: {self.max_contracts_mini} contratos fixos, consistência {self.consistency_rule_pct}%, drawdown TRAILING REAL-TIME")
            else:
                # EOD PA: 50% consistency, scaling tiers, EOD trailing drawdown
                pa_rules = rules.get("pa_rules", {})
                self.consistency_rule_pct = pa_rules.get("consistency_rule_percent", 50)
                # PA 50K Scaling Tiers (Apex Official TOS May 2026)
                self.scaling_tiers = {
                    1: {"profit_range": (0, 1499), "max_contracts": 2, "dll": 1000},
                    2: {"profit_range": (1500, 2999), "max_contracts": 3, "dll": 1000},
                    3: {"profit_range": (3000, 5999), "max_contracts": 4, "dll": 2000},
                    4: {"profit_range": (6000, float('inf')), "max_contracts": 4, "dll": 3000},
                }
                self.max_contracts_mini = 2  # Start at Tier 1 (conservative)
                logger.info(f"⚖️ Fase PA EOD: Tier Scaling ATIVO, consistência {self.consistency_rule_pct}%")
        else:
            eval_rules = rules.get("evaluation_rules", {})
            self.max_contracts_mini = eval_rules.get("max_contracts_mini", 6)
            self.consistency_rule_pct = 0  # Não se aplica na EVAL
            self.scaling_tiers = None
            logger.info(f"📋 Fase EVALUATION: max {self.max_contracts_mini} mini-contratos")

    async def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        V16.2: Calcula risco usando Guardian singleton (via HTTP) como fonte primária.
        Fallback para SQLite local se o Extratredey engine não estiver online.
        """
        asset = params.get("asset", "UNKNOWN")
        
        # Prioridade 1: Ler do Guardian Singleton via HTTP (Extratredey :8000)
        trades_hoje = 0
        pnl_source = "UNKNOWN"
        try:
            import httpx
            async with httpx.AsyncClient(timeout=2.0) as client:
                resp = await client.get("http://127.0.0.1:8000/api/pnl")
                if resp.status_code == 200:
                    data = resp.json()
                    trades_hoje = data.get("trades_today", 0)
                    pnl_source = "GUARDIAN_SINGLETON"
                    logger.info(f"[Compliance] Trade count via Guardian singleton: {trades_hoje}")
        except Exception as e:
            logger.debug(f"Guardian HTTP unavailable: {e}. Tentando SQLite fallback...")
        
        # Prioridade 2: Fallback para SQLite local
        if pnl_source == "UNKNOWN":
            try:
                if os.path.exists(self.db_path):
                    from datetime import timedelta
                    
                    # Resolvedor de Timezone Híbrido e Resiliente (Self-Healing)
                    ny_tz = None
                    try:
                        from zoneinfo import ZoneInfo
                        ny_tz = ZoneInfo("America/New_York")
                    except ImportError:
                        try:
                            import pytz
                            ny_tz = pytz.timezone("America/New_York")
                        except ImportError:
                            # Fallback nativo: calcula se está no Horário de Verão dos EUA (EDT = UTC-4, caso contrário EST = UTC-5)
                            # O horário de verão dos EUA inicia no 2º domingo de março e termina no 1º domingo de novembro
                            from datetime import timezone as datetime_timezone
                            now_utc = datetime.now(timezone.utc)
                            # Aproximação robusta: Março a Novembro como EDT (UTC-4), outros meses como EST (UTC-5)
                            if 3 <= now_utc.month <= 11:
                                ny_tz = datetime_timezone(timedelta(hours=-4))
                                logger.debug("TimeZone Fallback: Usando offset EDT (UTC-4)")
                            else:
                                ny_tz = datetime_timezone(timedelta(hours=-5))
                                logger.debug("TimeZone Fallback: Usando offset EST (UTC-5)")
                    
                    now_ny = datetime.now(ny_tz)
                    
                    # Se a hora atual de NY for menor que 17:00, a sessão iniciou ontem às 17:00 NY
                    if hasattr(now_ny, "hour") and now_ny.hour < 17:
                        session_start = now_ny.replace(hour=17, minute=0, second=0, microsecond=0) - timedelta(days=1)
                    elif hasattr(now_ny, "hour"):
                        session_start = now_ny.replace(hour=17, minute=0, second=0, microsecond=0)
                    else:
                        # Para objetos timezone nativos sem datetime enriquecido completo (offset fixo de fallback)
                        # datetime.now(tz) retorna um datetime normal
                        if now_ny.hour < 17:
                            session_start = now_ny.replace(hour=17, minute=0, second=0, microsecond=0) - timedelta(days=1)
                        else:
                            session_start = now_ny.replace(hour=17, minute=0, second=0, microsecond=0)
                        
                    # Converte o início da sessão de NY para UTC (formato usado pelo SQLite CURRENT_TIMESTAMP)
                    session_start_utc = session_start.astimezone(timezone.utc)
                    session_start_str = session_start_utc.strftime('%Y-%m-%d %H:%M:%S')
                    
                    # Conexão com timeout robusto para evitar locks
                    conn = sqlite3.connect(self.db_path, timeout=30.0)
                    cursor = conn.cursor()
                    cursor.execute(
                        "SELECT COUNT(*) FROM telemetry WHERE timestamp >= ? AND status IN ('APPROVED_BY_COMMITTEE', 'EXECUTED_IN_BROKER')",
                        (session_start_str,)
                    )
                    trades_hoje = cursor.fetchone()[0]
                    conn.close()
                    pnl_source = "SQLITE_LOCAL"
                    logger.info(f"[Compliance] Sessão Apex iniciada em (NY): {session_start.strftime('%Y-%m-%d %H:%M:%S')} | UTC: {session_start_str} | Trades detectados hoje: {trades_hoje}")
            except Exception as e:
                logger.warning(f"Erro ao ler telemetry.db para Compliance APEX: {e}")

        # Avaliação de Risco
        is_compliant = True
        rejection_reason = ""

        # Trava 1: Máximo de Trades
        if trades_hoje >= self.max_trades_per_day:
            is_compliant = False
            rejection_reason = f"Max Trades Diário Atingido ({self.max_trades_per_day})"
            
        # BUG-H04 FIX: Lê PnL real sem reinstanciar BrokerSyncSkill a cada chamada
        current_daily_pnl = 0.0
        try:
            # Prioridade: live_pnl.json (atualizado pelo BrokerSyncAgent)
            import json as _json
            pnl_path = os.path.join(os.path.dirname(self.db_path), "live_pnl.json")
            if os.path.exists(pnl_path):
                with open(pnl_path, "r") as f:
                    pnl_data = _json.load(f)
                    current_daily_pnl = pnl_data.get("pnl", 0.0)
                    logger.info(f"PnL Real lido de live_pnl.json: ${current_daily_pnl}")
        except Exception as e:
            logger.warning(f"Falha ao ler PnL de live_pnl.json: {e}. Usando $0.0 (fail-safe).")
            
        if current_daily_pnl <= self.daily_loss_limit:
            is_compliant = False
            rejection_reason = f"DLL Atingido (Perda Real >= $1000: ${current_daily_pnl})"

        if not is_compliant:
            logger.error(f"⚠️ APEX GUARDIAN BLOQUEOU A OPERAÇÃO: {rejection_reason}")
        else:
            logger.info("Apex Guardian: CLEAR para operar.")

        return {
            "status": "success",
            "is_compliant": is_compliant,
            "rejection_reason": rejection_reason,
            "trades_executed_today": trades_hoje
        }
