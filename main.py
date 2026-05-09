import asyncio
import logging
from core.engine import NexusEngine, Message

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
from skills.killswitch_skills import SystemKillSwitchSkill
from skills.macro_news_skills import MacroNewsSkill
from skills.order_flow_skills import LiquidityHeatmapSkill

# Importação de Skills
from skills.market_skills import MarketDataFetchSkill, StrategyAnalysisSkill
from skills.advanced_skills import FractalPatternSkill, CrossAssetCorrelationSkill
from skills.ai_skills import GeminiInferenceSkill
from skills.execution_skills import BrowserMCPExecutionSkill
from skills.smc_technical_skills import SmcTechnicalSkill

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(name)-20s | %(levelname)-7s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

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
    logging.info("==================================================================")
    logging.info("🌌 NEXUS SINGULARITY ENGINE V15.0: THE 4 CHAIRS NEURAL COMMITTEE")
    logging.info("==================================================================")

    engine = NexusEngine()

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

    # 2. Instancia a Forja de Skills
    fetch_skill = MarketDataFetchSkill()
    strategy_skill = StrategyAnalysisSkill()
    fractal_skill = FractalPatternSkill()
    correlation_skill = CrossAssetCorrelationSkill()
    gemini_skill = GeminiInferenceSkill()
    execution_mcp = BrowserMCPExecutionSkill()
    smc_skill = SmcTechnicalSkill()
    killswitch_skill = SystemKillSwitchSkill()
    macro_news_skill = MacroNewsSkill()
    order_flow_skill = LiquidityHeatmapSkill()

    # 3. Equipa os Agentes com suas Armas (Skills)
    data_ops.equip_skill(fetch_skill)
    macro.equip_skill(macro_news_skill)
    temporal.equip_skill(fractal_skill)
    oracle.equip_skill(strategy_skill)
    oracle.equip_skill(smc_skill)
    oracle.equip_skill(gemini_skill)
    devops.equip_skill(killswitch_skill)
    tape_reader.equip_skill(order_flow_skill)
    quantum.equip_skill(correlation_skill)
    broker.equip_skill(execution_mcp)

    # 4. Acopla o Enxame ao Motor
    for agent in [data_ops, macro, temporal, oracle, devops, tape_reader, quantum, guardian, committee, broker, forensic]:
        engine.register_agent(agent)

    # 5. Entra em Ignição (Assíncrono Multi-thread)
    await asyncio.gather(
        engine.start(),
        high_frequency_stream_simulator(engine)
    )

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("[MAIN] Desligamento Mestre ativado.")
