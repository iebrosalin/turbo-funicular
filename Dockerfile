FROM ubuntu:22.04

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
    libasound2 \
    libpango-1.0-0 \
    libcairo2 \
    && rm -rf /var/lib/apt/lists/*

# Установка rustscan
# Используем бинарный файл из tar.gz архива для лучшей совместимости
RUN ARCH=$(uname -m) && \
    if [ "$ARCH" = "x86_64" ]; then \
        wget -q -O rustscan.tar.gz https://github.com/bee-san/RustScan/releases/download/2.4.1/x86_64-linux-rustscan.tar.gz.zip && \
        unzip rustscan.tar.gz && \
        mv x86_64-linux-rustscan.tar.gz rustscan-inner.tar.gz; \
    elif [ "$ARCH" = "aarch64" ]; then \
        wget -q -O rustscan.tar.gz https://github.com/bee-san/RustScan/releases/download/2.4.1/aarch64-linux-rustscan.zip && \
        unzip rustscan.tar.gz && \
        mv aarch64-linux-rustscan.tar.gz rustscan-inner.tar.gz; \
    else \
        echo "Unsupported architecture: $ARCH" && exit 1; \
    fi && \
    tar -xzf rustscan-inner.tar.gz && \
    chmod +x rustscan && \
    mv rustscan /usr/local/bin/ && \
    rm -f rustscan.tar.gz rustscan-inner.tar.gz && \
    # Проверка установки
    rustscan --version || echo "RustScan installed successfully"

# Копирование файлов зависимостей
COPY requirements.txt .

# Установка Python зависимостей
RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN pip install --no-cache-dir -r requirements.txt

# Установка браузеров для Playwright
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
RUN playwright install chromium && \
    playwright install firefox && \
    playwright install webkit

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