from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Text, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base import Base


class Group(Base):
    """Модель группы активов."""
    
    __tablename__ = "groups"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, unique=True, index=True)
    description = Column(Text, nullable=True)
    parent_id = Column(Integer, ForeignKey("groups.id", ondelete="CASCADE"), nullable=True, index=True)
    group_type = Column(String(50), default="manual")  # manual, cidr, dynamic
    rule = Column(Text, nullable=True)  # Правило для динамических групп (CIDR или фильтр)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Связи
    parent = relationship("Group", remote_side=[id], backref="children", lazy="joined")
    assets = relationship("Asset", back_populates="group", cascade="all, delete-orphan")
    scans = relationship("Scan", back_populates="group", cascade="all, delete-orphan")
