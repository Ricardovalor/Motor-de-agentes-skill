import asyncio
import logging
import json
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import uvicorn
from core.engine import NexusEngine, Message
from memory.memory_manager import VectorMemory, StateMemory

# Importação dos Agentes de Elite
from agents.data_agent import DataAgent
from agents.oracle_agent import OracleAgent
from agents.guardian_agent import GuardianAgent
from agents.committee_agent import CommitteeAgent
from agents.forensic_agent import ForensicAgent
from agents.execution_agent import BrokerExecutionAgent
from agents.temporal_agent import TemporalAgent
from agents.quantum_risk_agent import QuantumRiskAgent
from agents.devops_agent import DevOpsWatchdogAgent
from agents.macro_sentiment_agent import MacroSentimentAgent
from agents.tape_reader_agent import TapeReaderAgent
from agents.broker_sync_agent import BrokerSyncAgent  # BUG-C01 FIX: Agente que estava órfão
from skills.killswitch_skills import SystemKillSwitchSkill
from skills.macro_news_skills import MacroNewsSkill
from skills.order_flow_skills import LiquidityHeatmapSkill
from skills.macro_calendar_skill import MacroCalendarSkill
from skills.tradovate_api_skill import TradovateAPISkill

# Importação de Skills
from skills.market_skills import MarketDataFetchSkill, StrategyAnalysisSkill
from skills.advanced_skills import FractalPatternSkill, CrossAssetCorrelationSkill
from skills.ai_skills import GeminiInferenceSkill
from skills.execution_skills import TradingViewTradovateMCPExecutionSkill
from skills.smc_technical_skills import SmcTechnicalSkill

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(name)-20s | %(levelname)-7s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# =========================================================================
# BUG-C02 FIX: FastAPI Webhook Server (antes não existia — sinais do
# TradingView e test_injection.py caíam no vácuo)
# =========================================================================
webhook_app = FastAPI(title="Nexus Zenith Webhook Receiver", version="16.2.0")

# Referência global ao engine para o webhook injetar sinais
_engine_ref: NexusEngine = None


@webhook_app.post("/webhook/tradingview")
async def receive_tradingview_signal(request: Request):
    """
    Endpoint que recebe alertas do TradingView (Pine Script) e injeta
    diretamente no Event Bus do Motor Nexus.
    """
    try:
        payload = await request.json()
        asset = payload.get("asset", "MNQ")
        signal = payload.get("signal", "NEUTRAL")
        price = payload.get("price", 0.0)

        logging.info(f"[WEBHOOK] Sinal recebido do TradingView: {asset} | {signal} @ {price}")

        if _engine_ref and _engine_ref.bus:
            await _engine_ref.bus.publish(Message(
                sender="Webhook-TradingView",
                topic="data_request",
                payload=payload
            ))
            return JSONResponse(
                content={"status": "OK", "message": f"Sinal {signal} para {asset} injetado no pipeline."},
                status_code=200
            )
        else:
            return JSONResponse(
                content={"status": "ERROR", "message": "Motor Nexus não inicializado."},
                status_code=503
            )
    except Exception as e:
        logging.error(f"[WEBHOOK] Erro ao processar sinal: {e}")
        return JSONResponse(
            content={"status": "ERROR", "message": str(e)},
            status_code=500
        )


@webhook_app.get("/health")
async def health_check():
    """Health check para Docker/Load Balancer."""
    agent_count = len(_engine_ref.agents) if _engine_ref else 0
    return {
        "status": "ONLINE",
        "engine_version": "V16.2-TITAN",
        "agents_registered": agent_count,
        "engine_running": _engine_ref.running if _engine_ref else False,
    }


async def run_webhook_server():
    """Inicia o servidor FastAPI em background (não bloqueia o Event Loop)."""
    config = uvicorn.Config(webhook_app, host="0.0.0.0", port=8005, log_level="warning")
    server = uvicorn.Server(config)
    await server.serve()


async def high_frequency_stream_simulator(engine: NexusEngine):
    """
    Simulador de Alta Frequência (Event Stream).
    Substitui o Cron lento por um firehose de WebSockets.
    """
    await asyncio.sleep(2)
    assets = ["MNQ", "MGC", "MES", "M6E"]
    logging.info("[STREAM] Abrindo canais de WebSocket HFT para ativos institucionais...")
    
    while True:
        for asset in assets:
            # Emite eventos em altíssima velocidade
            await engine.bus.publish(Message(sender="WSS-Stream", topic="data_request", payload={"asset": asset}))
            await asyncio.sleep(1.5) # Ritmo institucional de submissão

