from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
from backend.db.base import Base


class AssetChangeLog(Base):
    """Лог изменений актива"""
    
    __tablename__ = 'asset_change_logs'

    id = Column(Integer, primary_key=True, index=True)
    asset_id = Column(Integer, ForeignKey('assets.id', ondelete='CASCADE'), nullable=False, index=True)
    user_id = Column(Integer, nullable=True)  # ID пользователя (если есть система авторизации)
    username = Column(String(255), nullable=True)  # Имя пользователя
    action = Column(String(50), nullable=False)  # 'create', 'update', 'delete'
    changed_fields = Column(JSON, nullable=True)  # {'field_name': {'old': ..., 'new': ...}}
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, index=True)

    # Связь с активом
    asset = relationship('Asset', back_populates='change_logs')

    def to_dict(self):
        return {
            'id': self.id,
            'asset_id': self.asset_id,
            'user_id': self.user_id,
            'username': self.username,
            'action': self.action,
            'changed_fields': self.changed_fields,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
