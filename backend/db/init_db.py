#!/usr/bin/env python3
"""
Скрипт инициализации базы данных.
Создает все таблицы если они не существуют.
"""
import asyncio
import sys
import os

# Добавляем корень проекта в path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.db.session import engine
from sqlalchemy import text


async def init_db():
    """Инициализация базы данных."""
    # Импортируем все модели чтобы они зарегистрировались в metadata
    from backend.models import Asset, Group, Scan, ScanJob, ScanResult, ActivityLog, ServiceInventory
    
    async with engine.begin() as conn:
        # Создаем все таблицы
        await conn.run_sync(
            lambda conn: Asset.metadata.create_all(conn)
        )
        
        # Проверяем результат
        result = await conn.execute(
            text("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        )
        tables = [row[0] for row in result.fetchall()]
        
        print(f"✓ База данных инициализирована")
        print(f"✓ Создано таблиц: {len(tables)}")
        print(f"Таблицы: {', '.join(tables)}")


if __name__ == "__main__":
    try:
        asyncio.run(init_db())
        print("\n✓ Инициализация завершена успешно!")
    except Exception as e:
        print(f"\n✗ Ошибка инициализации: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
