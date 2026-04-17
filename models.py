# models.py
from extensions import db
from datetime import datetime
import json

class Group(db.Model):
    """Модель группы активов (статическая или динамическая)"""
    __tablename__ = 'group'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    parent_id = db.Column(db.Integer, db.ForeignKey('group.id'), nullable=True)
    is_dynamic = db.Column(db.Boolean, default=False)
    filter_query = db.Column(db.Text, nullable=True)  # JSON-структура фильтра для динамических групп
    
    # 🔹 Отношения (без backref='assets' — он определён в Asset!)
    parent = db.relationship('Group', remote_side=[id], backref='children')
    
    def __repr__(self):
        return f'<Group {self.name}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'parent_id': self.parent_id,
            'is_dynamic': self.is_dynamic,
            'filter_query': self.filter_query
        }


class Asset(db.Model):
    """Модель актива (устройства/сервера) в сети"""
    __tablename__ = 'asset'
    
    # 🔹 Основные идентификаторы
    id = db.Column(db.Integer, primary_key=True)
    ip_address = db.Column(db.String(50), nullable=False, index=True)
    hostname = db.Column(db.String(255), nullable=True)
    
    # 🔹 Информация об ОС
    os_info = db.Column(db.String(255), nullable=True)
    status = db.Column(db.String(20), default='up')
    
    # 🔹 Порты (разделённые по сканерам)
    open_ports = db.Column(db.Text, nullable=True)
    rustscan_ports = db.Column(db.Text, nullable=True)
    nmap_ports = db.Column(db.Text, nullable=True)
    ports_list = db.Column(db.Text, default='[]')
    
    # 🔹 Временные метки сканирований
    last_scanned = db.Column(db.DateTime, nullable=True)
    last_rustscan = db.Column(db.DateTime, nullable=True)
    last_nmap = db.Column(db.DateTime, nullable=True)
    
    # 🔹 Заметки и классификация
    notes = db.Column(db.Text, nullable=True)
    device_role = db.Column(db.String(100), nullable=True)
    device_tags = db.Column(db.Text, nullable=True)
    
    # 🔹 Источники данных
    scanners_used = db.Column(db.Text, nullable=True)
    data_source = db.Column(db.String(20), default='manual')
    
    # 🔹 Wazuh интеграция
    wazuh_agent_id = db.Column(db.String(50), nullable=True)
    
    # 🔹 OSquery интеграция
    osquery_status = db.Column(db.String(20), default='offline')
    osquery_last_seen = db.Column(db.DateTime, nullable=True)
    osquery_cpu = db.Column(db.String(255), nullable=True)
    osquery_ram = db.Column(db.String(50), nullable=True)
    osquery_disk = db.Column(db.String(50), nullable=True)
    osquery_os = db.Column(db.String(255), nullable=True)
    osquery_kernel = db.Column(db.String(255), nullable=True)
    osquery_uptime = db.Column(db.Integer, nullable=True)
    osquery_node_key = db.Column(db.String(100), nullable=True, unique=True)
    osquery_version = db.Column(db.String(50), nullable=True)
    
    # 🔹 Внешние ключи
    group_id = db.Column(db.Integer, db.ForeignKey('group.id'), nullable=True, index=True)
    
    # 🔹 Отношения (backref='assets' определён ЗДЕСЬ, не в Group!)
    group = db.relationship('Group', backref=db.backref('assets', lazy='dynamic'))
    change_log = db.relationship('AssetChangeLog', backref='asset', lazy='dynamic', cascade='all, delete-orphan')
    service_inventory = db.relationship('ServiceInventory', backref='asset', lazy='dynamic', cascade='all, delete-orphan')
    scan_results = db.relationship('ScanResult', backref='asset', lazy='dynamic', cascade='all, delete-orphan')
    
    def to_dict(self):
        """Сериализация актива в словарь"""
        return {
            'id': self.id,
            'ip_address': self.ip_address,
            'hostname': self.hostname,
            'os_info': self.os_info,
            'status': self.status,
            'open_ports': self.open_ports,
            'rustscan_ports': self.rustscan_ports,
            'nmap_ports': self.nmap_ports,
            'ports_list': json.loads(self.ports_list) if self.ports_list else [],
            'last_scanned': self.last_scanned.strftime('%Y-%m-%d %H:%M') if self.last_scanned else None,
            'last_rustscan': self.last_rustscan.strftime('%Y-%m-%d %H:%M') if self.last_rustscan else None,
            'last_nmap': self.last_nmap.strftime('%Y-%m-%d %H:%M') if self.last_nmap else None,
            'notes': self.notes,
            'device_role': self.device_role,
            'device_tags': json.loads(self.device_tags) if self.device_tags else [],
            'scanners_used': json.loads(self.scanners_used) if self.scanners_used else [],
            'data_source': self.data_source,
            'group_id': self.group_id,
            'group_name': self.group.name if self.group else None,
            'osquery_status': self.osquery_status,
            'osquery_last_seen': self.osquery_last_seen.strftime('%Y-%m-%d %H:%M') if self.osquery_last_seen else None,
        }
    
    def __repr__(self):
        return f'<Asset {self.ip_address}>'


