# Use a imagem oficial do Python que já suporta Playwright ou uma base leve
FROM python:3.12-slim

# Dependências do Chromium/Playwright
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    libglib2.0-0 \
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxext6 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libpango-1.0-0 \
    libcairo2 \
    libasound2 \
    libgtk-3-0 \
    libx11-xcb1 \
    fonts-liberation \
    xdg-utils \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copiar apenas os requisitos primeiro para aproveitar o cache do Docker
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Instalar os navegadores do Playwright
RUN playwright install chromium

# Criar o diretório de dados
RUN mkdir -p /app/data

# Copiar o restante do código
COPY . .

# Comando para rodar o bot
CMD ["python", "run.py"]
