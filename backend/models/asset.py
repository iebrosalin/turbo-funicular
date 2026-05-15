from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Text, Boolean, Index, JSON, Table, Float
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime
import uuid
from backend.db.base import Base

# Импортируем таблицу связи из base, чтобы избежать циклического импорта при импорте AssetGroup
# Таблица связи many-to-many между активами и группами
asset_groups = Table(
    'asset_groups',
    Base.metadata,
    Column('asset_id', Integer, ForeignKey('assets.id', ondelete='CASCADE'), primary_key=True),
    Column('group_id', Integer, ForeignKey('groups.id', ondelete='CASCADE'), primary_key=True)
)

# Таблица связи many-to-many между RedCheck хостами и группами
redcheck_host_groups = Table(
    'redcheck_host_groups',
    Base.metadata,
    Column('redcheck_host_id', Integer, ForeignKey('redcheck_hosts.id', ondelete='CASCADE'), primary_key=True),
    Column('group_id', Integer, ForeignKey('groups.id', ondelete='CASCADE'), primary_key=True)
)


class Asset(Base):
    """Сетевой актив (хост, сервер, устройство)"""
    
    __tablename__ = 'assets'

    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(String(36), unique=True, nullable=False, index=True, default=lambda: str(uuid.uuid4()))
    ip_address = Column(String(45), unique=True, nullable=False, index=True)  # Поддержка IPv6
    hostname = Column(String(255), nullable=True, index=True)
    mac_address = Column(String(17), nullable=True, index=True)  # MAC адрес устройства
    vendor = Column(String(255), nullable=True)  # Производитель устройства (по MAC)

    # Основная информация
    os_family = Column(String(50), nullable=True, index=True)  # Linux, Windows, etc.
    os_version = Column(String(100), nullable=True)
    device_type = Column(String(50), default='unknown', nullable=True, index=True)  # server, workstation, network_device

    # Статус и метаданные
    status = Column(String(20), default='active', nullable=True, index=True)  # active, inactive, archived
    location = Column(String(100), nullable=True)
    owner = Column(String(100), nullable=True)
    source = Column(String(20), default='manual', nullable=True, index=True)  # manual, scanning

    # DNS данные
    dns_names = Column(JSON, nullable=True, default=list)  # Список всех найденных имен
    fqdn = Column(String(255), nullable=True)  # Основное полное доменное имя
    dns_records = Column(JSON, nullable=True, default=dict)  # Словарь записей: {'A': [...], 'MX': [...], ...}

    # Теги
    tags = Column(JSON, nullable=True, default=list)  # Список тегов актива

    # Порты (разделение по источникам)
    rustscan_ports = Column(JSON, nullable=True, default=list)
    nmap_ports = Column(JSON, nullable=True, default=list)
    open_ports = Column(JSON, nullable=True, default=list)  # Список всех открытых портов

    # Временные метки сканирований
    last_rustscan = Column(DateTime(timezone=True), nullable=True)
    last_nmap = Column(DateTime(timezone=True), nullable=True)
    last_dns_scan = Column(DateTime(timezone=True), nullable=True)
    last_seen = Column(DateTime(timezone=True), nullable=True, index=True)  # Последняя дата любого сканирования

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now())
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(), onupdate=lambda: datetime.now())

    # Связи
    # secondary=asset_groups связывает с Group через таблицу многие-ко-многим
    # CASCADE удаляется через foreign key в таблице asset_groups (ondelete='CASCADE')
    groups = relationship('Group', secondary=asset_groups, back_populates='assets')

    # Прямые связи один-ко-многим
    # Каскадное удаление настроено на уровне БД через ondelete='CASCADE' в связанных моделях
    # SQLAlchemy автоматически использует CASCADE базы данных, поэтому cascade='all, delete-orphan' не нужен
    services = relationship('ServiceInventory', back_populates='asset')
    scan_results = relationship('ScanResult', back_populates='asset')
    activity_logs = relationship('ActivityLog', back_populates='asset')
    change_logs = relationship('AssetChangeLog', back_populates='asset')

    def update_ports(self, source, ports_data):
        """Обновление портов из указанного источника"""
        now = datetime.now()
        if source == 'rustscan':
            self.rustscan_ports = ports_data
            self.last_rustscan = now
        elif source == 'nmap':
            # ports_data может быть списком портов или списком словарей
            if isinstance(ports_data, list) and ports_data and isinstance(ports_data[0], dict):
                self.nmap_ports = [p.get('port') for p in ports_data]
            else:
                self.nmap_ports = ports_data
            self.last_nmap = now

        # Обновляем общий список открытых портов
        all_source_ports = set(self.rustscan_ports or []) | set(self.nmap_ports or [])
        self.open_ports = sorted(list(all_source_ports))
        
        self.updated_at = now

    @property
    def open_ports_property(self):
        """Вычисляемое свойство для объединения портов из rustscan и nmap (резервное)."""
        all_ports = set(self.rustscan_ports or []) | set(self.nmap_ports or [])
        return sorted(list(all_ports))

    def to_dict(self):
        return {
            'id': self.id,
            'uuid': self.uuid,
            'ip_address': self.ip_address,
            'hostname': self.hostname,
            'mac_address': self.mac_address,
            'vendor': self.vendor,
            'os_family': self.os_family,
            'os_version': self.os_version,
            'device_type': self.device_type,
            'status': self.status,
            'location': self.location,
            'owner': self.owner,
            'source': self.source,
            'dns_names': self.dns_names,
            'fqdn': self.fqdn,
            'dns_records': self.dns_records,
            'tags': self.tags,
            'open_ports': self.open_ports,  # Вычисляемое свойство
            'rustscan_ports': self.rustscan_ports,
            'nmap_ports': self.nmap_ports,
            'last_rustscan': self.last_rustscan.isoformat() if self.last_rustscan else None,
            'last_nmap': self.last_nmap.isoformat() if self.last_nmap else None,
            'last_dns_scan': self.last_dns_scan.isoformat() if self.last_dns_scan else None,
            'last_seen': self.last_seen.isoformat() if self.last_seen else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'groups': [g.name for g in self.groups]
        }


