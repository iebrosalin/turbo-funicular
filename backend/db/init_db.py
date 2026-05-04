#!/usr/bin/env python3
"""
Скрипт инициализации базы данных.
Создает все таблицы если они не существуют и создает корневую группу "Организация".
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
    from backend.db.session import asset_change_logs_table
    
    async with engine.begin() as conn:
        # Создаем все таблицы ORM
        await conn.run_sync(
            lambda conn: Asset.metadata.create_all(conn)
        )
        
        # Создаем таблицу asset_change_logs вручную (Core API)
        await conn.run_sync(
            lambda conn: asset_change_logs_table.create(conn, checkfirst=True)
        )
        
        # Проверяем результат
        result = await conn.execute(
            text("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        )
        tables = [row[0] for row in result.fetchall()]
        
        print(f"✓ База данных инициализирована")
        print(f"✓ Создано таблиц: {len(tables)}")
        print(f"Таблицы: {', '.join(tables)}")
        
        # Создаем корневую группу "Организация" если она не существует
        from sqlalchemy import select
        from backend.models.group import Group as AssetGroup
        
        query = select(AssetGroup).where(AssetGroup.description == "__root_organization__")
        root_result = await conn.execute(query)
        root_group = root_result.scalar_one_or_none()
        
        if not root_group:
            # Вставляем корневую группу
            insert_query = text("""
                INSERT INTO groups (uuid, name, description, parent_id, group_type, is_dynamic, created_at)
                VALUES (:uuid, :name, :description, :parent_id, :group_type, :is_dynamic, datetime('now'))
            """)
            import uuid
            await conn.execute(
                insert_query,
                {
                    "uuid": str(uuid.uuid4()),
                    "name": "Организация",
                    "description": "__root_organization__",
                    "parent_id": None,
                    "group_type": "manual",
                    "is_dynamic": False
                }
            )
            print(f"✓ Создана корневая группа 'Организация'")
        else:
            print(f"✓ Корневая группа 'Организация' уже существует")


if __name__ == "__main__":
    try:
        asyncio.run(init_db())
        print("\n✓ Инициализация завершена успешно!")
    except Exception as e:
        print(f"\n✗ Ошибка инициализации: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
