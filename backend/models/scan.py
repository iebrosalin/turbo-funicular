from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Text, Boolean, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
from backend.db.base import Base


class Scan(Base):
    """Модель сканирования (локальные сканирования nmap/rustscan/dig)."""
    
    __tablename__ = "scans"
    
    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(String(36), unique=True, nullable=False, index=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(255), nullable=False)
    target = Column(String(500), nullable=False)  # IP, диапазон или список
    scan_type = Column(String(50), default="nmap")  # nmap, rustscan, ping
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
    job_type = Column(String(50), nullable=False)  # nmap, rustscan, dig
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
    raw_output = Column(Text, nullable=True)  # Сырой вывод сканера
    scanned_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Связи
    scan = relationship("Scan", back_populates="results")
    asset = relationship("Asset", back_populates="scan_results")
    scan_job = relationship("ScanJob", backref="results")


class RedCheckScan(Base):
    """Модель сканирования RedCheck (объединяет задачу и отчёт)."""
    
    __tablename__ = "redcheck_scans"
    
    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(String(36), unique=True, nullable=False, index=True, default=lambda: str(uuid.uuid4()))
    
    # Информация о задаче
    redcheck_job_id = Column(Integer, nullable=True, index=True)  # ID задачи в RedCheck
    scan_type = Column(String(100), nullable=True)  # Тип сканирования (vulnerability, compliance, inventory)
    profile_id = Column(Integer, nullable=True)  # ID профиля проверки
    profile_name = Column(String(255), nullable=True)  # Название профиля
    target_id = Column(Integer, nullable=True, index=True)  # ID цели в RedCheck
    target_name = Column(String(255), nullable=True)  # Название цели
    host_group_id = Column(Integer, nullable=True)  # ID группы хостов
    
    # Статус и прогресс
    status = Column(String(50), default="pending")  # pending, running, completed, failed, cancelled
    progress = Column(Integer, default=0)  # 0-100%
    
    # Информация об отчёте
    redcheck_report_id = Column(Integer, nullable=True, index=True)  # ID отчёта в RedCheck
    report_format = Column(String(50), nullable=True)  # Формат отчёта (pdf, html, xml, json)
    report_status = Column(String(50), nullable=True)  # Статус экспорта отчёта
    
    # Результаты
    vulnerabilities_count = Column(Integer, default=0)  # Количество уязвимостей
    critical_count = Column(Integer, default=0)  # Критические
    high_count = Column(Integer, default=0)  # Высокие
    medium_count = Column(Integer, default=0)  # Средние
    low_count = Column(Integer, default=0)  # Низкие
    hosts_scanned = Column(Integer, default=0)  # Количество просканированных хостов
    hosts_failed = Column(Integer, default=0)  # Количество неудачных хостов
    
    # Метаданные
    name = Column(String(255), nullable=True)  # Название сканирования
    description = Column(Text, nullable=True)  # Описание
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    error_message = Column(Text, nullable=True)
    
    # Дополнительные данные из API
    raw_data = Column(JSON, nullable=True, default=dict)  # Сырые данные из API


# Добавим обратные связи
Scan.results = relationship("ScanResult", back_populates="scan", cascade="all, delete-orphan")
