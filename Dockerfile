FROM python:3.11-slim

# Evita que o Python escreva arquivos .pyc
ENV PYTHONDONTWRITEBYTECODE 1
# Mantém os logs do python desimpedidos para visualização no docker
ENV PYTHONUNBUFFERED 1

WORKDIR /app

# Instala dependências do sistema e Node.js para o TradingView MCP Server
RUN apt-get update && apt-get install -y curl && \
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y \
    build-essential \
    libsqlite3-dev \
    nodejs \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copia o código do motor
COPY . .

# Instala as dependências do servidor MCP Node.js (se existirem)
RUN if [ -d "tradingview-mcp" ]; then cd tradingview-mcp && npm install; fi

# Expõe a porta padrão para futuro dashboard/API
EXPOSE 8005

# Executa o Event Loop do motor
CMD ["python", "main.py"]
