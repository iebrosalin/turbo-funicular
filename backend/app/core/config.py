from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Настройки приложения."""
    
    # База данных
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@db:5432/netinventory"
    
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
