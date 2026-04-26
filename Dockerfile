FROM ubuntu:24.04

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    python3-venv \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Установка системных зависимостей для nmap, playwright и других утилит
RUN apt-get update && apt-get install -y --no-install-recommends \
    nmap \
    dnsutils \
    gcc \
    libpq-dev \
    curl \
    wget \
    ca-certificates \
    unzip \
    # Playwright dependencies
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libdbus-1-3 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libasound2t64 \
    libpango-1.0-0 \
    libcairo2 \
    && rm -rf /var/lib/apt/lists/*

# Установка rustscan
# RustScan теперь распространяется в zip-архиве с .deb файлом внутри
RUN wget -q -O rustscan.deb.zip https://github.com/bee-san/RustScan/releases/download/2.4.1/rustscan.deb.zip \
    && unzip rustscan.deb.zip \
    && dpkg -i rustscan_*.deb || apt-get install -f -y \
    && rm -f rustscan.deb.zip rustscan.tmp*-stripped rustscan_*.deb

# Копирование файлов зависимостей
COPY requirements.txt .

# Установка Python зависимостей
RUN pip3 install --break-system-packages --no-cache-dir -r requirements.txt

# Установка системных зависимостей для Playwright (Chromium)
RUN apt-get update && apt-get install -y \
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libdbus-1-3 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libasound2t64 \
    libatspi2.0-0 \
    fonts-unifont \
    libxshmfence1 \
    && rm -rf /var/lib/apt/lists/*

# Установка браузеров для Playwright
# Используем --no-deps, так как зависимости уже установлены выше
RUN playwright install chromium
RUN playwright install-deps chromium || true

# Создание директории для базы данных (если используется SQLite)
RUN mkdir -p /app/instance

# Переменные окружения
ENV FLASK_APP=app.py
ENV PYTHONUNBUFFERED=1
ENV FLASK_DEBUG=1

# Порт приложения
EXPOSE 5000

# Команда запуска: для разработки используем flask run с автоперезагрузкой
# Для production замените на gunicorn
CMD ["flask", "run", "--host=0.0.0.0", "--port=5000", "--reload"]