class RedCheckHost(Base):
    """Модель хоста (актива) из RedCheck."""
    
    __tablename__ = "redcheck_hosts"
    
    id = Column(Integer, primary_key=True, index=True)
    redcheck_guid = Column(String(100), unique=True, nullable=False, index=True)  # GUID в RedCheck
    
    # Основная информация
    hostname = Column(String(255), nullable=True)
    ip_address = Column(String(45), nullable=True, index=True)
    mac_address = Column(String(17), nullable=True)
    
    # ОС
    os_type = Column(String(100), nullable=True)  # Windows, Linux, etc.
    os_version = Column(String(255), nullable=True)
    os_architecture = Column(String(50), nullable=True)
    
    # Статус
    status = Column(String(50), default="active")  # active, inactive, unknown
    is_active = Column(Boolean, default=True)
    
    # Группы (many-to-many связь)
    groups = relationship('Group', secondary=redcheck_host_groups, back_populates='redcheck_hosts')
    
    # Уязвимости
    vulnerabilities_count = Column(Integer, default=0)
    critical_vulnerabilities = Column(Integer, default=0)
    high_vulnerabilities = Column(Integer, default=0)
    medium_vulnerabilities = Column(Integer, default=0)
    low_vulnerabilities = Column(Integer, default=0)
    
    # Порты (удалено по требованию - не нужно добавлять open_ports в redcheck_hosts)
    open_ports_count = Column(Integer, default=0)
    
    # Соответствие
    compliance_score = Column(Float, nullable=True)  # Процент соответствия
    last_compliance_check = Column(DateTime(timezone=True), nullable=True)
    
    # Временные метки
    first_seen = Column(DateTime(timezone=True), nullable=True)
    last_seen = Column(DateTime(timezone=True), nullable=True)
    last_synced = Column(DateTime(timezone=True), nullable=True)
    
    # Дополнительные данные
    raw_data = Column(JSON, nullable=True)
    
    # Метаданные
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    def to_dict(self):
        """Преобразование в словарь."""
        return {
            "id": self.id,
            "redcheck_guid": self.redcheck_guid,
            "hostname": self.hostname,
            "ip_address": self.ip_address,
            "mac_address": self.mac_address,
            "os_type": self.os_type,
            "os_version": self.os_version,
            "os_architecture": self.os_architecture,
            "status": self.status,
            "is_active": self.is_active,
            "groups": [g.name for g in self.groups] if self.groups else [],
            "vulnerabilities_count": self.vulnerabilities_count,
            "critical_vulnerabilities": self.critical_vulnerabilities,
            "high_vulnerabilities": self.high_vulnerabilities,
            "medium_vulnerabilities": self.medium_vulnerabilities,
            "low_vulnerabilities": self.low_vulnerabilities,
            "open_ports_count": self.open_ports_count,
            "compliance_score": self.compliance_score,
            "last_compliance_check": self.last_compliance_check.isoformat() if self.last_compliance_check else None,
            "first_seen": self.first_seen.isoformat() if self.first_seen else None,
            "last_seen": self.last_seen.isoformat() if self.last_seen else None,
            "last_synced": self.last_synced.isoformat() if self.last_synced else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }
