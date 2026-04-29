from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Text, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from backend.db.base import Base


class Group(Base):
    """Модель группы активов."""
    
    __tablename__ = "groups"
    
    id = Column(Integer, primary_key=True, index=True)
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
    
    def to_dict(self, include_children=False):
        """Конвертировать группу в словарь с подсчётом активов."""
        from sqlalchemy import select, func
        from db.session import get_sync_session
        from models.asset import asset_groups
        
        result = {
            'id': self.id,
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
        
        # Подсчёт активов через many-to-many связь
        try:
            with get_sync_session() as session:
                stmt = select(func.count(asset_groups.c.asset_id)).where(
                    asset_groups.c.group_id == self.id
                )
                assets_count = session.scalar(stmt)
                result['assets_count'] = assets_count or 0
        except Exception:
            result['assets_count'] = 0
        
        if include_children and hasattr(self, 'children') and self.children:
            result['children'] = [child.to_dict(include_children=True) for child in self.children]
        
        return result
# Алиас для совместимости со старым кодом
AssetGroup = Group
