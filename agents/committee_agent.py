from core.base import BaseAgent
from core.engine import Message
from config.settings import settings
from skills.temporal_skills import TemporalChronosSkill
from skills.rl_feedback_skills import ReinforcementLearningSkill

class CommitteeAgent(BaseAgent):
    """
    Tribunal de Decisão Multi-agente.
    Bate o martelo final avaliando todas as 4 Cadeiras, 
    incluindo a validação de Kill Zone (Temporal) e o RL Feedback.
    """
    def __init__(self):
        super().__init__(name="Committee-Council", role="Consenso e Orquestrador Final")
        self.temporal_skill = TemporalChronosSkill()
        self.rl_skill = ReinforcementLearningSkill()

    async def initialize(self):
        await super().initialize()
        self.bus.subscribe("action_approved", self)

    async def handle_message(self, message: Message):
        insight = message.payload
        self.logger.info(f"Sinal Institucional Recebido para {insight.get('asset')}. Consolidando execução...")
        
        # 1. Checagem da Cadeira Temporal (Kill Zones)
        temporal_eval = await self.temporal_skill.execute(insight)
        
        if not temporal_eval["in_kill_zone"]:
            # Corta a confiança se operar fora do horário
            insight["confidence"] -= temporal_eval["confidence_penalty"]
            self.logger.warning(f"Atenção: Ativo {insight.get('asset')} avaliado fora da Kill Zone ({temporal_eval['ny_time']} NY). Confiança reduzida para {insight.get('confidence'):.2f}")
            
            # Se a confiança cair muito, o comitê derruba o trade
            if insight["confidence"] < 0.5:
                insight["status"] = "REJECTED_BY_COMMITTEE"
                self.logger.error("Comitê VETOU a operação: Fora de Horário (Kill Zone) e sem Edge suficiente.")
                await self.bus.publish(Message(sender=self.name, topic="action_rejected", payload=insight))
                return

        # 2. Feedback Loop RL (Ajuste Histórico Forense)
        rl_eval = await self.rl_skill.execute(insight)
        old_confidence = insight["confidence"]
        insight["confidence"] *= rl_eval["weight_multiplier"]
        
        if rl_eval["weight_multiplier"] < 1.0:
            self.logger.info(f"RL Penalty aplicado: Convicção caiu de {old_confidence:.2f} para {insight['confidence']:.2f} devido ao overtrading ({rl_eval['historical_trades']} trades passados).")

        # Verifica se após o RL Penalty a confiança ainda é suficiente
        if insight["confidence"] < settings.ORACLE_CONFIDENCE_THRESHOLD:
            insight["status"] = "REJECTED_BY_COMMITTEE"
            self.logger.error("Comitê VETOU a operação: RL Feedback reduziu a convicção abaixo do limite seguro.")
            await self.bus.publish(Message(sender=self.name, topic="action_rejected", payload=insight))
            return

        # 3. Extrai e consolida L2 Imbalance e Votos (SMC, Macro, Tape, Risk)
        qs = int(insight.get("confidence", 0.0) * 100)
        
        # O TapeReader pode ter adicionado "tape_bias" no insight
        tape_bias = insight.get("tape_bias", "NEUTRAL")
        is_long = insight.get("signal") == "LONG"
        
        # Mapeia viés do tape para porcentagens exatas de L2 Bid/Ask e Delta
        if tape_bias == "BULLISH_ABSORPTION":
            bid_pct, ask_pct, l2_delta = 72, 28, 450
        elif tape_bias == "BEARISH_ABSORPTION":
            bid_pct, ask_pct, l2_delta = 25, 75, -480
        else:
            # Fluxo misto
            bid_pct = 55 if is_long else 45
            ask_pct = 100 - bid_pct
            l2_delta = 120 if is_long else -120
            
        # Votos do Comitê de Agentes: [SMC, Macro, Tape, Risk]
        # Aqui o conselho aprova porque chegou até aqui, mas o peso varia.
        fvg_ok = insight.get("fvg_detected", False)
        votes = [
            True if fvg_ok or qs > 40 else False,  # SMC (SmcTechnicalSkill)
            True,                                  # Macro (Sempre True se não for veto global)
            True if (is_long and bid_pct > 50) or (not is_long and ask_pct > 50) else False, # TapeReader
            True if qs > 60 else False             # QuantumRisk (RlFeedback + Oracle)
        ]

        insight["qs"] = qs
        insight["bid_pct"] = bid_pct
        insight["ask_pct"] = ask_pct
        insight["l2_delta"] = l2_delta
        insight["kill_zone_status"] = temporal_eval["active_zone"]
        insight["committee_votes"] = votes

        # 4. O Committee adiciona os parâmetros finais de risk/reward institucionais
        verdict = {
            "status": "EXECUTE",
            "asset": insight.get("asset"),
            "signal": insight.get("signal"),
            "confidence": insight.get("confidence"),
            "target_take_profit": settings.RISK_REWARD_RATIO,
            "max_drawdown": settings.MAX_DRAWDOWN_PERCENT,
            "kill_zone_status": temporal_eval["active_zone"],
            "rl_multiplier": rl_eval["weight_multiplier"],
            # Tudo vai para raw_data no ForensicAgent:
            "raw_analysis": insight,
            "qs": qs,
            "bid_pct": bid_pct,
            "ask_pct": ask_pct,
            "l2_delta": l2_delta,
            "committee_votes": votes
        }
        
        self.logger.info(f"[VEREDICTO FINAL APROVADO] Ordem para {insight.get('asset')} -> SINAL: {insight.get('signal')} | Zone: {temporal_eval['active_zone']} | RL: {rl_eval['weight_multiplier']}x")
        
        # Dispara para o Forense e para a camada de execução real (boleta)
        await self.bus.publish(Message(sender=self.name, topic="execute_action", payload=verdict))
