"""
Скрипт миграции базы данных для переименования external_id в redcheck_guid
"""
import sys
from pathlib import Path

# Добавляем корневую директорию в путь
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import create_engine, text
from backend.core.config import settings


def migrate_external_id_to_redcheck_guid():
    """Миграция: переименование колонки external_id в redcheck_guid в таблице redcheck_hosts"""
    # Преобразуем async URL в sync для работы с SQLAlchemy Core
    db_url = settings.DATABASE_URL.replace("+asyncpg", "").replace("+aiosqlite", "")
    
    print(f"🔌 Подключение к базе данных: {db_url}")
    
    engine = create_engine(
        db_url,
        echo=False,
        connect_args={"check_same_thread": False} if "sqlite" in db_url else {}
    )
    
    with engine.connect() as conn:
        try:
            # Проверяем, существует ли таблица redcheck_hosts
            result = conn.execute(text("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='redcheck_hosts'
            """)).fetchone()
            
            if not result:
                print("ℹ️ Таблица redcheck_hosts не найдена. Миграция не требуется.")
                return
            
            # Проверяем, существует ли колонка external_id
            columns_result = conn.execute(text("PRAGMA table_info(redcheck_hosts)")).fetchall()
            column_names = [col[1] for col in columns_result]
            
            if 'external_id' not in column_names:
                if 'redcheck_guid' in column_names:
                    print("✅ Колонка redcheck_guid уже существует. Миграция не требуется.")
                else:
                    print("❌ Колонка external_id не найдена и redcheck_guid отсутствует.")
                return
            
            if 'redcheck_guid' in column_names:
                print("⚠️ Колонка redcheck_guid уже существует. Пропускаем создание.")
            else:
                # SQLite не поддерживает прямое переименование колонки с изменением типа
                # Создаем новую колонку redcheck_guid
                print("📝 Создание колонки redcheck_guid...")
                conn.execute(text("""
                    ALTER TABLE redcheck_hosts 
                    ADD COLUMN redcheck_guid VARCHAR(100)
                """))
                conn.commit()
                print("✅ Колонка redcheck_guid создана.")
            
            # Копируем данные из external_id в redcheck_guid
            print("📝 Копирование данных из external_id в redcheck_guid...")
            conn.execute(text("""
                UPDATE redcheck_hosts 
                SET redcheck_guid = external_id 
                WHERE redcheck_guid IS NULL
            """))
            conn.commit()
            print("✅ Данные скопированы.")
            
            # В SQLite нет прямого DROP COLUMN в старых версиях, но в новых (3.35+) есть
            # Для совместимости просто помечаем old колонку как неиспользуемую
            # Или пробуем удалить, если версия SQLite позволяет
            try:
                print("📝 Удаление старой колонки external_id...")
                conn.execute(text("""
                    ALTER TABLE redcheck_hosts 
                    DROP COLUMN external_id
                """))
                conn.commit()
                print("✅ Колонка external_id удалена.")
            except Exception as e:
                print(f"⚠️ Не удалось удалить колонку external_id (возможно, старая версия SQLite): {e}")
                print("   Колонка будет проигнорирована приложением.")
            
            # Создаем индекс на redcheck_guid, если его нет
            print("📝 Создание индекса на redcheck_guid...")
            try:
                conn.execute(text("""
                    CREATE INDEX IF NOT EXISTS ix_redcheck_hosts_redcheck_guid 
                    ON redcheck_hosts (redcheck_guid)
                """))
                conn.commit()
                print("✅ Индекс создан.")
            except Exception as e:
                print(f"⚠️ Не удалось создать индекс: {e}")
            
            # Создаем уникальный индекс
            print("📝 Создание уникального индекса на redcheck_guid...")
            try:
                conn.execute(text("""
                    CREATE UNIQUE INDEX IF NOT EXISTS uq_redcheck_hosts_redcheck_guid 
                    ON redcheck_hosts (redcheck_guid)
                """))
                conn.commit()
                print("✅ Уникальный индекс создан.")
            except Exception as e:
                print(f"⚠️ Не удалось создать уникальный индекс: {e}")
            
            print("\n✅ Миграция успешно завершена!")
            print("   external_id → redcheck_guid")
            
        except Exception as e:
            print(f"❌ Ошибка миграции: {e}")
            raise


if __name__ == "__main__":
    migrate_external_id_to_redcheck_guid()
