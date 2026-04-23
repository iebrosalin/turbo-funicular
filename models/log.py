from datetime import datetime
from extensions import db
from utils import MOSCOW_TZ

class ActivityLog(db.Model):
    """Лог изменений и событий системы"""
    __tablename__ = 'activity_log'
    
    id = db.Column(db.Integer, primary_key=True)
    asset_id = db.Column(db.Integer, db.ForeignKey('asset.id', ondelete='CASCADE'), index=True)

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
    
class AssetChangeLog(db.Model):
    """Лог изменений активов"""
    __tablename__ = 'asset_change_log'

    id = db.Column(db.Integer, primary_key=True)
    asset_id = db.Column(db.Integer, db.ForeignKey('asset.id', ondelete='CASCADE'), index=True)
    
    change_type = db.Column(db.String(50))  # type of change
    field_name = db.Column(db.String(100))  # which field changed
    old_value = db.Column(db.Text)  # previous value (JSON string)
    new_value = db.Column(db.Text)  # new value (JSON string)

    scan_job_id = db.Column(db.Integer, db.ForeignKey('scan_job.id'))
    notes = db.Column(db.Text)

    changed_at = db.Column(db.DateTime, default=lambda: datetime.now(MOSCOW_TZ), index=True)

    asset = db.relationship('Asset', backref=db.backref('change_logs', cascade='all, delete-orphan'))
    scan_job = db.relationship('ScanJob', backref='change_logs')

    def to_dict(self):
        return {
            'id': self.id,
            'asset_id': self.asset_id,
            'change_type': self.change_type,
            'field_name': self.field_name,
            'old_value': self.old_value,
            'new_value': self.new_value,
            'scan_job_id': self.scan_job_id,
            'notes': self.notes,
            'changed_at': self.changed_at.isoformat() if self.changed_at else None
        }