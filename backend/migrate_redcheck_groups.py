"""
Миграция: создание таблицы redcheck_host_groups для many-to-many связи
между RedCheck хостами и группами.
"""
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy import text
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/asset_db")

async def migrate():
    engine = create_async_engine(DATABASE_URL, echo=False)
    
    async with engine.begin() as conn:
        # Создаём таблицу связи если она не существует
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS redcheck_host_groups (
                redcheck_host_id INTEGER NOT NULL,
                group_id INTEGER NOT NULL,
                PRIMARY KEY (redcheck_host_id, group_id),
                FOREIGN KEY (redcheck_host_id) REFERENCES redcheck_hosts(id) ON DELETE CASCADE,
                FOREIGN KEY (group_id) REFERENCES groups(id) ON DELETE CASCADE
            )
        """))
        
        # Проверяем, есть ли колонка groups в таблице redcheck_hosts (старая текстовая колонка)
        result = await conn.execute(text("""
            SELECT column_name FROM information_schema.columns 
            WHERE table_name = 'redcheck_hosts' AND column_name = 'groups'
        """))
        columns = result.fetchall()
        
        if columns:
            print("⚠️  Обнаружена старая колонка 'groups' в таблице redcheck_hosts")
            print("   Она будет удалена после переноса данных (если данные есть)")
            
            # Проверяем, есть ли данные в старой колонке
            data_result = await conn.execute(text("""
                SELECT COUNT(*) FROM redcheck_hosts WHERE groups IS NOT NULL AND groups != ''
            """))
            count = data_result.scalar()
            
            if count > 0:
                print(f"   Найдено {count} записей со старыми данными групп")
                print("   ⚠️  Внимание: данные в формате CSV не будут автоматически перенесены")
                print("   Рекомендуется выполнить синхронизацию с RedCheck заново")
            
            # Удаляем старую колонку
            try:
                await conn.execute(text("ALTER TABLE redcheck_hosts DROP COLUMN groups"))
                print("✅ Старая колонка 'groups' удалена")
            except Exception as e:
                print(f"⚠️  Не удалось удалить старую колонку: {e}")
        
        print("✅ Таблица redcheck_host_groups создана/обновлена")

if __name__ == "__main__":
    asyncio.run(migrate())
