from core.base import BaseSkill
import asyncio
import os
import logging

logger = logging.getLogger("GeminiInference")


class GeminiInferenceSkill(BaseSkill):
    """
    Habilidade Generativa Cognitiva (LLM).
    
    V16.2: Possui dois modos:
    - REAL: Usa API do Google Gemini (requer GEMINI_API_KEY no .env)
    - HEURISTIC: Análise baseada em keywords do contexto (sem LLM externo)
    
    O modo é selecionado automaticamente com base na disponibilidade da chave.
    """
    def __init__(self):
        super().__init__(name="GeminiInference")
        self._api_key = os.getenv("GEMINI_API_KEY", "")
        self._mode = "GEMINI_API" if self._api_key else "HEURISTIC"
        logger.info(f"GeminiInference inicializado em modo: {self._mode}")

    async def execute(self, prompt_context: str = "", **kwargs) -> dict:
        self.logger.info(f"Processando contexto cognitivo ({self._mode}): {prompt_context[:60]}...")
        
        if self._mode == "GEMINI_API":
            return await self._execute_gemini_api(prompt_context)
        else:
            return self._execute_heuristic(prompt_context)

    async def _execute_gemini_api(self, prompt_context: str) -> dict:
        """Execução real via Google Gemini API (gemini-2.0-flash)."""
        try:
            import google.generativeai as genai
            genai.configure(api_key=self._api_key)
            
            model = genai.GenerativeModel('gemini-2.0-flash')
            
            system_prompt = (
                "Você é um analista quantitativo institucional especializado em Micro E-mini Nasdaq (MNQ) "
                "e Micro Gold (MGC). Analise o contexto de mercado abaixo e forneça uma decisão cognitiva "
                "em formato conciso (máximo 2 frases). Avalie o risco de 0.0 a 1.0 e a confiança de 0.0 a 1.0. "
                "Responda APENAS no formato: DECISAO: <texto> | RISCO: <float> | CONFIANCA: <float>"
            )
            
            response = await asyncio.to_thread(
                model.generate_content,
                f"{system_prompt}\n\nCONTEXTO: {prompt_context}"
            )
            
            text = response.text.strip()
            self.logger.info(f"[GEMINI API] Resposta: {text[:100]}...")
            
            # Parse da resposta estruturada
            decision = text
            risk_score = 0.30
            confidence = 0.85
            
            if "DECISAO:" in text and "RISCO:" in text and "CONFIANCA:" in text:
                parts = text.split("|")
                for part in parts:
                    part = part.strip()
                    if part.startswith("DECISAO:"):
                        decision = part.replace("DECISAO:", "").strip()
                    elif part.startswith("RISCO:"):
                        try:
                            risk_score = float(part.replace("RISCO:", "").strip())
                        except ValueError:
                            pass
                    elif part.startswith("CONFIANCA:"):
                        try:
                            confidence = float(part.replace("CONFIANCA:", "").strip())
                        except ValueError:
                            pass
            
            return {
                "cognitive_decision": decision,
                "risk_score": min(max(risk_score, 0.0), 1.0),
                "ai_confidence": min(max(confidence, 0.0), 1.0),
                "inference_mode": "GEMINI_API"
            }
            
        except Exception as e:
            self.logger.error(f"[GEMINI API] Falha: {e}. Fallback para heurística.")
            return self._execute_heuristic(prompt_context)

    def _execute_heuristic(self, prompt_context: str) -> dict:
        """
        Análise heurística baseada em keywords do contexto.
        HONESTAMENTE ROTULADA como heurística — não é NLP/LLM.
        """
        prompt_lower = prompt_context.lower()
        
        confidence = 0.85
        risk_score = 0.30
        decision_text = "Mercado apresenta condições moderadas."
        
        # Análise SMC & FVG
        if "fvg: true" in prompt_lower or "fvg_detected: true" in prompt_lower:
            confidence += 0.05
            decision_text = "Desbalanceamento (FVG) detectado, validando estrutura institucional."
        elif "smc bias: bullish" in prompt_lower:
            decision_text = "Viés institucional de alta claro. Procurar falhas de Swing Low."
            confidence += 0.03
        
        # Análise Macro (News)
        if "macro context: shock" in prompt_lower or "uncertain_shock" in prompt_lower:
            risk_score += 0.50
            confidence -= 0.20
            decision_text += " ALERTA MACRO: Notícia de alto impacto em andamento."
        elif "macro context: risk_on" in prompt_lower or "risk-on" in prompt_lower:
            risk_score -= 0.10
            confidence += 0.05
            decision_text += " Sentimento macro Risk-On suporta a entrada."
            
        # Análise de Exaustão (RSI)
        if "rsi:" in prompt_lower:
            try:
                rsi_str = prompt_lower.split("rsi:")[1].split("|")[0].strip()
                if rsi_str != "none":
                    rsi_val = float(rsi_str)
                    if rsi_val > 70:
                        decision_text += " RSI indica sobrecompra (risco de pullback)."
                        risk_score += 0.20
                    elif rsi_val < 30:
                        decision_text += " RSI indica exaustão vendedora (sobrevenda)."
                        risk_score += 0.20
            except (ValueError, IndexError):
                pass
                
        # RAG Feedback Loop (Memória Passada)
        if "memória passada:" in prompt_lower:
            try:
                mem_text = prompt_lower.split("memória passada:")[1]
                if "rejected" in mem_text:
                    risk_score += 0.40
                    confidence -= 0.15
                    decision_text += " [RL] Padrão similar foi REJEITADO no passado."
                elif "executed" in mem_text:
                    risk_score -= 0.15
                    confidence += 0.10
                    decision_text += " [RL] Padrão similar operou com sucesso no passado."
            except IndexError:
                pass

        return {
            "cognitive_decision": decision_text.strip(),
            "risk_score": min(max(risk_score, 0.0), 1.0),
            "ai_confidence": min(max(confidence, 0.0), 1.0),
            "inference_mode": "HEURISTIC"
        }
