# models/group.py
from datetime import datetime
from extensions import db
from utils import MOSCOW_TZ

from .base import asset_groups

class AssetGroup(db.Model):
    """Группа активов (например, по отделам, локациям или функциям)"""
    __tablename__ = 'asset_group'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False, index=True)
    description = db.Column(db.Text)
    
    # Иерархия: ссылка на родительскую группу
    parent_id = db.Column(db.Integer, db.ForeignKey('asset_group.id'), nullable=True, index=True)
       # Динамические группы
    is_dynamic = db.Column(db.Boolean, default=False)
    filter_rules = db.Column(db.Text)  # JSON с правилами фильтрации
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(MOSCOW_TZ))
    
    # Связь с родительской группой (обратная связь)
    parent = db.relationship(
        'AssetGroup',
        backref=db.backref('children', lazy='dynamic'),
        remote_side='AssetGroup.id',
        foreign_keys=[parent_id]
    )
    
    # Связь с активами
    assets = db.relationship('Asset', secondary=asset_groups, back_populates='groups')
    
    def to_dict(self, include_children=False):
        """
        Преобразование в словарь.
        :param include_children: Если True, рекурсивно включает дочерние группы.
        """
        import json

        # Парсим filter_rules из JSON строки если есть
        parsed_filter_rules = None
        if self.filter_rules:
            try:
                parsed_filter_rules = json.loads(self.filter_rules)
            except (json.JSONDecodeError, TypeError):
                parsed_filter_rules = []

        data = {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'parent_id': self.parent_id,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'assets_count': len(self.assets),
            'is_dynamic': self.is_dynamic,
            'filter_rules': parsed_filter_rules or []
        }
        
        if include_children and self.children:
            data['children'] = [child.to_dict(include_children=True) for child in self.children]
            
        return data