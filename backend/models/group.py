from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Text, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
from backend.db.base import Base


class Group(Base):
    """Модель группы активов."""
    
    __tablename__ = "groups"
    
    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(String(36), unique=True, nullable=False, index=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(255), nullable=False, unique=True, index=True)
    description = Column(Text, nullable=True)
    parent_id = Column(Integer, ForeignKey("groups.id", ondelete="CASCADE"), nullable=True, index=True)
    group_type = Column(String(50), default="manual")  # manual, cidr, dynamic
    is_dynamic = Column(Boolean, default=False)  # Флаг динамической группы
    rule = Column(Text, nullable=True)  # Правило для динамических групп (CIDR или фильтр)
    filter_rules = Column(Text, nullable=True)  # JSON правила фильтрации для динамических групп
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Связи
    parent = relationship("Group", remote_side=[id], backref="children", lazy="joined")
    # Many-to-many связь с активами через таблицу asset_groups
    assets = relationship("Asset", secondary="asset_groups", back_populates="groups")
    scans = relationship("Scan", back_populates="group", cascade="all, delete-orphan")
    
    def to_dict(self):
        """Конвертировать группу в словарь без подсчёта активов.
        
        Для получения количества активов используйте отдельный асинхронный метод сервиса.
        """
        result = {
            'id': self.id,
            'uuid': self.uuid,
            'name': self.name,
            'description': self.description,
            'parent_id': self.parent_id,
            'group_type': self.group_type,
            'is_dynamic': self.is_dynamic,
            'rule': self.rule,
            'filter_rules': self.filter_rules,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }
        
        if hasattr(self, '_children_list') and self._children_list:
            result['children'] = [child.to_dict() for child in self._children_list]
        
        return result
# Алиас для совместимости со старым кодом
AssetGroup = Group
