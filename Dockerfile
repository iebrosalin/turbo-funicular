FROM python:3.12-slim

WORKDIR /app

# Установка системных зависимостей для nmap и других утилит
RUN apt-get update && apt-get install -y --no-install-recommends \
    nmap \
    dnsutils \
    gcc \
    libpq-dev \
    curl \
    wget \
    ca-certificates \
    unzip \
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
RUN pip install --no-cache-dir -r requirements.txt

# Копирование всего кода приложения
COPY backend/ ./backend/
COPY frontend/ ./frontend/

# Создание директории для базы данных (если используется SQLite)
RUN mkdir -p /app/instance

# Порт приложения
EXPOSE 8000

# Команда запуска FastAPI приложения
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]