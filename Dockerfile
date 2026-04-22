FROM python:3.12-slim

WORKDIR /app

# Установка системных зависимостей для nmap и других утилит
RUN apt-get update && apt-get install -y --no-install-recommends \
    nmap \
    dnsutils \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Копирование файлов зависимостей
COPY requirements.txt .

# Установка Python зависимостей
RUN pip install --no-cache-dir -r requirements.txt

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