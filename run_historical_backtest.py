import asyncio
import aiohttp
import yfinance as yf
import pandas as pd
from ta.momentum import RSIIndicator
from ta.trend import EMAIndicator
import time
import json
import sqlite3

# ═══════════════════════════════════════════════════════════════════════════
# 🦅 NEXUS ZENITH V16.2 - QUANTUM HISTORICAL BACKTEST SCRIPT
# ═══════════════════════════════════════════════════════════════════════════
# ═══════════════════════════════════════════════════════════════════════════
# Simula os disparos passados do TradingView lendo dados históricos.
# Requer que o Motor Nexus esteja rodando na porta 8000.
# ═══════════════════════════════════════════════════════════════════════════

ASSET = "MNQ"
YF_TICKER = "NQ=F"

async def send_signal(session, asset, signal, price, timestamp, fvg_type):
    payload = {
        "asset": asset,
        "signal": signal,
        "price": price,
        "fvg_detected": True,
        "fvg_type": fvg_type,
        "timestamp": timestamp.isoformat()
    }
    
    for port in [8000, 8005]:
        url = f"http://127.0.0.1:{port}/webhook/tradingview"
        try:
            async with session.post(url, json=payload, timeout=3) as response:
                result = await response.text()
                if response.status == 200:
                    print(f"[{timestamp}] 📤 Injeção enviada na porta {port}: {signal} @ {price:.2f} -> Motor Retornou OK")
                    return True
        except Exception:
            continue
            
    print(f"[{timestamp}] ❌ Motor Offline nas portas 8000 e 8005. Certifique-se que o Nexus ou o Docker está rodando!")
    return False

async def run_backtest():
    print(f"\n🔄 Iniciando Backtest Estrutural com Dados Passados do {ASSET}...")
    print("Baixando dados do Yahoo Finance (Últimos 15 dias, 1 hora)...")
    
    df = yf.download(YF_TICKER, period="15d", interval="1h", progress=False)
    
    if df.empty:
        print("⚠️ Yahoo Finance bloqueou a conexão ou sem dados. Gerando Série Histórica Sintética (Ondas Senoidais + Ruído)...")
        import numpy as np
        dates = pd.date_range(end=pd.Timestamp.now(), periods=100, freq='1h')
        t = np.arange(100)
        # Cria uma tendência forçada para simular Bull e Bear Runs e bater no RSI
        prices = 19500 + np.sin(t * 0.15) * 1500 + np.random.randn(100) * 5
        df = pd.DataFrame({"Close": prices}, index=dates)

    # Se as colunas vierem em formato MultiIndex (Comum no yfinance mais recente)
    if isinstance(df.columns, pd.MultiIndex):
        close_series = df["Close"].iloc[:, 0]
    else:
        close_series = df["Close"]

    print("Calculando Indicadores Físicos (RSI, EMA)...")
    df['RSI_14'] = RSIIndicator(close_series, window=14).rsi()
    df['EMA_50'] = EMAIndicator(close_series, window=50).ema_indicator()
    
    # Remove NaN
    df = df.dropna()

    print("\n🔍 Procurando setups no passado...")
    setups = []
    
    # Varredura (Simulando o Pine Script)
    for index, row in df.iterrows():
        # Lidar com extração caso seja DataFrame multivariado do YF
        rsi = row['RSI_14'].iloc[0] if isinstance(row['RSI_14'], pd.Series) else row['RSI_14']
        price = row['Close'].iloc[0] if isinstance(row['Close'], pd.Series) else row['Close']
        ema = row['EMA_50'].iloc[0] if isinstance(row['EMA_50'], pd.Series) else row['EMA_50']
        
        signal = None
        fvg_type = "UNKNOWN"
        
        if rsi < 45:
            signal = "LONG"
            fvg_type = "BULLISH_H4"
        elif rsi > 55:
            signal = "SHORT"
            fvg_type = "BEARISH_H4"
            
        if signal:
            setups.append((index, signal, float(price), fvg_type, float(rsi)))
            
    print(f"🎯 Foram encontrados {len(setups)} setups históricos que ativariam o TradingView.")
    print("Iniciando injeção no Motor Nexus...\n")
    
    async with aiohttp.ClientSession() as session:
        for setup in setups:
            timestamp, signal, price, fvg_type, rsi = setup
            print(f"--- Processando Sinal Histórico: RSI {rsi:.2f} ---")
            success = await send_signal(session, ASSET, signal, price, timestamp, fvg_type)
            if not success:
                print("⚠️ Interrompendo backtest pois o motor não está respondendo.")
                break
            
            # Pausa para dar tempo ao sistema (Agentes, Supabase, ML) processar a ordem
            await asyncio.sleep(4.0)
            
    print("\n✅ Backtest Concluído. O motor processou o histórico como se fosse tempo real.")
    print("Verifique o dashboard em http://127.0.0.1:8000 para analisar o Machine Learning reagindo a cada tentativa!")

def gerar_auditoria_banco():
    print("\n📊 --- RELATÓRIO DE AUDITORIA FORENSE (TELEMETRY DB) ---")
    try:
        conn = sqlite3.connect("memory_data/telemetry.db")
        cursor = conn.cursor()
        cursor.execute("SELECT timestamp, asset, signal, status, confidence FROM telemetry ORDER BY timestamp DESC LIMIT 10")
        rows = cursor.fetchall()
        
        if not rows:
            print("Nenhum dado encontrado no banco de telemetria.")
        else:
            print(f"{'DATA/HORA':<22} | {'ATIVO':<6} | {'SINAL':<6} | {'STATUS':<25} | {'QS'}")
            print("-" * 75)
            for r in rows:
                print(f"{r[0]:<22} | {r[1]:<6} | {r[2]:<6} | {r[3]:<25} | {r[4]:.2f}")
        conn.close()
    except Exception as e:
        print(f"Não foi possível ler a telemetria: {e}")

if __name__ == "__main__":
    asyncio.run(run_backtest())
    time.sleep(2)
    gerar_auditoria_banco()