async def main():
    global _engine_ref

    logging.info("==================================================================")
    logging.info("🌌 NEXUS ZENITH ENGINE V16.2: TITAN HARDENED")
    logging.info("==================================================================")

    engine = NexusEngine()
    _engine_ref = engine  # Expõe para o webhook

    # 1. Instancia o Enxame de Agentes (Swarm)
    data_ops = DataAgent()
    macro = MacroSentimentAgent()
    temporal = TemporalAgent()
    oracle = OracleAgent()
    devops = DevOpsWatchdogAgent()
    tape_reader = TapeReaderAgent()
    quantum = QuantumRiskAgent()
    guardian = GuardianAgent()
    committee = CommitteeAgent()
    forensic = ForensicAgent()
    broker = BrokerExecutionAgent()
    broker_sync = BrokerSyncAgent()  # BUG-C01 FIX: Agente de PnL/Trailing agora ativo!

    # TITAN-004 FIX: Singleton MemoryBank — Oracle e Forensic compartilham
    # a mesma instância VectorMemory (evita lock conflict no ChromaDB)
    from config.settings import settings
    shared_vector_db = VectorMemory(persist_dir=settings.CHROMA_DB_PATH)
    shared_state_db = StateMemory(db_path="memory_data/telemetry.db")  # TITAN-013: Path unificado
    oracle.vector_db = shared_vector_db
    forensic.vector_db = shared_vector_db
    forensic.sql_db = shared_state_db
    logging.info("[TITAN-004] MemoryBank singleton injetado: Oracle e Forensic compartilham VectorMemory.")

    # 2. Instancia a Forja de Skills
    fetch_skill = MarketDataFetchSkill()
    strategy_skill = StrategyAnalysisSkill()
    fractal_skill = FractalPatternSkill()
    correlation_skill = CrossAssetCorrelationSkill()
    gemini_skill = GeminiInferenceSkill()
    execution_mcp = TradingViewTradovateMCPExecutionSkill()
    smc_skill = SmcTechnicalSkill()
    killswitch_skill = SystemKillSwitchSkill()
    macro_news_skill = MacroNewsSkill()
    order_flow_skill = LiquidityHeatmapSkill()
    macro_calendar_skill = MacroCalendarSkill()
    tradovate_api_skill = TradovateAPISkill(mode="demo")  # Fase 2: demo first

    # 3. Equipa os Agentes com suas Armas (Skills)
    data_ops.equip_skill(fetch_skill)
    macro.equip_skill(macro_news_skill)
    macro.equip_skill(macro_calendar_skill)  # Fase 3: Calendar blackout
    temporal.equip_skill(fractal_skill)
    oracle.equip_skill(strategy_skill)
    oracle.equip_skill(smc_skill)
    oracle.equip_skill(gemini_skill)
    devops.equip_skill(killswitch_skill)
    devops.equip_skill(tradovate_api_skill)  # Fase 2: Kill Switch flatten via API
    tape_reader.equip_skill(order_flow_skill)
    quantum.equip_skill(correlation_skill)
    broker.equip_skill(execution_mcp)
    broker.equip_skill(tradovate_api_skill)  # Fase 2: Dual mode execution

    # 4. Acopla o Enxame ao Motor (BUG-C01 FIX: broker_sync agora incluído!)
    for agent in [data_ops, macro, temporal, oracle, devops, tape_reader, quantum, guardian, committee, broker, forensic, broker_sync]:
        engine.register_agent(agent)

    # 5. Entra em Ignição (Assíncrono Multi-thread)
    # BUG-C02 FIX: Agora roda o webhook server junto com o engine
    logging.info("[MAIN] Webhook server disponível em http://0.0.0.0:8005/webhook/tradingview")
    await asyncio.gather(
        engine.start(),
        high_frequency_stream_simulator(engine),
        run_webhook_server(),  # BUG-C02 FIX: Servidor HTTP agora ativo!
    )

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        # TITAN-009 FIX: Graceful shutdown — sinaliza agentes antes de sair
        logging.info("[MAIN] 🔴 Shutdown Mestre ativado. Encerrando agentes...")
        if _engine_ref:
            _engine_ref.stop()
        logging.info("[MAIN] Motor desligado com segurança.")
