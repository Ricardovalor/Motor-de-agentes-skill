import urllib.request
import json

def disparar_sinal(asset="MNQ", signal="LONG", price=19500):
    print(f"🚀 Iniciando teste de injeção na mesa HFT - Ativo: {asset} | Sinal: {signal}")
    url = "http://127.0.0.1:8000/webhook/tradingview" # Executando de dentro do mesmo container/host (porta real Python)
    
    # Se bater no Docker do lado de fora, a porta mapeada é 8005
    # Tenta 8000 (se tiver rodando `python main.py` puro) e 8005 (se tiver no Docker)
    payload = json.dumps({
        "asset": asset, 
        "signal": signal, 
        "price": price,
        "fvg_detected": True,
        "fvg_type": "BULLISH_H4"
    }).encode('utf-8')
    
    success = False
    for port in [8000, 8005]:
        try:
            req = urllib.request.Request(f"http://127.0.0.1:{port}/webhook/tradingview", data=payload, headers={'Content-Type': 'application/json'})
            response = urllib.request.urlopen(req, timeout=3)
            data = response.read().decode('utf-8')
            print(f"✅ Sucesso na Porta {port}! Motor Nexus Recebeu o Sinal: {data}")
            success = True
            break
        except Exception as e:
            pass

    if not success:
        print("❌ FALHA! Certifique-se que o motor está rodando via 'python main.py' ou 'docker-compose up'.")

if __name__ == "__main__":
    disparar_sinal(asset="MNQ", signal="LONG", price=19850.50)
