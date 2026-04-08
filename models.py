# models.py
import json
from datetime import datetime
from extensions import db

class Group(db.Model):
    __tablename__ = 'group'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    parent_id = db.Column(db.Integer, db.ForeignKey('group.id'), nullable=True)
    filter_query = db.Column(db.Text, nullable=True)
    is_dynamic = db.Column(db.Boolean, default=False)
    children = db.relationship('Group', backref=db.backref('parent', remote_side=[id]))
    assets = db.relationship('Asset', backref='group', lazy=True)
    def __repr__(self): return f'<Group {self.name}>'

class Asset(db.Model):
    __tablename__ = 'asset'
    id = db.Column(db.Integer, primary_key=True)
    ip_address = db.Column(db.String(50), nullable=False, index=True)
    hostname = db.Column(db.String(255))
    os_info = db.Column(db.String(255))
    status = db.Column(db.String(20), default='up')
    open_ports = db.Column(db.Text)
    last_scanned = db.Column(db.DateTime, default=datetime.utcnow)
    notes = db.Column(db.Text)
    group_id = db.Column(db.Integer, db.ForeignKey('group.id'), nullable=True)
    def __repr__(self): return f'<Asset {self.ip_address}>'

class ScanJob(db.Model):
    __tablename__ = 'scan_job'
    id = db.Column(db.Integer, primary_key=True)
    scan_type = db.Column(db.String(20), nullable=False)
    target = db.Column(db.String(500), nullable=False)
    status = db.Column(db.String(20), default='pending')
    progress = db.Column(db.Integer, default=0)
    started_at = db.Column(db.DateTime)
    completed_at = db.Column(db.DateTime)
    error_message = db.Column(db.Text)
    rustscan_output = db.Column(db.Text)
    nmap_xml_path = db.Column(db.String(500))
    nmap_grep_path = db.Column(db.String(500))
    nmap_normal_path = db.Column(db.String(500))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    def to_dict(self):
        return {
            'id': self.id, 'scan_type': self.scan_type, 'target': self.target,
            'status': self.status, 'progress': self.progress,
            'started_at': self.started_at.strftime('%Y-%m-%d %H:%M:%S') if self.started_at else None,
            'completed_at': self.completed_at.strftime('%Y-%m-%d %H:%M:%S') if self.completed_at else None,
            'error_message': self.error_message,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S')
        }

class ScanResult(db.Model):
    __tablename__ = 'scan_result'
    id = db.Column(db.Integer, primary_key=True)
    asset_id = db.Column(db.Integer, db.ForeignKey('asset.id'), nullable=True)
    ip_address = db.Column(db.String(50), nullable=False)
    scan_job_id = db.Column(db.Integer, db.ForeignKey('scan_job.id'))
    ports = db.Column(db.Text)
    services = db.Column(db.Text)
    os_detection = db.Column(db.String(255))
    scanned_at = db.Column(db.DateTime, default=datetime.utcnow)
    job = db.relationship('ScanJob', backref='results')
    asset = db.relationship('Asset', backref='scan_results')

class AssetChangeLog(db.Model):
    __tablename__ = 'asset_change_log'
    id = db.Column(db.Integer, primary_key=True)
    asset_id = db.Column(db.Integer, db.ForeignKey('asset.id'), nullable=False)
    changed_at = db.Column(db.DateTime, default=datetime.utcnow)
    change_type = db.Column(db.String(50), nullable=False)
    field_name = db.Column(db.String(100))
    old_value = db.Column(db.Text)
    new_value = db.Column(db.Text)
    scan_job_id = db.Column(db.Integer, db.ForeignKey('scan_job.id'))
    notes = db.Column(db.Text)
    asset = db.relationship('Asset', backref='change_log')
    scan_job = db.relationship('ScanJob', backref='change_logs')
    def to_dict(self):
        return {
            'id': self.id, 'asset_id': self.asset_id,
            'changed_at': self.changed_at.strftime('%Y-%m-%d %H:%M:%S'),
            'change_type': self.change_type, 'field_name': self.field_name,
            'old_value': json.loads(self.old_value) if self.old_value else None,
            'new_value': json.loads(self.new_value) if self.new_value else None,
            'scan_job_id': self.scan_job_id, 'notes': self.notes
        }

class ServiceInventory(db.Model):
    __tablename__ = 'service_inventory'
    id = db.Column(db.Integer, primary_key=True)
    asset_id = db.Column(db.Integer, db.ForeignKey('asset.id'), nullable=False)
    port = db.Column(db.String(20), nullable=False)
    protocol = db.Column(db.String(10))
    service_name = db.Column(db.String(100))
    product = db.Column(db.String(255))
    version = db.Column(db.String(255))
    extrainfo = db.Column(db.String(500))
    cpe = db.Column(db.String(500))
    script_output = db.Column(db.Text)
    first_seen = db.Column(db.DateTime, default=datetime.utcnow)
    last_seen = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)
    asset = db.relationship('Asset', backref='service_inventory')
    def to_dict(self):
        return {
            'id': self.id, 'port': self.port, 'protocol': self.protocol,
            'service_name': self.service_name, 'product': self.product, 'version': self.version,
            'extrainfo': self.extrainfo, 'cpe': self.cpe, 'script_output': self.script_output,
            'first_seen': self.first_seen.strftime('%Y-%m-%d %H:%M:%S'),
            'last_seen': self.last_seen.strftime('%Y-%m-%d %H:%M:%S'), 'is_active': self.is_active
        }