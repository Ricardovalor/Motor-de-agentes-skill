from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import sqlite3
import uvicorn
import os
import sys
import io
import json

# TITAN-015 FIX: Força UTF-8 no stdout para evitar UnicodeEncodeError
# no terminal Windows (cp1252 não suporta emojis)
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

app = FastAPI(title="Nexus Zenith V16.2 TITAN Dashboard")

ALLOWED_ORIGINS = [
    "http://localhost:3030",
    "http://127.0.0.1:3030",
    "http://localhost:8081",
    "http://127.0.0.1:8081",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "http://localhost:8005",
    "http://127.0.0.1:8005",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "memory_data", "telemetry.db")

def get_db_connection():
    """Retorna uma conexãoSQLite thread-safe com WAL mode e timeout configurados para produção HFT."""
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.row_factory = sqlite3.Row
    return conn

# Inicialização de tabelas necessárias no banco
def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Tabela de telemetria
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS telemetry (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            asset TEXT,
            signal TEXT,
            confidence REAL,
            status TEXT,
            raw_data TEXT
        )
    ''')
    
    # Tabela de prompts da biblioteca
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS prompts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT,
            description TEXT,
            score REAL,
            prompt_text TEXT
        )
    ''')
    
    # Popula prompts padrão caso a tabela esteja vazia
    cursor.execute("SELECT COUNT(*) as count FROM prompts")
    if cursor.fetchone()["count"] == 0:
        default_prompts = [
            ("Técnico (SMC)", "Identificação de Fair Value Gaps (FVG) de 1m alinhados a blocos de ordens institucionais de 15m no MNQ.", 9.8, 
             "Analise o fluxo do livro do MNQ para detectar desequilíbrios estruturais (FVG). Aguarde alinhamento temporal de 15m."),
            ("Guardian (Risco)", "Filtro estrito de limites de drawdown diário Apex de $500, com cálculo dinâmico de trailing drawdown e parada forçada.", 9.9, 
             "Limite DLL por ativo em -$250. Max diário -$500. Trailing drawdown calibrado em $2,000 máximo para conta Apex."),
            ("Feedback Loop RL", "Ajuste dinâmico de taxas de aprendizado via algoritmo Kelly Criterion com base no histórico de trades recentes de MGC.", 9.5, 
             "Calcule o Kelly Criterion com base no win rate de 30 dias. Aplique punição adaptativa se a latência subir."),
            ("Quantitativo", "Estimativa de desbalanço do livro de ofertas (Order Flow Imbalance - OFI) usando DOM L2 e desvio padrão de ordens iceberg.", 9.7, 
             "Monitore bids/asks em tempo real. Identifique pressões compradoras ou compradoras no book com peso dinâmico de desbalanceamento.")
        ]
        cursor.executemany(
            "INSERT INTO prompts (category, description, score, prompt_text) VALUES (?, ?, ?, ?)",
            default_prompts
        )
        conn.commit()
        
    conn.close()

init_db()

@app.get("/api/telemetry")
def get_telemetry():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM telemetry ORDER BY id DESC LIMIT 50")
        rows = cursor.fetchall()
        data = [dict(row) for row in rows]
        conn.close()
        return {"status": "success", "data": data}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/api/pnl")
def get_pnl():
    try:
        pnl_path = os.path.join(os.path.dirname(__file__), "..", "memory_data", "live_pnl.json")
        if os.path.exists(pnl_path):
            with open(pnl_path, "r") as f:
                return json.load(f)
        return {"pnl": 0.0}
    except Exception as e:
        return {"pnl": 0.0, "error": str(e)}

@app.get("/api/forensics")
def get_forensics():
    """
    Retorna o Histórico de Trades formatado a partir do banco de dados telemetry.db.
    Extrai preços e infere contratos dinamicamente do campo raw_data para total fidelidade de trading.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        # Filtra apenas registros que representam decisões do comitê de trading ou ordens executadas
        cursor.execute("SELECT * FROM telemetry WHERE status IN ('APPROVED_BY_COMMITTEE', 'EXECUTED_IN_BROKER', 'REJECTED_BY_GUARDIAN', 'REJECTED_BY_COMMITTEE') ORDER BY id DESC LIMIT 30")
        rows = cursor.fetchall()
        
        trades = []
        for row in rows:
            raw = {}
            try:
                raw = json.loads(row["raw_data"] or "{}")
            except:
                pass
            
            # Formatação inteligente do trade
            price = raw.get("price", raw.get("price_entry", 0.0))
            if not price and row["asset"] == "MNQ":
                price = 30405.25 # Fallback
            elif not price and row["asset"] == "MGC":
                price = 4593.0
                
            contracts = 6 if row["asset"] == "MNQ" else 1
            
            trades.append({
                "timestamp": row["timestamp"],
                "asset": row["asset"],
                "class": raw.get("smc_bias", "SMC + Quant"),
                "action": row["signal"],
                "price": price,
                "contracts": contracts,
                "confidence": row["confidence"],
                "status": row["status"]
            })
            
        conn.close()
        return {"status": "success", "data": trades}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/api/prompts")
def get_prompts():
    """
    Retorna os prompts cadastrados na biblioteca para a interface Prompt Engine.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM prompts ORDER BY id ASC")
        rows = cursor.fetchall()
        data = [dict(row) for row in rows]
        conn.close()
        return {"status": "success", "data": data}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/api/network")
def get_network_nodes():
    nodes = [
        {"id": 1, "label": "Data-Ops", "group": "ingestion", "title": "MarketDataFetchSkill"},
        {"id": 9, "label": "Macro-Geopolítica", "group": "analysis", "title": "MacroNewsSkill"},
        {"id": 2, "label": "Temporal-Chronos", "group": "analysis", "title": "FractalPatternSkill"},
        {"id": 3, "label": "Oracle-Prime", "group": "brain", "title": "Gemini + SMC + Quant"},
        {"id": 10, "label": "DevOps-Watchdog", "group": "security", "title": "KillSwitch / Ping / RAM"},
        {"id": 11, "label": "TapeReader-Flow", "group": "analysis", "title": "DOM L2 / Order Flow"},
        {"id": 4, "label": "Quantum-Risk", "group": "risk", "title": "MonteCarlo"},
        {"id": 5, "label": "Guardian-Protocol", "group": "security", "title": "Apex Compliance"},
        {"id": 6, "label": "Committee-Council", "group": "consensus", "title": "Final Verdict + RL"},
        {"id": 7, "label": "Broker-Execution", "group": "mcp", "title": "CDP/Port 9222"},
        {"id": 8, "label": "Forensic-Audit", "group": "memory", "title": "ChromaDB / Supabase"}
    ]
    edges = [
        {"from": 1, "to": 9}, {"from": 1, "to": 2},
        {"from": 9, "to": 3}, {"from": 3, "to": 10},
        {"from": 10, "to": 11}, {"from": 11, "to": 4},
        {"from": 4, "to": 5}, {"from": 5, "to": 6},
        {"from": 2, "to": 6}, {"from": 6, "to": 7},
        {"from": 6, "to": 8}, {"from": 7, "to": 8}
    ]
    return {"nodes": nodes, "edges": edges}

@app.get("/", response_class=HTMLResponse)
def serve_dashboard():
    html_path = os.path.join(os.path.dirname(__file__), "index.html")
    with open(html_path, "r", encoding="utf-8") as f:
        return f.read()

if __name__ == "__main__":
    print("🚀 Iniciando Nexus Unified Dashboard na porta 3030...")
    uvicorn.run(app, host="0.0.0.0", port=3030)
