# Nexus Zenith — Motor de Agentes Skill 🌌
**Versão: V16.2 TITAN Hardened** | Apex Trader Funding Compliant | EOD 50K

---

## Visão Geral

O **Nexus Zenith Motor** é o backend institucional de análise e execução automatizada de operações em futuros micro (CME).
Opera como um swarm de **12 agentes autônomos** coordenados por um **Event Bus assíncrono** (pub/sub), validando cada sinal através de um pipeline de **6 estágios determinísticos** antes de qualquer roteamento de ordem.

### Ativos Monitorados
| Ativo | Classe | Tick Size | Tick Value |
|:------|:------:|:---------:|:----------:|
| MNQ | Equity Index | 0.25 | $0.50 |
| MGC | Precious Metal | 0.10 | $1.00 |
| MES | Equity Index | 0.25 | $1.25 |
| M6E | FX | 0.0001 | $1.25 |

---

## Arquitetura

```
TradingView (Pine Script V10.5)
        │ Webhook POST /webhook
        ▼
┌─────────────────────────────────────────────┐
│           NexusEngine (Event Bus)            │
│       asyncio.Queue (backpressure=100)       │
├─────────┬──────────┬───────────┬────────────┤
│ Oracle  │Committee │ Guardian  │ BrokerSync │
│  (SMC)  │(4-Chair) │  (Apex)   │ (Trailing) │
├─────────┴──────────┴───────────┴────────────┤
│ MacroNews │ TapeReader │ Temporal │ Forensic │
├─────────────────────────────────────────────┤
│          Skills Layer (15 Skills)            │
│  Tradovate API │ ChromaDB │ yFinance │ RSS  │
└─────────────────────────────────────────────┘
        │ DMA Order
        ▼
  Tradovate API (REST/WebSocket)
```

---

## Agentes (12)

| Agente | Função | Padrão |
|:-------|:-------|:------:|
| **OracleAgent** | Análise SMC (BOS, FVG, ChoCH, OB) | Singleton |
| **CommitteeAgent** | Consenso de 4 cadeiras (SMC, Quant, Risk, Compliance) | Singleton |
| **GuardianAgent** | Compliance Apex (DD, DLL, Kill Zones, anti-overtrading) | Singleton |
| **BrokerSyncAgent** | PnL em tempo real + trailing stop dinâmico | Singleton |
| **ExecutionAgent** | Roteamento de ordens (API/CDP) | Standard |
| **ForensicAgent** | Auditoria + gravação telemetria | Singleton |
| **MacroSentimentAgent** | RSS multi-provider (CNBC/Yahoo/MarketWatch) | Standard |
| **TapeReaderAgent** | L2 DOM + order flow analysis | Standard |
| **TemporalAgent** | Hurst exponent + fractal analysis | Standard |
| **DataAgent** | Market data (yFinance fallback) | Standard |
| **QuantumRiskAgent** | Monte Carlo + VaR + correlação | Standard |
| **DevOpsAgent** | Kill switch + health monitoring | Standard |

---

## Skills (15)

| Skill | Arquivo | Integração |
|:------|:--------|:-----------|
| TradovateAPISkill | `tradovate_api_skill.py` | REST API DMA (aiohttp persistent session) |
| MacroNewsSkill | `macro_news_skills.py` | RSS chain: CNBC → Yahoo → MarketWatch |
| ExecutionSkill | `execution_skills.py` | Bracket orders OSO (MNQ/MGC/MES/M6E) |
| MarketSkill | `market_skills.py` | yFinance real-time quotes |
| AdvancedSkill | `advanced_skills.py` | SMC pattern detection |
| TemporalSkill | `temporal_skills.py` | Hurst + fractal |
| ComplianceSkill | `compliance_skills.py` | Apex rule enforcement |
| AISkill | `ai_skills.py` | Gemini/OpenAI inference |
| MacroCalendarSkill | `macro_calendar_skill.py` | Economic event blackout |
| BrokerSkill | `broker_skills.py` | CDP screen reader (legacy) |
| CommonSkills | `common_skills.py` | Shared utilities |

---

## Pré-Requisitos

| Ferramenta | Versão Mínima |
|:-----------|:-------------|
| Python | 3.9+ |
| Docker | 29+ |
| Git | 2.40+ |

### Dependências Python
```
pip install -r requirements.txt
```

---

## Variáveis de Ambiente (.env)

```env
ENVIRONMENT=production
SUPABASE_URL=https://vrehsxauesxobieimitb.supabase.co
SUPABASE_KEY=<sua_service_role_key>
GEMINI_API_KEY=<sua_chave_gemini>
MAX_DRAWDOWN_PERCENT=4.0
ORACLE_CONFIDENCE_THRESHOLD=0.65
GUARDIAN_STRICT_MODE=True
```

---

## Como Rodar

### Local (desenvolvimento)
```powershell
cd "I:\Motor de agentes skill"
py main.py
# → Engine na porta 8005
# → Dashboard na porta 3030
```

### Docker
```powershell
cd "I:\Motor de agentes skill"
docker-compose up -d --build
```

### Teste de Injeção
```powershell
py test_injection.py
# Dispara sinal LONG MES via webhook local
```

---

## Infraestrutura

| Componente | Porta | Protocolo |
|:-----------|:-----:|:---------:|
| Motor Webhook | 8005 | HTTP POST |
| Swarm Dashboard | 3030 | HTTP/WS |
| MCP Server | 8006 | Stdio |
| Chrome CDP | 9222 | WS (legado) |

---

## Projeto TITAN (V16.2 Hardening)

19 correções de nível institucional aplicadas em 13/Mai/2026:

- **TITAN-001**: EventBus backpressure (Queue maxsize=100)
- **TITAN-002**: SQLite conexão persistente + threading.Lock
- **TITAN-003**: ChromaDB lock timeout 5s
- **TITAN-004**: MemoryBank Singleton (Oracle + Forensic)
- **TITAN-005**: Bloqueio de ordens sem Stop Loss
- **TITAN-006**: Trailing stop com entry_price real
- **TITAN-007**: MES/M6E nos ASSET_PARAMS
- **TITAN-008**: Kill Zone dinâmica no trade journal
- **TITAN-009**: Graceful shutdown com flag propagation
- **TITAN-010**: Anti-hedging duplicado removido
- **TITAN-011**: RSS chain 3 provedores (CNBC/Yahoo/MW)
- **TITAN-012**: Import order PEP 8
- **TITAN-013**: SQLite path unificado
- **TITAN-014**: aiohttp session persistente (connection pooling)
- **TITAN-015**: Fix encoding UTF-8 para Windows cp1252

---

## Compliance Apex Trader Funding

| Regra | Valor | Enforcement |
|:------|:------|:-----------|
| Max Trailing Drawdown | $2,000 | GuardianAgent (EOD) |
| Max Daily Loss (DLL) | $1,000 | GuardianAgent (pause) |
| Max Diário de Trades | 3 | GuardianAgent (counter) |
| Flatten antes do close | 16:55 ET | rules.json auto_flatten |
| Modelo | EOD 50K | Evaluation phase |

---

## Repositórios

| Repo | Link |
|:-----|:-----|
| Motor de Agentes | [GitHub](https://github.com/Ricardovalor/Motor-de-agentes-skill) |
| Extratredey Gateway | [GitHub](https://github.com/Ricardovalor/extratredey) |

---

> *"Nenhum trade entra cego. Nenhum trade falha em silêncio."*  
> — Manifesto Nexus Zenith V16.2 TITAN
