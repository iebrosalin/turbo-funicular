# Используем актуальный стабильный образ Python 3.12
FROM python:3.12-slim

# Установка системных зависимостей
# Добавлены: rustscan (быстрый сканер), dnsutils (dig), nmap
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    nmap \
    rustscan \
    dnsutils \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Копирование файла зависимостей
COPY requirements.txt .

# Установка Python-зависимостей
RUN pip install --no-cache-dir -r requirements.txt

# Копирование всего исходного кода
COPY . .

# ---------------------------------------------------------
# ЭТАП БЕЗОПАСНОСТИ: Запуск тестов при сборке образа
# Если тесты падают, сборка прерывается с ошибкой.
# ---------------------------------------------------------
RUN echo "🧪 Running tests during Docker build..." && \
    python -m pytest tests/ -v --tb=short || \
    (echo "❌ BUILD FAILED: Tests did not pass!" && exit 1)
# ---------------------------------------------------------

# Команда запуска контейнера:
# 1. Применяем миграции Alembic
# 2. Запускаем сервер Uvicorn
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]