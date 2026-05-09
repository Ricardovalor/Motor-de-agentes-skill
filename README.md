# Nexus Singularity Engine (Motor de Agentes & Skills) 🌌

## Visão Geral do Projeto
O **Nexus Singularity Engine** é a evolução arquitetônica definitiva, sintetizada a partir das melhores práticas institucionais e analíticas dos projetos `Extratredey` (High-Frequency Trading & Risk) e `Jogo Quina Trinca` (Deep Pattern Recognition & Committee Logic). 

Este repositório atua como um **"Motor" (Engine)** revolucionário de Inteligência Artificial, projetado para operar com enxames de agentes autônomos (Swarm Intelligence) conectados a habilidades (Skills) dinâmicas.

A arquitetura não prejudica nenhum dos projetos legados, servindo como a "Next-Gen" para a equipe inteira escalar novas aplicações e análises tecnológicas.

## 🚀 Arquitetura Revolucionária

O motor se baseia nos seguintes pilares fundamentais, todos unificados via um Message Bus assíncrono:

1. **The Engine (O Motor)**: Coração do sistema. Um Event Loop assíncrono ultrarrápido que gerencia o ciclo de vida dos agentes, injeção de dependências e distribuição de tarefas em tempo real.
2. **Os Agentes**: Entidades autônomas cognitivas.
   - **Oracle Agent**: O "Cérebro" Preditivo (LLM-driven).
   - **Guardian Agent**: O "Cão de Guarda" para Validação e Compliance (Zero-Defect).
   - **Committee Agent**: O "Tribunal" de Consenso Multi-agente (Evita alucinações e garante alta probabilidade).
   - **Forensic Agent**: Auditoria de Performance e Machine Learning Feedback.
3. **Skills (Habilidades)**: Módulos plugáveis. Onde antes a lógica era engessada no agente, agora os agentes "equipam" skills (ex: Web Scraping, ML Analysis, Code Execution, Backtesting).
4. **Memory (Vector & State)**: Memória contínua e persistente baseada em RAG (Retrieval-Augmented Generation) para longo prazo e Redis/Memory para curto prazo.

## 🛠 Estrutura do Diretório

```
/
├── core/               # Núcleo do Motor (Event Bus, System Loop)
├── agents/             # Agentes Autônomos (Oracle, Guardian, Committee, etc)
├── skills/             # Habilidades acopláveis aos Agentes
├── memory/             # Banco de dados Vetorial e Retenção de Contexto
├── telemetry/          # Monitoramento Institucional e Logs
├── config/             # Parâmetros de Configuração e Envs
├── main.py             # Entrypoint de Inicialização do Motor
├── requirements.txt    # Dependências do Sistema
└── Dockerfile          # Containerização Institucional
```

## Como Iniciar

1. Clone o projeto e instale as dependências:
```bash
pip install -r requirements.txt
```

2. Execute o Motor:
```bash
python main.py
```

## Manifesto da Equipe
Este projeto foi idealizado pela análise de tecnologia reversa e síntese de arquiteturas avançadas. Bem-vindos ao próximo nível de autonomia artificial.
