from datetime import datetime
from extensions import db
from utils import MOSCOW_TZ

class ActivityLog(db.Model):
    """Лог изменений и событий системы"""
    __tablename__ = 'activity_log'
    
    id = db.Column(db.Integer, primary_key=True)
    asset_id = db.Column(db.Integer, db.ForeignKey('asset.id'), index=True)
    
    event_type = db.Column(db.String(50), index=True) # port_discovered, service_detected, os_changed, scan_completed
    description = db.Column(db.Text, nullable=False)
    details = db.Column(db.JSON) # Детали изменения (старое/новое значение)
    
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(MOSCOW_TZ), index=True)
    
    asset = db.relationship('Asset', back_populates='activity_logs')
    
    def to_dict(self):
        return {
            'id': self.id,
            'asset_id': self.asset_id,
            'event_type': self.event_type,
            'description': self.description,
            'details': self.details,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }