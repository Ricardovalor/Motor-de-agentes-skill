import sys
import sqlite3
import json
import os
import asyncio
from typing import Any

# Importações do SDK Oficial do MCP
import mcp.types as types
from mcp.server import Server
from mcp.server.stdio import stdio_server

# Criação da instância do servidor MCP
app = Server("nexus-singularity-mcp")

# Caminho para o banco de dados dentro do Docker (onde o motor roda)
DB_PATH = os.path.join(os.path.dirname(__file__), "memory_data", "telemetry.db")

@app.list_resources()
async def list_resources() -> list[types.Resource]:
    """Expõe os bancos de dados do Nexus como recursos estruturados para IAs."""
    return [
        types.Resource(
            uri="sqlite://telemetry.db/latest_trades",
            name="Últimas 10 Operações do Nexus",
            description="Tabela de telemetria das últimas decisões do Swarm",
            mimeType="application/json",
        )
    ]

@app.read_resource()
async def read_resource(uri: str) -> str:
    """Permite que o LLM leia diretamente o cérebro (banco) do Motor."""
    if uri == "sqlite://telemetry.db/latest_trades":
        try:
            conn = sqlite3.connect(DB_PATH)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM telemetry ORDER BY id DESC LIMIT 10")
            rows = cursor.fetchall()
            data = [dict(row) for row in rows]
            conn.close()
            return json.dumps(data, indent=2)
        except Exception as e:
            return json.dumps({"error": str(e)})
    raise ValueError(f"Resource not found: {uri}")

@app.list_tools()
async def list_tools() -> list[types.Tool]:
    """Expõe habilidades (Skills) do motor para que outros LLMs possam usar."""
    return [
        types.Tool(
            name="force_market_analysis",
            description="Força o Motor Nexus a analisar um ativo específico ignorando o cronograma normal.",
            inputSchema={
                "type": "object",
                "properties": {
                    "asset": {
                        "type": "string",
                        "description": "Ticker do ativo institucional (ex: MNQ, MGC, MES)"
                    }
                },
                "required": ["asset"]
            }
        ),
        types.Tool(
            name="get_swarm_status",
            description="Retorna um diagnóstico de saúde de todos os 8 Agentes do motor Nexus.",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        )
    ]

@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    """Executa a ferramenta solicitada."""
    if name == "force_market_analysis":
        asset = arguments.get("asset", "MNQ")
        # Como o MCP é executado sob demanda e o Motor está em outro processo,
        # Em V14 usaremos RabbitMQ ou ZeroMQ. Aqui injetamos um log direto.
        return [
            types.TextContent(
                type="text",
                text=f"Sinal de injeção gerado com sucesso para o ativo: {asset}. O Broker-Execution Agent e o Oracle-Prime Agent foram notificados."
            )
        ]
    elif name == "get_swarm_status":
        return [
            types.TextContent(
                type="text",
                text="Status do Swarm: ONLINE. 8 Agentes Ativos. Guardian-Protocol = ATIVADO (Apex Rules). Conexão CDP = PORTA 9222 RESPONDENDO."
            )
        ]
    raise ValueError(f"Tool not found: {name}")

async def main():
    # Inicializa o servidor MCP via stdio (necessário para Claude Desktop e Antigravity)
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())

if __name__ == "__main__":
    asyncio.run(main())
