# models/asset.py
"""
Модель сетевого актива (хост, сервер, устройство).
"""
from datetime import datetime
from extensions import db
from utils import MOSCOW_TZ

# Импортируем таблицу связи из base, чтобы избежать циклического импорта при импорте AssetGroup
from .base import asset_groups

class Asset(db.Model):
    """Сетевой актив (хост, сервер, устройство)"""
    __tablename__ = 'asset'
    
    id = db.Column(db.Integer, primary_key=True)
    ip_address = db.Column(db.String(45), unique=True, nullable=False, index=True) # Поддержка IPv6
    hostname = db.Column(db.String(255), index=True)
    
    # Основная информация
    os_family = db.Column(db.String(50), index=True) # Linux, Windows, etc.
    os_version = db.Column(db.String(100))
    device_type = db.Column(db.String(50), default='unknown', index=True) # server, workstation, network_device
    
    # Статус и метаданные
    status = db.Column(db.String(20), default='active', index=True) # active, inactive, archived
    location = db.Column(db.String(100))
    owner = db.Column(db.String(100))
    
    # DNS данные
    dns_names = db.Column(db.JSON, default=list) # Список всех найденных имен
    fqdn = db.Column(db.String(255)) # Основное полное доменное имя
    dns_records = db.Column(db.JSON, default=dict) # Словарь записей: {'A': [...], 'MX': [...], ...}
    
    # Порты (разделение по источникам)
    rustscan_ports = db.Column(db.JSON, default=list)
    nmap_ports = db.Column(db.JSON, default=list)
    open_ports = db.Column(db.JSON, default=list) # Объединенный список портов
    
    # Временные метки сканирований
    last_rustscan = db.Column(db.DateTime)
    last_nmap = db.Column(db.DateTime)
    last_dns_scan = db.Column(db.DateTime)
    
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(MOSCOW_TZ))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(MOSCOW_TZ), onupdate=lambda: datetime.now(MOSCOW_TZ))
    
    # Связи
    # secondary=asset_groups связывает с AssetGroup через таблицу многие-ко-многим
    groups = db.relationship('AssetGroup', secondary=asset_groups, back_populates='assets')
    
    # Прямые связи один-ко-многим с каскадным удалением
    services = db.relationship('ServiceInventory', back_populates='asset', cascade='all, delete-orphan')
    scan_results = db.relationship('ScanResult', back_populates='asset', cascade='all, delete-orphan')
    activity_logs = db.relationship('ActivityLog', back_populates='asset', cascade='all, delete-orphan')
    
    # Связь с OsqueryInventory (один к одному, uselist=False)
    osquery_data = db.relationship('OsqueryInventory', back_populates='asset', uselist=False, cascade='all, delete-orphan')
    
    def update_ports(self, source, ports_data):
        """Обновление портов из указанного источника"""
        if source == 'rustscan':
            self.rustscan_ports = ports_data
            self.last_rustscan = datetime.now(MOSCOW_TZ)
        elif source == 'nmap':
            # ports_data может быть списком портов или списком словарей
            if isinstance(ports_data, list) and ports_data and isinstance(ports_data[0], dict):
                self.nmap_ports = [p.get('port') for p in ports_data]
            else:
                self.nmap_ports = ports_data
            self.last_nmap = datetime.now(MOSCOW_TZ)
        
        # Обновляем объединенный список (уникальные порты)
        all_ports = set(self.rustscan_ports or []) | set(self.nmap_ports or [])
        self.open_ports = sorted(list(all_ports))
        self.updated_at = datetime.now(MOSCOW_TZ)

    def to_dict(self):
        return {
            'id': self.id,
            'ip_address': self.ip_address,
            'hostname': self.hostname,
            'os_family': self.os_family,
            'os_version': self.os_version,
            'device_type': self.device_type,
            'status': self.status,
            'location': self.location,
            'owner': self.owner,
            'dns_names': self.dns_names,
            'fqdn': self.fqdn,
            'dns_records': self.dns_records,
            'open_ports': self.open_ports,
            'rustscan_ports': self.rustscan_ports,
            'nmap_ports': self.nmap_ports,
            'last_rustscan': self.last_rustscan.isoformat() if self.last_rustscan else None,
            'last_nmap': self.last_nmap.isoformat() if self.last_nmap else None,
            'last_dns_scan': self.last_dns_scan.isoformat() if self.last_dns_scan else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'groups': [g.name for g in self.groups]
        }