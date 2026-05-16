from pydantic_settings import BaseSettings, SettingsConfigDict
import os
from pathlib import Path

# Определяем базовую директорию проекта (корень репозитория)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Директория instance в корне проекта для хранения SQLite базы
INSTANCE_DIR = os.path.join(BASE_DIR, 'instance')
os.makedirs(INSTANCE_DIR, exist_ok=True)


class Settings(BaseSettings):
    """Настройки приложения."""

    # База данных - по умолчанию SQLite для локального запуска
    DATABASE_URL: str = ""
    
    # Путь к директории instance
    INSTANCE_DIR: str = INSTANCE_DIR

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
        # Устанавливаем DATABASE_URL по умолчанию если не задан
        if not self.DATABASE_URL:
            self.DATABASE_URL = f"sqlite+aiosqlite:///{os.path.join(self.INSTANCE_DIR, 'app.db')}"


settings = Settings()
