#!/usr/bin/env python3
"""
Точка входа для запуска приложения из корня проекта.
Использование: python app.py
"""

import os
import sys
import logging

# Настраиваем логирование ДО импорта backend
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Добавляем корень проекта в PYTHONPATH
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

logger.info(f"🔍 BASE_DIR: {BASE_DIR}")
logger.info(f"🔍 PYTHONPATH: {sys.path[:3]}")

# Устанавливаем переменную окружения для правильного определения путей
os.environ['PROJECT_ROOT'] = BASE_DIR
logger.info(f"🔍 PROJECT_ROOT: {os.environ.get('PROJECT_ROOT')}")

# Проверяем существование критических файлов перед импортом
db_dir = "/workspace/data"
db_file = "/workspace/data/app.db"
logger.info(f"🔍 Директория БД существует: {os.path.exists(db_dir)}")
logger.info(f"🔍 Файл БД существует: {os.path.exists(db_file)}")
logger.info(f"🔍 Права на запись в директорию: {os.access(db_dir, os.W_OK)}")

from backend.main import app
import uvicorn

if __name__ == '__main__':
    logger.info("=" * 60)
    logger.info("🚀 Starting Network Asset Manager...")
    logger.info("=" * 60)
    logger.info("Database: SQLite (/workspace/data/app.db)")
    logger.info("")
    logger.info("🌐 Доступные интерфейсы для подключения:")
    logger.info("   ➤ http://127.0.0.1:5000")
    logger.info("")
    logger.info("📚 API Documentation: http://127.0.0.1:5000/docs")
    logger.info("🏠 Web Interface:     http://127.0.0.1:5000/")
    logger.info("=" * 60)
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=5000,
        log_level="info"
    )
