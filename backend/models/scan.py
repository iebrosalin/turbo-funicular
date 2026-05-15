from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Text, Boolean, JSON, Float
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
from backend.db.base import Base


class Scan(Base):
    """Модель сканирования."""
    
    __tablename__ = "scans"
    
    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(String(36), unique=True, nullable=False, index=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(255), nullable=False)
    target = Column(String(500), nullable=False)  # IP, диапазон или список
    scan_type = Column(String(50), default="nmap")  # nmap, rustscan, ping, fping
    status = Column(String(50), default="pending")  # pending, running, completed, failed
    progress = Column(Integer, default=0)  # 0-100%
    result = Column(Text, nullable=True)  # JSON результат сканирования
    group_id = Column(Integer, ForeignKey("groups.id", ondelete="SET NULL"), nullable=True, index=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    error_message = Column(Text, nullable=True)
    
    # Связи
    group = relationship("Group", back_populates="scans")


class ScanJob(Base):
    """Модель задачи сканирования в очереди."""
    
    __tablename__ = "scan_jobs"
    
    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(String(36), unique=True, nullable=False, index=True, default=lambda: str(uuid.uuid4()))
    scan_id = Column(Integer, ForeignKey("scans.id", ondelete="CASCADE"), nullable=False)
    job_type = Column(String(50), nullable=False)  # nmap, rustscan, dig, fping
    status = Column(String(50), default="pending")  # pending, running, completed, failed
    priority = Column(Integer, default=0)  # Приоритет задачи
    worker_id = Column(String(100), nullable=True)  # ID воркера
    parameters = Column(JSON, nullable=True, default=dict)  # Параметры задачи
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    error_message = Column(Text, nullable=True)
    
    # Связи
    scan = relationship("Scan", backref="jobs")


class ScanResult(Base):
    """Модель результата сканирования по хостам."""
    
    __tablename__ = "scan_results"
    
    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(String(36), unique=True, nullable=False, index=True, default=lambda: str(uuid.uuid4()))
    scan_id = Column(Integer, ForeignKey("scans.id", ondelete="CASCADE"), nullable=False)
    scan_job_id = Column(Integer, ForeignKey("scan_jobs.id", ondelete="CASCADE"), nullable=True)
    asset_id = Column(Integer, ForeignKey("assets.id", ondelete="CASCADE"), nullable=True)
    ip_address = Column(String(45), nullable=False)
    status = Column(String(50), default="pending")  # pending, success, failed
    ports = Column(JSON, nullable=True, default=list)  # Список портов
    services = Column(JSON, nullable=True, default=dict)  # Информация о сервисах
    os_info = Column(String(255), nullable=True)
    hostname = Column(String(255), nullable=True)
    raw_output = Column(Text, nullable=True)  # Сырой вывод сканера (по умолчанию для всех)
    output_xml = Column(Text, nullable=True)  # XML формат (для nmap)
    output_gnmap = Column(Text, nullable=True)  # Grepable/Nmap формат (для nmap)
    output_normal = Column(Text, nullable=True)  # Normal формат (для nmap)
    output_json = Column(JSON, nullable=True)  # JSON формат (для rustscan и dig)
    scanned_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Связи
    scan = relationship("Scan", back_populates="results")
    asset = relationship("Asset", back_populates="scan_results")
    scan_job = relationship("ScanJob", backref="results")


# Добавим обратные связи
Scan.results = relationship("ScanResult", back_populates="scan", cascade="all, delete-orphan")


class RedCheckScan(Base):
    """Модель сканирования RedCheck (объединяет задачу и отчёт)."""
    
    __tablename__ = "redcheck_scans"
    
    id = Column(Integer, primary_key=True, index=True)
    external_id = Column(String(100), unique=True, nullable=False, index=True)  # ID в RedCheck
    
    # Основная информация
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    scan_type = Column(String(50), default="unknown")  # vulnerability_scan, compliance_check, etc.
    status = Column(String(50), default="pending")  # pending, running, completed, failed, cancelled
    progress = Column(Integer, default=0)  # 0-100%
    
    # Профиль и цель
    profile_name = Column(String(255), nullable=True)
    profile_id = Column(String(100), nullable=True)
    target_name = Column(String(255), nullable=True)
    target_id = Column(String(100), nullable=True)
    
    # Временные метки
    created_at = Column(DateTime(timezone=True), nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    
    # Уязвимости
    vulnerabilities_critical = Column(Integer, default=0)
    vulnerabilities_high = Column(Integer, default=0)
    vulnerabilities_medium = Column(Integer, default=0)
    vulnerabilities_low = Column(Integer, default=0)
    vulnerabilities_total = Column(Integer, default=0)
    
    # Отчёт
    has_report = Column(Boolean, default=False)
    report_id = Column(String(100), nullable=True)
    report_format = Column(String(20), nullable=True)
    
    # Дополнительные данные
    raw_data = Column(JSON, nullable=True)
    
    # Метаданные
    synced_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    def to_dict(self):
        """Преобразование в словарь."""
        return {
            "id": self.id,
            "external_id": self.external_id,
            "name": self.name,
            "description": self.description,
            "scan_type": self.scan_type,
            "status": self.status,
            "progress": self.progress,
            "profile_name": self.profile_name,
            "profile_id": self.profile_id,
            "target_name": self.target_name,
            "target_id": self.target_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "vulnerabilities_critical": self.vulnerabilities_critical,
            "vulnerabilities_high": self.vulnerabilities_high,
            "vulnerabilities_medium": self.vulnerabilities_medium,
            "vulnerabilities_low": self.vulnerabilities_low,
            "vulnerabilities_total": self.vulnerabilities_total,
            "has_report": self.has_report,
            "report_id": self.report_id,
            "report_format": self.report_format,
            "synced_at": self.synced_at.isoformat() if self.synced_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }
