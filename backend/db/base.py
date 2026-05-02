from sqlalchemy.orm import DeclarativeBase
from datetime import datetime, timezone


class Base(DeclarativeBase):
    """Базовый класс для всех моделей."""
    pass


# Импортируем все модели, чтобы они были зарегистрированы в SQLAlchemy
# Это необходимо для корректной работы relationships с строковыми ссылками
# Импорт выполняется в backend.db.session после определения Base
