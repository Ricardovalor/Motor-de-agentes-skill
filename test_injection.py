import requests
import json
import time
import sys
import io

# TITAN-015 FIX: Força UTF-8 no stdout para evitar UnicodeEncodeError
# no terminal Windows (cp1252 não suporta emojis)
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

def inject_signal(asset, signal, price):
    url = "http://localhost:8005/webhook/tradingview"
    
    payload = {
        "asset": asset,
        "signal": signal,
        "price": price
    }
    
    headers = {
        "Content-Type": "application/json"
    }
    
    print(f"[INJECTOR] Disparando Sinal {signal} no {asset} a ${price}...")
    
    try:
        start_time = time.time()
        response = requests.post(url, data=json.dumps(payload), headers=headers, timeout=30)
        end_time = time.time()
        
        latency = round((end_time - start_time) * 1000, 2)
        
        if response.status_code == 200:
            print(f"[SUCESSO] Roteamento concluido! O Motor engoliu a ordem em {latency}ms.")
            print(f"[RESPOSTA] {response.json()}")
        else:
            print(f"[ERRO] O Motor recusou o pacote HTTP: {response.status_code}")
            print(f"Detalhes: {response.text}")
            
    except requests.exceptions.ConnectionError:
        print("[FALHA] O Motor parece estar offline. Voce esqueceu de rodar 'py main.py'?")
    except Exception as e:
        print(f"[ERRO INTERNO] {e}")

if __name__ == "__main__":
    print("=========================================================")
    print("      Nexus Zenith - TradingView Webhook Injector        ")
    print("=========================================================")
    
    inject_signal(asset="MES", signal="LONG", price=5042.25)
    
    print("=========================================================")
    print("Injecao concluida. Verifique a tela do Motor para os logs.")
