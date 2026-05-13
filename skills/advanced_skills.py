from core.base import BaseSkill
import asyncio
import numpy as np
import math
import logging

logger = logging.getLogger("AdvancedSkills")


class FractalPatternSkill(BaseSkill):
    """
    Análise Fractal Real via Hurst Exponent.
    Calcula o expoente de Hurst a partir dos retornos logarítmicos do histórico de preços.
    H > 0.5 = Tendência (persistência), H < 0.5 = Reversão à média, H ≈ 0.5 = Random Walk.
    """
    def __init__(self):
        super().__init__(name="FractalPattern")

    def _hurst_exponent(self, prices: np.ndarray) -> float:
        """Calcula o Hurst Exponent via método R/S (Rescaled Range)."""
        if len(prices) < 20:
            return 0.5  # Dados insuficientes → neutro
        
        log_returns = np.diff(np.log(prices))
        
        # Método R/S simplificado
        n = len(log_returns)
        max_k = min(n // 2, 50)
        if max_k < 4:
            return 0.5
            
        rs_list = []
        ns_list = []
        
        for k in range(4, max_k + 1):
            rs_values = []
            for start in range(0, n - k, k):
                chunk = log_returns[start:start + k]
                mean_chunk = np.mean(chunk)
                cumdev = np.cumsum(chunk - mean_chunk)
                r = np.max(cumdev) - np.min(cumdev)
                s = np.std(chunk, ddof=1) if np.std(chunk, ddof=1) > 0 else 1e-10
                rs_values.append(r / s)
            if rs_values:
                rs_list.append(np.mean(rs_values))
                ns_list.append(k)
        
        if len(rs_list) < 2:
            return 0.5
            
        log_rs = np.log(rs_list)
        log_ns = np.log(ns_list)
        
        # Regressão linear: log(R/S) = H * log(n) + c
        coeffs = np.polyfit(log_ns, log_rs, 1)
        return float(np.clip(coeffs[0], 0.0, 1.0))

    async def execute(self, historical_data=None, **kwargs) -> dict:
        self.logger.info("Calculando Hurst Exponent (análise fractal real)...")
        
        # Aceita DataFrame ou lista/array
        prices = None
        if historical_data is not None:
            if hasattr(historical_data, 'values'):
                # É um DataFrame/Series
                try:
                    import pandas as pd
                    if isinstance(historical_data.columns, pd.MultiIndex):
                        prices = historical_data["Close"].iloc[:, 0].values
                    elif "Close" in historical_data.columns:
                        prices = historical_data["Close"].values
                except Exception:
                    pass
            elif isinstance(historical_data, (list, np.ndarray)):
                prices = np.array(historical_data, dtype=float)
        
        if prices is None or len(prices) < 10:
            self.logger.warning("Dados insuficientes para cálculo fractal real. Retornando NEUTRAL.")
            return {
                "fractal_entropy": 0.5,
                "hidden_pattern_detected": False,
                "mathematical_bias": "NEUTRAL",
                "data_source": "INSUFFICIENT_DATA"
            }
        
        hurst = self._hurst_exponent(prices)
        
        # H > 0.6 = Forte tendência (padrão detectado)
        # H < 0.4 = Forte reversão à média
        # 0.4 <= H <= 0.6 = Sem padrão claro
        pattern_detected = abs(hurst - 0.5) > 0.1
        
        if hurst > 0.6:
            bias = "BULLISH" if prices[-1] > prices[-5] else "BEARISH"
        elif hurst < 0.4:
            bias = "BEARISH" if prices[-1] > prices[-5] else "BULLISH"  # Reversão esperada
        else:
            bias = "NEUTRAL"
        
        self.logger.info(f"Hurst Exponent = {hurst:.3f} | Bias = {bias} | Padrão = {pattern_detected}")
        
        return {
            "fractal_entropy": round(hurst, 4),
            "hidden_pattern_detected": pattern_detected,
            "mathematical_bias": bias,
            "data_source": "HURST_RS_REAL"
        }


class CrossAssetCorrelationSkill(BaseSkill):
    """
    Correlação Cross-Asset Real via Pearson.
    Calcula correlação entre dois ativos usando dados históricos reais do Yahoo Finance.
    """
    def __init__(self):
        super().__init__(name="CrossAssetCorrelation")

    async def execute(self, asset_a: str = "MNQ", asset_b: str = "MGC", **kwargs) -> dict:
        self.logger.info(f"Calculando correlação Pearson real entre {asset_a} e {asset_b}...")
        
        ticker_map = {"MNQ": "NQ=F", "MGC": "GC=F", "MES": "ES=F", "M6E": "EURUSD=X"}
        yf_a = ticker_map.get(asset_a, asset_a)
        yf_b = ticker_map.get(asset_b, asset_b)
        
        try:
            import yfinance as yf
            import pandas as pd
            
            # V16.2 FIX: 5min candles alinhado com timeframe operacional
            data_a = await asyncio.to_thread(yf.download, yf_a, period="5d", interval="5m", progress=False)
            data_b = await asyncio.to_thread(yf.download, yf_b, period="5d", interval="5m", progress=False)
            
            if data_a.empty or data_b.empty or len(data_a) < 10 or len(data_b) < 10:
                raise ValueError("Dados insuficientes para correlação")
            
            # Extrai Close
            close_a = data_a["Close"].iloc[:, 0].values if isinstance(data_a.columns, pd.MultiIndex) else data_a["Close"].values
            close_b = data_b["Close"].iloc[:, 0].values if isinstance(data_b.columns, pd.MultiIndex) else data_b["Close"].values
            
            # Alinha tamanhos
            min_len = min(len(close_a), len(close_b))
            close_a = close_a[-min_len:]
            close_b = close_b[-min_len:]
            
            # Retornos logarítmicos
            ret_a = np.diff(np.log(close_a))
            ret_b = np.diff(np.log(close_b))
            
            # Pearson
            correlation = float(np.corrcoef(ret_a, ret_b)[0, 1])
            
            # V16.2 NEW: SMT Divergence Detection (Smart Money Trap)
            # Se os últimos 5 candles mostram direções opostas = possível armadilha
            recent_a = ret_a[-5:] if len(ret_a) >= 5 else ret_a
            recent_b = ret_b[-5:] if len(ret_b) >= 5 else ret_b
            direction_a = 1 if np.sum(recent_a) > 0 else -1
            direction_b = 1 if np.sum(recent_b) > 0 else -1
            smt_divergence = direction_a != direction_b
            
            # Rolling correlation (últimas 20 barras) para detectar breakdown
            if len(ret_a) >= 20:
                rolling_corr = float(np.corrcoef(ret_a[-20:], ret_b[-20:])[0, 1])
            else:
                rolling_corr = correlation
            
            corr_breakdown = abs(correlation - rolling_corr) > 0.3
            
            self.logger.info(
                f"Correlação {asset_a}/{asset_b} = {correlation:.4f} | "
                f"SMT Divergence: {smt_divergence} | Rolling: {rolling_corr:.4f}"
            )
            
            return {
                "pair": f"{asset_a}/{asset_b}",
                "correlation": round(correlation, 4),
                "rolling_correlation": round(rolling_corr, 4),
                "smt_divergence": smt_divergence,
                "correlation_breakdown": corr_breakdown,
                "hedging_recommended": correlation < -0.5,
                "data_source": "YAHOO_FINANCE_5MIN"
            }
            
        except Exception as e:
            self.logger.warning(f"Falha ao calcular correlação real: {e}. Retornando NEUTRAL.")
            return {
                "pair": f"{asset_a}/{asset_b}",
                "correlation": 0.0,
                "rolling_correlation": 0.0,
                "smt_divergence": False,
                "correlation_breakdown": False,
                "hedging_recommended": False,
                "data_source": "UNAVAILABLE"
            }

