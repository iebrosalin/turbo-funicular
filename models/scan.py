from datetime import datetime
from extensions import db
from utils import MOSCOW_TZ

class ScanJob(db.Model):
    """Задание на сканирование (очередь и история запусков)"""
    __tablename__ = 'scan_job'
    
    id = db.Column(db.Integer, primary_key=True)
    scan_type = db.Column(db.String(50), nullable=False, index=True) # nmap, rustscan, dig
    target = db.Column(db.String(500), nullable=False) # IP, диапазон или домен
    
    status = db.Column(db.String(20), default='pending', index=True) # pending, running, completed, failed, stopped, cancelled
    progress = db.Column(db.Integer, default=0) # Процент выполнения 0-100
    
    parameters = db.Column(db.JSON) # Параметры запуска (порты, скрипты, аргументы)
    
    output_file = db.Column(db.String(500)) # Путь к основному файлу вывода
    error_message = db.Column(db.Text)
    
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(MOSCOW_TZ))
    started_at = db.Column(db.DateTime)
    completed_at = db.Column(db.DateTime)
    
    # Связь с результатами
    results = db.relationship('ScanResult', back_populates='job', cascade='all, delete-orphan')
    
    def to_dict(self):
        return {
            'id': self.id,
            'scan_type': self.scan_type,
            'target': self.target,
            'status': self.status,
            'progress': self.progress,
            'parameters': self.parameters,
            'error_message': self.error_message,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None
        }

class ScanResult(db.Model):
    """Результаты конкретного сканирования хоста"""
    __tablename__ = 'scan_result'
    
    id = db.Column(db.Integer, primary_key=True)
    job_id = db.Column(db.Integer, db.ForeignKey('scan_job.id'), nullable=False, index=True)
    asset_id = db.Column(db.Integer, db.ForeignKey('asset.id', ondelete='CASCADE'), nullable=True, index=True) # Может быть null если актив не создан/найден
        
    asset_ip = db.Column(db.String(45), index=True)
    hostname = db.Column(db.String(255))
    
    os_match = db.Column(db.String(200))
    os_accuracy = db.Column(db.Integer)
    
    ports = db.Column(db.JSON, default=list) # Список портов из этого сканирования
    raw_output = db.Column(db.Text) # Сырой вывод (xml для nmap, text для других)
    
    scanned_at = db.Column(db.DateTime, default=lambda: datetime.now(MOSCOW_TZ))
    
    job = db.relationship('ScanJob', back_populates='results')
    asset = db.relationship('Asset', back_populates='scan_results')