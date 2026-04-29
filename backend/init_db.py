"""
Скрипт инициализации базы данных.
Создает все таблицы, определенные в моделях SQLAlchemy.
"""
import sys
from pathlib import Path

# Добавляем корневую директорию в путь
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import create_engine
from db.base import Base  # Импортирует все модели
from core.config import settings


def init_db():
    """Инициализирует базу данных, создавая все таблицы."""
    # Преобразуем async URL в sync для создания таблиц
    db_url = settings.DATABASE_URL.replace("+asyncpg", "").replace("+aiosqlite", "")
    
    print(f"🔌 Подключение к базе данных: {db_url}")
    
    engine = create_engine(
        db_url,
        echo=False,
        connect_args={"check_same_thread": False} if "sqlite" in db_url else {}
    )
    
    try:
        # Создаем все таблицы
        Base.metadata.create_all(bind=engine)
        print("✅ База данных успешно инициализирована.")
        print("✅ Все таблицы созданы.")
    except Exception as e:
        print(f"❌ Ошибка инициализации базы данных: {e}")
        raise


if __name__ == "__main__":
    init_db()
