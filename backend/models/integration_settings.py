"""
Модель для хранения настроек интеграций
"""
from sqlalchemy import Column, Integer, String, Boolean, Integer, DateTime, Text
from sqlalchemy.sql import func
from backend.db.base import Base


class IntegrationSettings(Base):
    """Настройки интеграций с внешними системами"""
    __tablename__ = "integration_settings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), unique=True, nullable=False, comment="Название интеграции (например, redcheck)")
    api_url = Column(String(500), nullable=True, comment="URL API")
    api_version = Column(String(50), nullable=True, default="v1.0", comment="Версия API")
    username = Column(String(200), nullable=True, comment="Имя пользователя")
    password = Column(String(200), nullable=True, comment="Пароль (в реальном проекте нужно шифровать)")
    auth_type = Column(String(50), nullable=True, default="basic", comment="Тип аутентификации")
    timeout = Column(Integer, nullable=True, default=30, comment="Таймаут запросов в секундах")
    verify_ssl = Column(Boolean, nullable=True, default=True, comment="Проверка SSL сертификата")
    enabled = Column(Boolean, nullable=True, default=False, comment="Включена ли интеграция")
    extra_config = Column(Text, nullable=True, comment="Дополнительные настройки в JSON формате")
    created_at = Column(DateTime, server_default=func.now(), comment="Дата создания")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="Дата обновления")