class ScanJob(db.Model):
    """Модель задания сканирования (Nmap/Rustscan/Nslookup)"""
    __tablename__ = 'scan_job'
    
    id = db.Column(db.Integer, primary_key=True)
    scan_type = db.Column(db.String(20), nullable=False)  # 'nmap', 'rustscan', 'nslookup'
    target = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), default='pending')  # pending, running, paused, completed, failed, stopped
    progress = db.Column(db.Integer, default=0)
    current_target = db.Column(db.String(255), nullable=True)
    total_hosts = db.Column(db.Integer, default=0)
    hosts_processed = db.Column(db.Integer, default=0)
    error_message = db.Column(db.Text, nullable=True)
    rustscan_output = db.Column(db.Text, nullable=True)  # 🔥 Содержимое вывода rustscan
    rustscan_text_path = db.Column(db.String(500), nullable=True)  # Путь к текстовому файлу rustscan
    nmap_xml_path = db.Column(db.String(500), nullable=True)  # Путь к XML файлу nmap
    nmap_grep_path = db.Column(db.String(500), nullable=True)  # Путь к grepable файлу nmap
    nmap_normal_path = db.Column(db.String(500), nullable=True)  # Путь к normal файлу nmap
    nmap_xml_content = db.Column(db.Text, nullable=True)  # 🔥 Содержимое XML файла nmap
    nmap_grep_content = db.Column(db.Text, nullable=True)  # 🔥 Содержимое grepable файла nmap
    nmap_normal_content = db.Column(db.Text, nullable=True)  # 🔥 Содержимое normal файла nmap
    nslookup_output = db.Column(db.Text, nullable=True)  # 🔥 Содержимое вывода nslookup
    nslookup_file_path = db.Column(db.String(500), nullable=True)  # Путь к файлу nslookup
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    started_at = db.Column(db.DateTime, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)
    
    # 🔹 Отношения
    results = db.relationship('ScanResult', backref='job', lazy='dynamic', cascade='all, delete-orphan')
    
    def to_dict(self):
        return {
            'id': self.id,
            'scan_type': self.scan_type,
            'target': self.target,
            'status': self.status,
            'progress': self.progress,
            'current_target': self.current_target,
            'total_hosts': self.total_hosts,
            'hosts_processed': self.hosts_processed,
            'error_message': self.error_message,
            'rustscan_output': self.rustscan_output,
            'rustscan_text_path': self.rustscan_text_path,
            'nmap_xml_path': self.nmap_xml_path,
            'nmap_grep_path': self.nmap_grep_path,
            'nmap_normal_path': self.nmap_normal_path,
            'nmap_xml_content': self.nmap_xml_content,
            'nmap_grep_content': self.nmap_grep_content,
            'nmap_normal_content': self.nmap_normal_content,
            'nslookup_output': self.nslookup_output,
            'nslookup_file_path': self.nslookup_file_path,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M') if self.created_at else None,
            'started_at': self.started_at.strftime('%Y-%m-%d %H:%M') if self.started_at else None,
            'completed_at': self.completed_at.strftime('%Y-%m-%d %H:%M') if self.completed_at else None,
        }
    
    def __repr__(self):
        return f'<ScanJob {self.id} ({self.scan_type})>'


class ScanResult(db.Model):
    """Модель результата сканирования"""
    __tablename__ = 'scan_result'
    
    id = db.Column(db.Integer, primary_key=True)
    asset_id = db.Column(db.Integer, db.ForeignKey('asset.id'), nullable=True)
    ip_address = db.Column(db.String(50), nullable=False)
    scan_job_id = db.Column(db.Integer, db.ForeignKey('scan_job.id'), nullable=True)
    scan_type = db.Column(db.String(20), nullable=True)  # 🔥 Добавлено для фильтрации
    ports = db.Column(db.Text, nullable=True)
    services = db.Column(db.Text, nullable=True)
    os_detection = db.Column(db.String(255), nullable=True)
    scanned_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'asset_id': self.asset_id,
            'ip_address': self.ip_address,
            'scan_type': self.scan_type,
            'ports': json.loads(self.ports) if self.ports else [],
            'services': json.loads(self.services) if self.services else [],
            'os_detection': self.os_detection,
            'scanned_at': self.scanned_at.strftime('%Y-%m-%d %H:%M') if self.scanned_at else None,
        }
    
    def __repr__(self):
        return f'<ScanResult {self.ip_address}>'


