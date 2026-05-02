from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Text, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
from backend.db.base import Base


class ServiceInventory(Base):
    """Модель сервиса на порту (детальная информация)."""
    
    __tablename__ = "service_inventory"
    
    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(String(36), unique=True, nullable=False, index=True, default=lambda: str(uuid.uuid4()))
    asset_id = Column(Integer, ForeignKey("assets.id", ondelete="CASCADE"), nullable=False, index=True)
    port = Column(Integer, nullable=False)
    protocol = Column(String(10), default="tcp")  # tcp, udp
    state = Column(String(50), default="open")  # open, closed, filtered
    service_name = Column(String(100), nullable=True)  # http, ssh, etc.
    product = Column(String(255), nullable=True)  # Продукт (nginx, OpenSSH)
    version = Column(String(255), nullable=True)  # Версия продукта
    extra_info = Column(Text, nullable=True)  # Дополнительная информация
    ostype = Column(String(100), nullable=True)  # Тип ОС
    devicetype = Column(String(100), nullable=True)  # Тип устройства
    
    # SSL информация (алиасы для совместимости)
    ssl_cert_subject = Column(Text, nullable=True)
    ssl_cert_issuer = Column(Text, nullable=True)
    ssl_cert_not_before = Column(DateTime(timezone=True), nullable=True)
    ssl_cert_not_after = Column(DateTime(timezone=True), nullable=True)
    ssl_cert_serial = Column(String(255), nullable=True)
    
    # Алиасы для совместимости с шаблоном
    @property
    def ssl_subject(self):
        return self.ssl_cert_subject
    
    @property
    def ssl_issuer(self):
        return self.ssl_cert_issuer
    
    @property
    def ssl_not_before(self):
        return self.ssl_cert_not_before
    
    @property
    def ssl_not_after(self):
        return self.ssl_cert_not_after
    
    # Scripts Nmap
    scripts = Column(JSON, nullable=True, default=list)  # Результаты NSE скриптов
    
    @property
    def script_output(self):
        return self.scripts
    
    # Временные метки
    last_seen = Column(DateTime(timezone=True), nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Связи
    asset = relationship("Asset", back_populates="services")
