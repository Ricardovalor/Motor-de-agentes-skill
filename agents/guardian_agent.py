from core.base import BaseAgent
from core.engine import Message
from config.settings import settings
from skills.compliance_skills import ApexComplianceSkill

class GuardianAgent(BaseAgent):
    """
    O guardião institucional da Apex e Compliance "Zero-Defect".
    """
    def __init__(self):
        super().__init__(name="Guardian-Protocol", role="Validador de Risco Apex")
        self.compliance_skill = ApexComplianceSkill()

    async def initialize(self):
        await super().initialize()
        # Ouve o Risco Quântico
        self.bus.subscribe("quantum_risk_approved", self)

    async def handle_message(self, message: Message):
        insight = message.payload
        confidence = insight.get('confidence', 0)
        confidence_display = f"{confidence:.2f}" if confidence is not None else "N/A"
        self.logger.info(f"Validando sinal: {insight.get('signal', 'UNKNOWN')} com convicção de {confidence_display}")
        
        # 1. Filtro Básico do Oracle
        if insight.get("signal") == "NEUTRAL":
            self.logger.info("Compliance REJEITADO: Sinal neutro.")
            await self.bus.publish(Message(sender=self.name, topic="action_rejected", payload=insight))
            return
            
        if confidence < settings.ORACLE_CONFIDENCE_THRESHOLD:
            self.logger.warning(f"Compliance REJEITADO. Convicção abaixo de {settings.ORACLE_CONFIDENCE_THRESHOLD}.")
            await self.bus.publish(Message(sender=self.name, topic="action_rejected", payload=insight))
            return

        # 2. Avaliação de Compliance Strict APEX (Cadeira Guardian Real)
        compliance_result = await self.compliance_skill.execute(insight)
        
        if not compliance_result["is_compliant"]:
            insight["status"] = "REJECTED_BY_GUARDIAN"
            insight["rejection_reason"] = compliance_result["rejection_reason"]
            self.logger.error(f"Compliance REJEITADO pelas regras Apex: {insight['rejection_reason']}")
            await self.bus.publish(Message(sender=self.name, topic="action_rejected", payload=insight))
            return

        # 3. Aprovado
        self.logger.info("Compliance APROVADO. Risco dentro dos limites da Apex.")
        await self.bus.publish(Message(sender=self.name, topic="action_approved", payload=insight))
