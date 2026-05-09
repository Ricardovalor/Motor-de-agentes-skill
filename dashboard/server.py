from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import sqlite3
import uvicorn
import os

app = FastAPI(title="Nexus Unified Dashboard")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "memory_data", "telemetry.db")

@app.get("/api/telemetry")
def get_telemetry():
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Cria a tabela se não existir (para evitar erros se o dashboard ligar antes do motor)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS executions (
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

@app.get("/api/network")
def get_network_nodes():
    # Retorna a topologia do Swarm para o Visualizador MCP
    nodes = [
        {"id": 1, "label": "Data-Ops", "group": "ingestion", "title": "MarketDataFetchSkill"},
        {"id": 2, "label": "Temporal-Chronos", "group": "analysis", "title": "FractalPatternSkill"},
        {"id": 3, "label": "Oracle-Prime", "group": "brain", "title": "GeminiInferenceSkill"},
        {"id": 4, "label": "Quantum-Risk", "group": "risk", "title": "MonteCarlo"},
        {"id": 5, "label": "Guardian-Protocol", "group": "security", "title": "Apex Compliance"},
        {"id": 6, "label": "Committee-Council", "group": "consensus", "title": "Final Verdict"},
        {"id": 7, "label": "Broker-Execution", "group": "mcp", "title": "CDP/Port 9222"},
        {"id": 8, "label": "Forensic-Audit", "group": "memory", "title": "ChromaDB / SQLite"}
    ]
    edges = [
        {"from": 1, "to": 2}, {"from": 1, "to": 3},
        {"from": 2, "to": 6}, {"from": 3, "to": 4},
        {"from": 4, "to": 5}, {"from": 5, "to": 6},
        {"from": 6, "to": 7}, {"from": 7, "to": 8},
        {"from": 6, "to": 8}
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
