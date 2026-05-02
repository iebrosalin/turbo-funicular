from sqlalchemy.orm import DeclarativeBase
from datetime import datetime, timezone


class Base(DeclarativeBase):
    """Базовый класс для всех моделей."""
    pass


# Импортируем все модели, чтобы они были зарегистрированы в SQLAlchemy
# Это необходимо для корректной работы relationships с строковыми ссылками
# Импорт выполняется в backend.db.session после определения Base

# Создаем таблицу asset_change_logs напрямую через Base.metadata
# Это обходит необходимость в миграциях Alembic
from sqlalchemy import Table, Column, Integer, String, ForeignKey, DateTime, JSON, Index

# Создаем таблицу сразу при импорте модуля
asset_change_logs_table = Table(
    'asset_change_logs',
    Base.metadata,
    Column('id', Integer, primary_key=True, index=True),
    Column('asset_id', Integer, ForeignKey('assets.id', ondelete='CASCADE'), nullable=False, index=True),
    Column('user_id', Integer, nullable=True),
    Column('username', String(255), nullable=True),
    Column('action', String(50), nullable=False),
    Column('changed_fields', JSON, nullable=True),
    Column('created_at', DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)
)

def init_change_log_table():
    """Пустая функция для обратной совместимости - таблица создается при импорте."""
    return asset_change_logs_table
