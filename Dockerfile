FROM python:3.11-slim

# Evita que o Python escreva arquivos .pyc
ENV PYTHONDONTWRITEBYTECODE 1
# Mantém os logs do python desimpedidos para visualização no docker
ENV PYTHONUNBUFFERED 1

WORKDIR /app

# Instala dependências do sistema
RUN apt-get update && apt-get install -y \
    build-essential \
    libsqlite3-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copia o código do motor
COPY . .

# Expõe a porta padrão para futuro dashboard/API
EXPOSE 8000

# Executa o Event Loop do motor
CMD ["python", "main.py"]
