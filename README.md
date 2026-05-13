# Nexus Zenith Singularity Engine 🌌
**Versão Homologada: V10.5-production (Core V16.2 Quantum Reality)**

## 🛡️ Visão Institucional
O **Nexus Zenith Singularity Engine** é a infraestrutura de inteligência de enxame (Swarm Intelligence) projetada para **High-Frequency Trading e Risco Paramétrico**. Construído para aprovação rigorosa em mesas proprietárias (Apex Trader Funding), ele atua em simbiose com o painel `Extratredey` para atingir o nível **Zero-Defect Execution**.

A arquitetura resolve anomalias financeiras cognitivas por meio de Consenso Multi-agente, validado de ponta a ponta contra falhas silenciosas, problemas multi-drive, e interrupções de rede.

---

## 🚀 Pilares da Arquitetura (V10.5)

1. **A Malha Central (The Event Bus)**: Motor Event Loop não-bloqueante ultrarrápido (asyncio) gerenciando agentes via injeção de pub/sub e concorrência Thread-Safe (locks em ChromaDB e SQLite).
2. **Sistema Multi-Drive Cross-Silo**: 
   - **Drive I:** `Motor de Agentes` (Backend de processamento, ML, e Supabase persistence).
   - **Drive E:** `Extratredey` (FastAPI Webhooks, React/Next.js Dashboards, Webhooks de TradingView).
3. **Ponte Zero-Defect**: Resolução cruzada contínua (`live_pnl.json`) e callbacks rígidos em tasks assíncronas para interceptar qualquer crash silencioso de I/O de rede.

---

## 🏛️ Os Agentes (A Mesa Operacional)

A tomada de decisão passa por um funil de **6 Estágios Determinísticos**:

- **Data-Ops Agent**: Coleta estruturada em milissegundos combinando hooks físicos (API) e Pine Script Alerts (V9.2.2).
- **Macro-Geopolitica & Tape Reader**: *Fail-safes* que vetam o trade antecipadamente baseado em *Smart Money Traps* e choques de liquidez da CNBC RSS e ForexFactory. Possuem *pass-throughs* elegantes caso offline.
- **Oracle Agent (Cérebro)**: Motor preditivo focado em análise estrutural (SMC, ChoCH, FVG, e Squeeze Momentum).
- **Committee Agent (Consenso)**: Pesos calibrados ativamente via Kelly Criterion e Teoria dos Jogos.
- **Guardian Agent (Apex Compliance)**: O "Cão de Guarda". Um Singleton absoluto que persiste DD (Drawdown) diário, aplica Multiplicadores ATR de Kill Zones (NY_OPEN, LONDON) e rege o Circuit Breaker.
- **BrokerSyncAgent & DevOps**: Agentes autônomos de liquidação emergencial (`emergency_flatten`) se as métricas de saúde caírem (RAM > 95%, Ping > 300ms).

---

## ⚙️ Dependências Requeridas

As Chaves de API requeridas no `.env` do Motor:
- `TRADOVATE_API_KEY` e `TRADOVATE_API_SECRET`
- `SUPABASE_URL` e `SUPABASE_KEY` (Trilha de auditoria Forense criptografada)
- `CHROMA_DB_DIR` (Para persistência de contexto em RAG)
- `ENVIRONMENT=production`

---

## 🛠 Como Iniciar a Mesa Operacional (Homologação Final)

A sequência de partida para evitar timeouts de sincronização do Webhook é:

1. **Garantir a Source of Truth**:
   O arquivo `rules.json` (com os parâmetros exatos da Apex e do seu gerenciamento de risco) precisa ser idêntico no Motor (I:) e no Extratredey (E:).
   
2. **Ligar o Cérebro (Motor - Drive I:)**:
```bash
cd "I:\Motor de agentes skill"
python main.py
```
> O Motor registrará os Singletons (Guardian) e iniciará a escuta (porta 8005) para receber ordens e telemetria da L2 Feed.

3. **Ligar os Sentidos (Extratredey - Drive E:)**:
```bash
cd "E:\extratredey"
python src\main.py
```
> O Extratredey servirá o Dashboard na porta 3030 e iniciará a Rota do Webhook do TradingView na porta 8000.

---

### 📜 Manifesto do Arquiteto (V16.2 Audited)
> *"Nenhum trade entra cego. Nenhum trade falha em silêncio."*

Este motor foi refatorado a nível de `bytecode` cognitivo. Nós eliminamos mocks legados, hardcodes de fuso horário, race conditions no vetor de memória e garantimos que se a máquina for quebrar, ela quebra em *fail-safe* seguro (flatten all), salvando a conta financiadora.
