#!/usr/bin/env python3
"""
Скрипт инициализации базы данных.
Создает все таблицы если они не существуют и создает корневую группу.
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
    from backend.models import Asset, Group, Scan, ScanJob, ScanResult, ActivityLog, ServiceInventory, IntegrationSettings
    from backend.db.session import asset_change_logs_table
    
    async with engine.begin() as conn:
        # Удаляем старую таблицу scan_results если она существует (для пересоздания с новыми колонками)
        await conn.execute(text("DROP TABLE IF EXISTS scan_results"))
        print("✓ Удалена старая таблица scan_results (будет пересоздана)")
        
        # Удаляем старую таблицу integration_settings для пересоздания с новыми колонками
        await conn.execute(text("DROP TABLE IF EXISTS integration_settings"))
        print("✓ Удалена старая таблица integration_settings (будет пересоздана)")
        
        # Создаем все таблицы ORM
        await conn.run_sync(
            lambda conn: Asset.metadata.create_all(conn)
        )
        
        # Создаем таблицу asset_change_logs вручную (Core API)
        await conn.run_sync(
            lambda conn: asset_change_logs_table.create(conn, checkfirst=True)
        )
        
        # Создаем индексы для asset_change_logs
        await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_asset_change_logs_asset_id ON asset_change_logs(asset_id)"))
        await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_asset_change_logs_created_at ON asset_change_logs(created_at)"))
        
        # Проверяем результат
        result = await conn.execute(
            text("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        )
        tables = [row[0] for row in result.fetchall()]
        
        print(f"✓ База данных инициализирована")
        print(f"✓ Создано таблиц: {len(tables)}")
        print(f"Таблицы: {', '.join(tables)}")
        
        # Создаем корневую группу если она не существует
        from sqlalchemy import select
        from backend.models.group import Group as AssetGroup
        
        # Сначала пытаемся найти группу с id=0
        query = select(AssetGroup).where(AssetGroup.id == 0)
        result = await conn.execute(query)
        root_group = result.mappings().first()
        
        if not root_group:
            # Вставляем корневую группу с id=0
            insert_query = text("""
                INSERT INTO groups (id, uuid, name, parent_id, group_type, is_dynamic, created_at)
                VALUES (0, :uuid, :name, :parent_id, :group_type, :is_dynamic, datetime('now'))
            """)
            import uuid
            await conn.execute(
                insert_query,
                {
                    "uuid": str(uuid.uuid4()),
                    "name": "Root",
                    "parent_id": None,
                    "group_type": "manual",
                    "is_dynamic": False
                }
            )
            print(f"✓ Создана корневая группа с ID 0")
        else:
            update_query = text("UPDATE groups SET name = :name, description = NULL WHERE id = 0")
            await conn.execute(update_query, {"name": "Root"})
            print(f"✓ Корневая группа уже существует (ID: {root_group['id']}), имя обновлено на Root")


if __name__ == "__main__":
    try:
        asyncio.run(init_db())
        print("\n✓ Инициализация завершена успешно!")
    except Exception as e:
        print(f"\n✗ Ошибка инициализации: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
