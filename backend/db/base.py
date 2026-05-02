from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, JSON
from datetime import datetime, timezone


class Base(DeclarativeBase):
    """Базовый класс для всех моделей."""
    pass


# Таблица для логирования изменений активов (Core API)
asset_change_logs_table = None  # Будет определена после импорта моделей


# Импортируем все модели, чтобы они были зарегистрированы в SQLAlchemy
# Это необходимо для корректной работы relationships с строковыми ссылками
# Импорт выполняется в backend.db.session после определения Base
