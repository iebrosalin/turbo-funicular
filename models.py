from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from extensions import db
import json

class Group(db.Model):
    __tablename__ = 'group'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    parent_id = db.Column(db.Integer, db.ForeignKey('group.id'), nullable=True)
    is_dynamic = db.Column(db.Boolean, default=False)
    filter_rules = db.Column(db.Text, nullable=True)  # JSON строка с правилами
    
    # Рекурсивная связь
    children = db.relationship('Group', backref=db.backref('parent', remote_side=[id]), lazy='dynamic')
    assets = db.relationship('Asset', backref='group', lazy='dynamic', cascade='all, delete-orphan')

class Asset(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ip_address = db.Column(db.String(50), nullable=False, index=True)
    hostname = db.Column(db.String(255), nullable=True)
    os_info = db.Column(db.String(100), nullable=True)
    mac_address = db.Column(db.String(50), nullable=True)
    group_id = db.Column(db.Integer, db.ForeignKey('group.id'), nullable=True, index=True)
    
    # Дополнительные поля
    device_role = db.Column(db.String(100), nullable=True)
    device_tags = db.Column(db.Text, nullable=True)  # 🔥 JSON список тегов (добавлено)
    status = db.Column(db.String(50), default='active')
    notes = db.Column(db.Text, nullable=True)
    
    # Поля для DNS (из nslookup)
    dns_names = db.Column(db.Text, nullable=True)  # JSON список доменов
    
    # Поля для совместимости со старым кодом и scanner.py
    data_source = db.Column(db.String(50), default='manual')
    last_scanned = db.Column(db.DateTime, nullable=True)
    scanners_used = db.Column(db.Text, nullable=True)  # JSON список сканеров
    
    # Порты от разных сканеров (строки)
    open_ports = db.Column(db.Text, nullable=True)      # Объединенный список "22/tcp, 80/tcp"
    ports_list = db.Column(db.Text, nullable=True)      # JSON список портов
    
    rustscan_ports = db.Column(db.Text, nullable=True)  # 🔥 Порты только от RustScan (добавлено)
    nmap_ports = db.Column(db.Text, nullable=True)      # 🔥 Порты только от Nmap (добавлено)
    
    # Даты последних сканирований конкретными утилитами
    last_rustscan = db.Column(db.DateTime, nullable=True)  # 🔥 (добавлено)
    last_nmap = db.Column(db.DateTime, nullable=True)      # 🔥 (добавлено)

    # Связи
    scan_results = db.relationship('ScanResult', backref='asset', lazy='select', cascade='all, delete-orphan')
    change_log = db.relationship('AssetChangeLog', backref='asset', lazy='select', cascade='all, delete-orphan')
    services = db.relationship('ServiceInventory', backref='asset', lazy='select', cascade='all, delete-orphan')
    
    # Особое внимание здесь: если это one-to-one, uselist=False обязательно, но lazy не может быть 'dynamic'
    osquery_inventory = db.relationship('OsqueryInventory', backref='asset', lazy='select', uselist=False, cascade='all, delete-orphan')

class AssetChangeLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    asset_id = db.Column(db.Integer, db.ForeignKey('asset.id'), nullable=False)
    changed_at = db.Column(db.DateTime, default=datetime.utcnow)
    field_name = db.Column(db.String(100))
    old_value = db.Column(db.Text)
    new_value = db.Column(db.Text)
    changed_by = db.Column(db.String(100), default='system')
    # Для совместимости со старым кодом
    change_type = db.Column(db.String(50), nullable=True)
    scan_job_id = db.Column(db.Integer, db.ForeignKey('scan_job.id'), nullable=True)
    notes = db.Column(db.Text, nullable=True)

class ServiceInventory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    asset_id = db.Column(db.Integer, db.ForeignKey('asset.id'), nullable=False)
    port = db.Column(db.Integer) # Или String если хранится как "22/tcp"
    protocol = db.Column(db.String(10))
    service_name = db.Column(db.String(100))
    version = db.Column(db.String(100))
    state = db.Column(db.String(50))
    last_seen = db.Column(db.DateTime, default=datetime.utcnow)
    # Для совместимости
    is_active = db.Column(db.Boolean, default=True)
    # Дополнительные поля из парсера nmap (если используются)
    product = db.Column(db.String(255), nullable=True)
    extrainfo = db.Column(db.Text, nullable=True)

class OsqueryInventory(db.Model):
    __tablename__ = 'osquery_inventory'
    id = db.Column(db.Integer, primary_key=True)
    asset_id = db.Column(db.Integer, db.ForeignKey('asset.id'), nullable=False, unique=True)
    
    # Основная информация из OSquery
    osquery_version = db.Column(db.String(50))
    os_name = db.Column(db.String(100))
    os_version = db.Column(db.String(100))
    os_build = db.Column(db.String(50))
    os_platform = db.Column(db.String(50))
    platform_like = db.Column(db.String(50))
    code_name = db.Column(db.String(50))
    
    # Система
    hostname = db.Column(db.String(255))
    uuid = db.Column(db.String(100))
    cpu_type = db.Column(db.String(100))
    cpu_subtype = db.Column(db.String(100))
    cpu_brand = db.Column(db.String(100))
    cpu_physical_cores = db.Column(db.Integer)
    cpu_logical_cores = db.Column(db.Integer)
    cpu_microcode = db.Column(db.String(50))
    
    # Память и диск
    physical_memory = db.Column(db.BigInteger)
    hardware_vendor = db.Column(db.String(100))
    hardware_model = db.Column(db.String(100))
    hardware_version = db.Column(db.String(50))
    hardware_serial = db.Column(db.String(100))
    board_vendor = db.Column(db.String(100))
    board_model = db.Column(db.String(100))
    board_version = db.Column(db.String(50))
    board_serial = db.Column(db.String(100))
    chassis_type = db.Column(db.String(50))
    
    # Статус агента
    status = db.Column(db.String(20), default='unknown')
    last_seen = db.Column(db.DateTime, default=datetime.utcnow)
    config_hash = db.Column(db.String(64))

class ScanJob(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    scan_type = db.Column(db.String(50), nullable=False)
    target = db.Column(db.String(255), nullable=False)
    status = db.Column(db.String(20), default='pending')
    progress = db.Column(db.Integer, default=0)
    
    current_target = db.Column(db.String(255), nullable=True)
    total_hosts = db.Column(db.Integer, default=0)
    hosts_processed = db.Column(db.Integer, default=0)
    error_message = db.Column(db.Text, nullable=True)
    
    # Вывод сканеров
    rustscan_output = db.Column(db.Text, nullable=True)
    rustscan_text_path = db.Column(db.String(500), nullable=True)
    
    nmap_xml_path = db.Column(db.String(500), nullable=True)
    nmap_grep_path = db.Column(db.String(500), nullable=True)
    nmap_normal_path = db.Column(db.String(500), nullable=True)
    
    nmap_xml_content = db.Column(db.Text, nullable=True)
    nmap_grep_content = db.Column(db.Text, nullable=True)
    nmap_normal_content = db.Column(db.Text, nullable=True)
    
    nslookup_output = db.Column(db.Text, nullable=True)
    nslookup_file_path = db.Column(db.String(500), nullable=True)
    
    scan_parameters = db.Column(db.Text, nullable=True)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    started_at = db.Column(db.DateTime, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)

class ScanResult(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    asset_id = db.Column(db.Integer, db.ForeignKey('asset.id'), nullable=False)
    scan_job_id = db.Column(db.Integer, db.ForeignKey('scan_job.id'), nullable=True)
    scanned_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    ip = db.Column(db.String(50))
    ports = db.Column(db.Text)
    os = db.Column(db.String(100), nullable=True)
    hostname = db.Column(db.String(255), nullable=True)
    os_detection = db.Column(db.String(100), nullable=True)
    services = db.Column(db.Text, nullable=True) # JSON
    scan_type = db.Column(db.String(50), nullable=True) # Для совместимости со старым кодом
    ip_address = db.Column(db.String(50), nullable=True) # Для совместимости

class ScanProfile(db.Model):
    __tablename__ = 'scan_profile'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    description = db.Column(db.Text, nullable=True)
    
    scan_type = db.Column(db.String(50), nullable=False)
    targets = db.Column(db.Text, nullable=True)
    ports = db.Column(db.String(255), nullable=True)
    timing = db.Column(db.String(10), default='T3')
    scripts = db.Column(db.Text, nullable=True)
    extra_args = db.Column(db.Text, nullable=True)
    
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class WazuhConfig(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    url = db.Column(db.String(255), nullable=False)
    username = db.Column(db.String(100), nullable=False)
    password = db.Column(db.String(255), nullable=False)
    verify_ssl = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)
    last_sync = db.Column(db.DateTime, nullable=True)