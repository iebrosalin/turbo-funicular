from pydantic_settings import BaseSettings, SettingsConfigDict
import os
from pathlib import Path

# Определяем базовую директорию проекта (корень репозитория)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Единая директория для всех баз данных
DATA_DIR = "/workspace/data"


class Settings(BaseSettings):
    """Настройки приложения."""

    # База данных - по умолчанию SQLite для локального запуска
    DATABASE_URL: str = ""
    
    # Путь к директории с базами данных
    DATA_DIR: str = DATA_DIR

    # Приложение
    PROJECT_NAME: str = "Network Inventory"
    APP_NAME: str = "Network Inventory"
    DEBUG: bool = True
    VERSION: str = "2.0.0"
    ENVIRONMENT: str = "development"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Создаем директорию для БД если не существует
        os.makedirs(DATA_DIR, exist_ok=True)
        # Устанавливаем DATABASE_URL по умолчанию если не задан
        if not self.DATABASE_URL:
            db_path = os.path.join(DATA_DIR, 'app.db')
            self.DATABASE_URL = f"sqlite+aiosqlite:///{db_path}"


settings = Settings()