class ServiceInventory(db.Model):
    """Модель сервиса на порту (из Nmap)"""
    __tablename__ = 'service_inventory'
    
    id = db.Column(db.Integer, primary_key=True)
    asset_id = db.Column(db.Integer, db.ForeignKey('asset.id'), nullable=False)
    port = db.Column(db.String(20), nullable=False)
    protocol = db.Column(db.String(10), default='tcp')
    service_name = db.Column(db.String(100), nullable=True)
    product = db.Column(db.String(255), nullable=True)
    version = db.Column(db.String(255), nullable=True)
    extrainfo = db.Column(db.Text, nullable=True)
    script_output = db.Column(db.Text, nullable=True)
    first_seen = db.Column(db.DateTime, default=datetime.utcnow)
    last_seen = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)
    
    def to_dict(self):
        return {
            'id': self.id,
            'port': self.port,
            'protocol': self.protocol,
            'service_name': self.service_name,
            'product': self.product,
            'version': self.version,
            'is_active': self.is_active,
            'last_seen': self.last_seen.strftime('%Y-%m-%d %H:%M') if self.last_seen else None,
        }
    
    def __repr__(self):
        return f'<ServiceInventory {self.port} ({self.service_name})>'


class AssetChangeLog(db.Model):
    """Модель журнала изменений актива"""
    __tablename__ = 'asset_change_log'
    
    id = db.Column(db.Integer, primary_key=True)
    asset_id = db.Column(db.Integer, db.ForeignKey('asset.id'), nullable=False)
    change_type = db.Column(db.String(50), nullable=False)  # port_added, port_removed, os_changed, etc.
    field_name = db.Column(db.String(100), nullable=True)
    old_value = db.Column(db.Text, nullable=True)
    new_value = db.Column(db.Text, nullable=True)
    scan_job_id = db.Column(db.Integer, db.ForeignKey('scan_job.id'), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    changed_at = db.Column(db.DateTime, default=datetime.utcnow)
    
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
            'changed_at': self.changed_at.strftime('%Y-%m-%d %H:%M') if self.changed_at else None,
        }
    
    def __repr__(self):
        return f'<AssetChangeLog {self.asset_id} ({self.change_type})>'


class ScanProfile(db.Model):
    """Модель профиля сканирования (шаблон настроек)"""
    __tablename__ = 'scan_profile'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    scan_type = db.Column(db.String(20), nullable=False)  # 'nmap', 'rustscan'
    target_method = db.Column(db.String(20), default='ip')  # 'ip', 'group'
    ports = db.Column(db.String(255), nullable=True)
    custom_args = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'scan_type': self.scan_type,
            'target_method': self.target_method,
            'ports': self.ports,
            'custom_args': self.custom_args,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M') if self.created_at else None,
            'updated_at': self.updated_at.strftime('%Y-%m-%d %H:%M') if self.updated_at else None,
        }
    
    def __repr__(self):
        return f'<ScanProfile {self.name}>'


class WazuhConfig(db.Model):
    """Модель конфигурации интеграции с Wazuh"""
    __tablename__ = 'wazuh_config'
    
    id = db.Column(db.Integer, primary_key=True)
    api_url = db.Column(db.String(255), nullable=False)
    api_username = db.Column(db.String(100), nullable=False)
    api_password = db.Column(db.String(100), nullable=False)
    verify_ssl = db.Column(db.Boolean, default=True)
    last_sync = db.Column(db.DateTime, nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    
    def to_dict(self):
        return {
            'id': self.id,
            'api_url': self.api_url,
            'api_username': self.api_username,
            'verify_ssl': self.verify_ssl,
            'last_sync': self.last_sync.strftime('%Y-%m-%d %H:%M') if self.last_sync else None,
            'is_active': self.is_active,
        }
    
    def __repr__(self):
        return f'<WazuhConfig {self.api_url}>'


class OsqueryInventory(db.Model):
    """Модель инвентаризации OSquery (детальная)"""
    __tablename__ = 'osquery_inventory'
    
    id = db.Column(db.Integer, primary_key=True)
    node_key = db.Column(db.String(100), nullable=False, unique=True, index=True)
    hostname = db.Column(db.String(255), nullable=True)
    uuid = db.Column(db.String(100), nullable=True)
    cpu_brand = db.Column(db.String(255), nullable=True)
    cpu_logical_cores = db.Column(db.Integer, nullable=True)
    physical_memory = db.Column(db.String(50), nullable=True)
    disk_size = db.Column(db.String(50), nullable=True)
    os_name = db.Column(db.String(100), nullable=True)
    os_version = db.Column(db.String(100), nullable=True)
    kernel_version = db.Column(db.String(100), nullable=True)
    uptime = db.Column(db.Integer, nullable=True)
    last_seen = db.Column(db.DateTime, default=datetime.utcnow)
    osquery_version = db.Column(db.String(50), nullable=True)
    
    def to_dict(self):
        return {
            'id': self.id,
            'node_key': self.node_key,
            'hostname': self.hostname,
            'cpu_brand': self.cpu_brand,
            'physical_memory': self.physical_memory,
            'os_name': self.os_name,
            'os_version': self.os_version,
            'last_seen': self.last_seen.strftime('%Y-%m-%d %H:%M') if self.last_seen else None,
        }
    
    def __repr__(self):
        return f'<OsqueryInventory {self.node_key}>'