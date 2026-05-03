from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Text, Boolean, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
from backend.db.base import Base


class ActivityLog(Base):
    """Модель лога активности."""
    
    __tablename__ = "activity_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(String(36), unique=True, nullable=False, index=True, default=lambda: str(uuid.uuid4()))
    asset_id = Column(Integer, ForeignKey("assets.id", ondelete="CASCADE"), nullable=True, index=True)
    action = Column(String(100), nullable=False)  # create, update, delete, scan, etc.
    resource_type = Column(String(50), nullable=False)  # asset, group, scan, etc.
    resource_id = Column(Integer, nullable=True)
    details = Column(JSON, nullable=True)  # Детали действия
    ip_address = Column(String(45), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Связи
    asset = relationship("Asset", back_populates="activity_logs")


class AssetChangeLog(Base):
    """Модель журнала изменений актива."""
    
    __tablename__ = "asset_change_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    asset_id = Column(Integer, ForeignKey("assets.id", ondelete="CASCADE"), nullable=False, index=True)
    field_name = Column(String(100), nullable=False)  # Имя изменённого поля
    old_value = Column(Text, nullable=True)  # Старое значение (JSON строка)
    new_value = Column(Text, nullable=True)  # Новое значение (JSON строка)
    changed_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Связь с активом
    asset = relationship("Asset", back_populates="change_logs")
