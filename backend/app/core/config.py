from pydantic_settings import BaseSettings, SettingsConfigDict
import os

# Определяем базовую директорию проекта (backend)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Создаем директорию instance если не существует (для SQLite)
INSTANCE_DIR = os.path.join(BASE_DIR, 'instance')
os.makedirs(INSTANCE_DIR, exist_ok=True)


class Settings(BaseSettings):
    """Настройки приложения."""

    # База данных - по умолчанию SQLite для локального запуска
    DATABASE_URL: str = f"sqlite+aiosqlite:///{os.path.join(INSTANCE_DIR, 'network_inventory.db')}"

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


settings = Settings()
