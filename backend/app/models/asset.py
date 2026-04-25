from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Text, Boolean, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base import Base


class Asset(Base):
    """Модель актива (хоста/IP)."""
    
    __tablename__ = "assets"
    
    id = Column(Integer, primary_key=True, index=True)
    ip_address = Column(String(45), nullable=False, index=True)  # Поддержка IPv6
    hostname = Column(String(255), nullable=True)
    mac_address = Column(String(17), nullable=True)
    os_info = Column(String(255), nullable=True)
    group_id = Column(Integer, ForeignKey("groups.id", ondelete="SET NULL"), nullable=True, index=True)
    status = Column(String(50), default="active")  # active, inactive, unknown
    last_seen = Column(DateTime(timezone=True), server_default=func.now())
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    notes = Column(Text, nullable=True)
    
    # Связи
    group = relationship("Group", back_populates="assets")
    
    # Индексы
    __table_args__ = (
        Index('ix_assets_ip_group', 'ip_address', 'group_id'),
    )
