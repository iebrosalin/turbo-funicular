# models.py
"""
Модели базы данных для системы управления активами и сканированиями.
Включает модели для активов, групп, сканирований, сервисов и логов активности.
"""
from datetime import datetime
from extensions import db
from utils import MOSCOW_TZ
import json

# Таблица многие-ко-многим для связи Активов и Групп
asset_groups = db.Table('asset_groups',
    db.Column('asset_id', db.Integer, db.ForeignKey('asset.id'), primary_key=True),
    db.Column('group_id', db.Integer, db.ForeignKey('asset_group.id'), primary_key=True)
)

class AssetGroup(db.Model):
    """Группа активов (например, по отделам, локациям или функциям)"""
    __tablename__ = 'asset_group'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False, index=True)
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(MOSCOW_TZ))
    
    # Связь с активами
    assets = db.relationship('Asset', secondary=asset_groups, back_populates='groups')
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'assets_count': len(self.assets)
        }

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
    
    # DNS данные (новые поля)
    dns_names = db.Column(db.JSON, default=list) # Список всех найденных имен ['host.local', 'web.example.com']
    fqdn = db.Column(db.String(255)) # Основное полное доменное имя
    dns_records = db.Column(db.JSON, default=dict) # Словарь записей: {'A': [...], 'MX': [...], ...}
    
    # Порты (разделение по источникам)
    rustscan_ports = db.Column(db.JSON, default=list) # Порты от Rustscan [80, 443]
    nmap_ports = db.Column(db.JSON, default=list) # Порты от Nmap (с деталями или просто список)
    open_ports = db.Column(db.JSON, default=list) # Объединенный список портов для быстрого доступа
    
    # Временные метки сканирований
    last_rustscan = db.Column(db.DateTime)
    last_nmap = db.Column(db.DateTime)
    last_dns_scan = db.Column(db.DateTime)
    
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(MOSCOW_TZ))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(MOSCOW_TZ), onupdate=lambda: datetime.now(MOSCOW_TZ))
    
    # Связи
    groups = db.relationship('AssetGroup', secondary=asset_groups, back_populates='assets')
    services = db.relationship('ServiceInventory', back_populates='asset', cascade='all, delete-orphan')
    scan_results = db.relationship('ScanResult', back_populates='asset', cascade='all, delete-orphan')
    activity_logs = db.relationship('ActivityLog', back_populates='asset', cascade='all, delete-orphan')
    
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

class ServiceInventory(db.Model):
    """Детальная информация о сервисах на портах"""
    __tablename__ = 'service_inventory'
    
    id = db.Column(db.Integer, primary_key=True)
    asset_id = db.Column(db.Integer, db.ForeignKey('asset.id'), nullable=False, index=True)
    
    port = db.Column(db.Integer, nullable=False)
    protocol = db.Column(db.String(10), default='tcp') # tcp, udp
    state = db.Column(db.String(20), default='open') # open, closed, filtered
    service_name = db.Column(db.String(100)) # http, ssh, mysql
    product = db.Column(db.String(200)) # Apache httpd
    version = db.Column(db.String(200)) # 2.4.41
    extra_info = db.Column(db.String(200)) # Ubuntu
    script_output = db.Column(db.Text) # Вывод скриптов nmap
    
    # SSL сертификат (если есть)
    ssl_subject = db.Column(db.String(500))
    ssl_issuer = db.Column(db.String(500))
    ssl_not_before = db.Column(db.DateTime)
    ssl_not_after = db.Column(db.DateTime)
    
    discovered_at = db.Column(db.DateTime, default=lambda: datetime.now(MOSCOW_TZ))
    
    asset = db.relationship('Asset', back_populates='services')
    
    def to_dict(self):
        return {
            'id': self.id,
            'port': self.port,
            'protocol': self.protocol,
            'state': self.state,
            'service_name': self.service_name,
            'product': self.product,
            'version': self.version,
            'extra_info': self.extra_info,
            'script_output': self.script_output,
            'ssl_info': {
                'subject': self.ssl_subject,
                'issuer': self.ssl_issuer,
                'not_before': self.ssl_not_before.isoformat() if self.ssl_not_before else None,
                'not_after': self.ssl_not_after.isoformat() if self.ssl_not_after else None
            } if self.ssl_subject else None,
            'discovered_at': self.discovered_at.isoformat() if self.discovered_at else None
        }

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
    asset_id = db.Column(db.Integer, db.ForeignKey('asset.id'), nullable=True, index=True) # Может быть null если актив не создан/найден
    
    asset_ip = db.Column(db.String(45), index=True)
    hostname = db.Column(db.String(255))
    
    os_match = db.Column(db.String(200))
    os_accuracy = db.Column(db.Integer)
    
    ports = db.Column(db.JSON, default=list) # Список портов из этого сканирования
    raw_output = db.Column(db.Text) # Сырой вывод (xml для nmap, text для других)
    
    scanned_at = db.Column(db.DateTime, default=lambda: datetime.now(MOSCOW_TZ))
    
    job = db.relationship('ScanJob', back_populates='results')
    asset = db.relationship('Asset', back_populates='scan_results')

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
class WazuhConfig(db.Model):
    """Конфигурация интеграции с Wazuh (заглушка для совместимости)"""
    __tablename__ = 'wazuh_config'
    
    id = db.Column(db.Integer, primary_key=True)
    api_url = db.Column(db.String(255))
    api_key = db.Column(db.String(255))
    enabled = db.Column(db.Boolean, default=False)
    
    def to_dict(self):
        return {
            'id': self.id,
            'api_url': self.api_url,
            'enabled': self.enabled
        }

class OsqueryInventory(db.Model):
    """Инвентаризация данных Osquery (заглушка для совместимости)"""
    __tablename__ = 'osquery_inventory'
    
    id = db.Column(db.Integer, primary_key=True)
    asset_id = db.Column(db.Integer, db.ForeignKey('asset.id'), nullable=False, index=True)
    
    hostname = db.Column(db.String(255))
    os_version = db.Column(db.String(100))
    platform = db.Column(db.String(50))
    hardware_model = db.Column(db.String(200))
    cpu_brand = db.Column(db.String(200))
    physical_memory = db.Column(db.BigInteger) # в байтах
    
    last_seen = db.Column(db.DateTime)
    
    asset = db.relationship('Asset', back_populates='osquery_data')