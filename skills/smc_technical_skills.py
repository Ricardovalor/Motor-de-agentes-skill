import pandas as pd
import numpy as np
from typing import Dict, Any
import logging
from core.base import BaseSkill

logger = logging.getLogger("SmcTechnical")

class SmcTechnicalSkill(BaseSkill):
    """
    Skill responsável pela Cadeira 'Técnico (SMC)' do Comitê Neural.
    Identifica estruturas do Smart Money Concepts como:
    - Fair Value Gaps (FVG)
    - Bias (Tendência baseada em topos e fundos)
    """
    def __init__(self):
        super().__init__(name="SmcTechnicalSkill", description="Detecção de Fluxo Institucional (FVG/ChoCH)")

    async def execute(self, market_data: dict) -> dict:
        df = market_data.get("history")
        asset = market_data.get("asset")
        
        if df is None or df.empty or len(df) < 3:
            logger.warning(f"Dados insuficientes para SMC em {asset}.")
            return {"smc_bias": "NEUTRAL", "fvg_detected": False, "fvg_type": None, "confidence_boost": 0.0}

        logger.info(f"Escaneando Liquidez Institucional (SMC) para {asset}...")

        # Flatten columns se vier do yfinance MultiIndex, garante fallback seguro para DataFrame sintético
        try:
            if isinstance(df.columns, pd.MultiIndex):
                high = df["High"].iloc[:, 0].values
                low = df["Low"].iloc[:, 0].values
                close = df["Close"].iloc[:, 0].values
            else:
                if "High" in df.columns:
                    high = df["High"].values
                    low = df["Low"].values
                    close = df["Close"].values
                else:
                    # Fallback caso o dataset seja sintético sem max/min
                    close = df["Close"].values
                    high = close * 1.001
                    low = close * 0.999
        except Exception as e:
            logger.error(f"Erro ao processar velas no SMC: {e}")
            return {"smc_bias": "NEUTRAL", "fvg_detected": False, "fvg_type": None, "confidence_boost": 0.0}

        fvg_detected = False
        fvg_type = None
        
        # Algoritmo de Fair Value Gap (FVG) usando as últimas 3 velas
        # Bullish FVG: Low da Vela 3 > High da Vela 1
        # Bearish FVG: High da Vela 3 < Low da Vela 1
        
        if len(high) >= 3:
            v1_high, v1_low = high[-3], low[-3]
            v3_high, v3_low = high[-1], low[-1]
            
            if v3_low > v1_high:
                fvg_detected = True
                fvg_type = "BULLISH_FVG"
            elif v3_high < v1_low:
                fvg_detected = True
                fvg_type = "BEARISH_FVG"

        # Simples Market Structure Bias (Comparando o preço atual com o preço de 20 períodos atrás)
        if len(close) >= 20:
            if close[-1] > close[-20]:
                smc_bias = "BULLISH"
            else:
                smc_bias = "BEARISH"
        else:
            smc_bias = "NEUTRAL"
            
        confidence_boost = 0.0
        # Aumenta a convicção se o FVG se alinhar com a tendência macro
        if fvg_detected:
            if fvg_type == "BULLISH_FVG" and smc_bias == "BULLISH":
                confidence_boost = 0.15
            elif fvg_type == "BEARISH_FVG" and smc_bias == "BEARISH":
                confidence_boost = 0.15

        logger.info(f"SMC Scan {asset}: Bias={smc_bias}, FVG={fvg_type}, Alinhamento=+{confidence_boost}")

        return {
            "smc_bias": smc_bias,
            "fvg_detected": fvg_detected,
            "fvg_type": fvg_type,
            "confidence_boost": confidence_boost
        }
