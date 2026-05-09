from core.base import BaseSkill
import asyncio

class WebSearchSkill(BaseSkill):
    """
    Habilidade de Busca na Web.
    Pode ser acoplada ao DataAgent ou OracleAgent para trazer informações em tempo real.
    """
    def __init__(self):
        super().__init__(name="WebSearch")

    async def execute(self, query: str) -> dict:
        self.logger.info(f"Executando busca web para: {query}")
        await asyncio.sleep(0.5) # Simulando I/O
        return {"query": query, "results": ["Insight tecnológico 1", "Dado profundo 2"]}

class MathExecutionSkill(BaseSkill):
    """
    Habilidade de Computação Matemática Avançada.
    Substitui a necessidade de o LLM calcular na unha.
    """
    def __init__(self):
        super().__init__(name="MathExecution")

    async def execute(self, expression: str) -> float:
        self.logger.info(f"Calculando expressão complexa: {expression}")
        try:
            # Em um sistema real rodaríamos via ast.literal_eval ou engine segura
            result = eval(expression)
            return float(result)
        except Exception as e:
            self.logger.error(f"Erro na matemática: {e}")
            return 0.0
