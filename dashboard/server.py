from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import sqlite3
import uvicorn
import os

app = FastAPI(title="Nexus Unified Dashboard")

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
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "memory_data", "telemetry.db")

@app.get("/api/telemetry")
def get_telemetry():
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Cria a tabela de telemetria se não existir (para evitar erros se o dashboard ligar antes do motor)
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
            import json
            with open(pnl_path, "r") as f:
                return json.load(f)
        return {"pnl": 0.0}
    except Exception as e:
        return {"pnl": 0.0, "error": str(e)}

@app.get("/api/swarm/consolidated")
def get_swarm_consolidated():
    """V16.2: Proxy para /api/swarm/stats do Extratredey Guardian."""
    import urllib.request
    try:
        req = urllib.request.Request("http://host.docker.internal:8000/api/swarm/stats")
        resp = urllib.request.urlopen(req, timeout=3)
        import json as _json
        return _json.loads(resp.read())
    except Exception:
        # Fallback: dados locais
        return {"status": "guardian_offline", "source": "local_dashboard"}

@app.get("/api/network")
def get_network_nodes():
    # Retorna a topologia do Swarm para o Visualizador MCP
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
