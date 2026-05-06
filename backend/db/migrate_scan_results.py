#!/usr/bin/env python3
"""
Миграция: Добавление колонок output_xml, output_gnmap, output_normal, output_json в таблицу scan_results
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.db.session import engine
from sqlalchemy import text


async def migrate():
    """Добавление отсутствующих колонок в таблицу scan_results."""
    async with engine.begin() as conn:
        # Проверяем существующие колонки
        result = await conn.execute(text("PRAGMA table_info(scan_results)"))
        columns = [row[1] for row in result.fetchall()]
        
        print(f"Существующие колонки: {columns}")
        
        # Колонки для добавления
        new_columns = [
            ("output_xml", "TEXT"),
            ("output_gnmap", "TEXT"),
            ("output_normal", "TEXT"),
            ("output_json", "JSON"),
        ]
        
        added = []
        for col_name, col_type in new_columns:
            if col_name not in columns:
                alter_sql = f"ALTER TABLE scan_results ADD COLUMN {col_name} {col_type}"
                await conn.execute(text(alter_sql))
                added.append(col_name)
                print(f"✓ Добавлена колонка: {col_name}")
            else:
                print(f"- Колонка {col_name} уже существует")
        
        if added:
            print(f"\n✓ Миграция завершена. Добавлено колонок: {len(added)}")
        else:
            print("\n- Все колонки уже существуют, миграция не требуется")


if __name__ == "__main__":
    try:
        asyncio.run(migrate())
        print("\n✓ Миграция завершена успешно!")
    except Exception as e:
        print(f"\n✗ Ошибка миграции: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
