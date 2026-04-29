from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Базовый класс для всех моделей."""
    pass


# Импортируем все модели, чтобы они были зарегистрированы в SQLAlchemy
# Это необходимо для корректной работы relationships с строковыми ссылками
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import models
