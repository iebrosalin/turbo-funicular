from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Text, Boolean, JSON, Float, Table
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
from backend.db.base import Base


# Таблица связи many-to-many между проектами и группами активов
project_groups = Table(
    'project_groups',
    Base.metadata,
    Column('project_id', Integer, ForeignKey('projects.id', ondelete='CASCADE'), primary_key=True),
    Column('group_id', Integer, ForeignKey('groups.id', ondelete='CASCADE'), primary_key=True)
)


class Project(Base):
    """Модель проекта пентеста."""
    
    __tablename__ = "projects"
    
    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(String(36), unique=True, nullable=False, index=True, default=lambda: str(uuid.uuid4()))
    
    # Основная информация
    name = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=True)
    customer = Column(String(255), nullable=True)  # Заказчик
    project_type = Column(String(50), default="pentest")  # pentest, audit, research
    
    # Статус
    status = Column(String(50), default="planning")  # planning, active, paused, completed, archived
    priority = Column(String(20), default="medium")  # low, medium, high, critical
    
    # Даты
    start_date = Column(DateTime(timezone=True), nullable=True)
    end_date = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Связи с группами активов
    groups = relationship('Group', secondary=project_groups, back_populates='projects')
    
    # Связи
    reports = relationship("ProjectReport", back_populates="project", cascade="all, delete-orphan")
    artifacts = relationship("ProjectArtifact", back_populates="project", cascade="all, delete-orphan")
    scan_sessions = relationship("ProjectScanSession", back_populates="project", cascade="all, delete-orphan")
    
    def to_dict(self):
        """Преобразование в словарь."""
        return {
            "id": self.id,
            "uuid": self.uuid,
            "name": self.name,
            "description": self.description,
            "customer": self.customer,
            "project_type": self.project_type,
            "status": self.status,
            "priority": self.priority,
            "start_date": self.start_date.isoformat() if self.start_date else None,
            "end_date": self.end_date.isoformat() if self.end_date else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "groups": [g.name for g in self.groups] if self.groups else [],
            "reports_count": len(self.reports) if hasattr(self, 'reports') else 0,
            "artifacts_count": len(self.artifacts) if hasattr(self, 'artifacts') else 0,
        }


class ProjectReport(Base):
    """Модель отчёта о тестировании (Markdown)."""
    
    __tablename__ = "project_reports"
    
    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(String(36), unique=True, nullable=False, index=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Информация об отчёте
    title = Column(String(255), nullable=False)
    report_type = Column(String(50), default="general")  # general, executive, technical, vulnerability
    
    # Контент
    content = Column(Text, nullable=False)  # Markdown контент
    content_html = Column(Text, nullable=True)  # HTML версия (кэшированная)
    
    # Метаданные
    version = Column(Integer, default=1)
    is_final = Column(Boolean, default=False)
    tags = Column(JSON, nullable=True, default=list)
    
    # Для Obsidian совместимости
    obsidian_tags = Column(Text, nullable=True)  # Теги в формате Obsidian
    obsidian_links = Column(JSON, nullable=True, default=list)  # Ссылки на другие заметки
    
    # Временные метки
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    published_at = Column(DateTime(timezone=True), nullable=True)
    
    # Связи
    project = relationship("Project", back_populates="reports")
    
    def to_dict(self):
        """Преобразование в словарь."""
        return {
            "id": self.id,
            "uuid": self.uuid,
            "project_id": self.project_id,
            "title": self.title,
            "report_type": self.report_type,
            "content": self.content,
            "content_html": self.content_html,
            "version": self.version,
            "is_final": self.is_final,
            "tags": self.tags,
            "obsidian_tags": self.obsidian_tags,
            "obsidian_links": self.obsidian_links,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "published_at": self.published_at.isoformat() if self.published_at else None,
        }


class ProjectArtifact(Base):
    """Модель артефакта проекта (файлы, скриншоты, логи)."""
    
    __tablename__ = "project_artifacts"
    
    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(String(36), unique=True, nullable=False, index=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Информация о файле
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    artifact_type = Column(String(50), default="file")  # file, screenshot, log, export, evidence
    
    # Хранение
    file_path = Column(String(500), nullable=False)  # Путь к файлу
    file_size = Column(Integer, default=0)  # Размер в байтах
    mime_type = Column(String(100), nullable=True)  # MIME тип файла
    checksum = Column(String(64), nullable=True)  # SHA256 хэш
    
    # Метаданные
    category = Column(String(50), nullable=True)  # reconnaissance, exploitation, post_exploitation, reporting
    tags = Column(JSON, nullable=True, default=list)
    
    # Связь со сканированием (опционально)
    scan_id = Column(Integer, ForeignKey("scans.id", ondelete="SET NULL"), nullable=True)
    
    # Временные метки
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    uploaded_at = Column(DateTime(timezone=True), nullable=True)
    
    # Связи
    project = relationship("Project", back_populates="artifacts")
    scan = relationship("Scan", backref="artifacts")
    
    def to_dict(self):
        """Преобразование в словарь."""
        return {
            "id": self.id,
            "uuid": self.uuid,
            "project_id": self.project_id,
            "name": self.name,
            "description": self.description,
            "artifact_type": self.artifact_type,
            "file_path": self.file_path,
            "file_size": self.file_size,
            "mime_type": self.mime_type,
            "checksum": self.checksum,
            "category": self.category,
            "tags": self.tags,
            "scan_id": self.scan_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "uploaded_at": self.uploaded_at.isoformat() if self.uploaded_at else None,
        }


class ProjectScanSession(Base):
    """Модель сессии сканирования в рамках проекта."""
    
    __tablename__ = "project_scan_sessions"
    
    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(String(36), unique=True, nullable=False, index=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Информация о сессии
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    session_type = Column(String(50), default="manual")  # manual, automated, scheduled
    
    # Утилиты и параметры
    utilities_used = Column(JSON, nullable=True, default=list)  # ['nmap', 'rustscan', 'dig', ...]
    parameters = Column(JSON, nullable=True, default=dict)  # Параметры запуска
    
    # Результаты
    targets = Column(JSON, nullable=True, default=list)  # Цели сканирования
    results_summary = Column(Text, nullable=True)  # Краткое описание результатов
    
    # Связи со сканированиями
    scan_ids = Column(JSON, nullable=True, default=list)  # ID связанных сканирований
    
    # Временные метки
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Связи
    project = relationship("Project", back_populates="scan_sessions")
    
    def to_dict(self):
        """Преобразование в словарь."""
        return {
            "id": self.id,
            "uuid": self.uuid,
            "project_id": self.project_id,
            "name": self.name,
            "description": self.description,
            "session_type": self.session_type,
            "utilities_used": self.utilities_used,
            "parameters": self.parameters,
            "targets": self.targets,
            "results_summary": self.results_summary,
            "scan_ids": self.scan_ids,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class CTFMachine(Base):
    """Модель для хранения информации о прохождении CTF машин."""
    
    __tablename__ = "ctf_machines"
    
    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(String(36), unique=True, nullable=False, index=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Информация о машине
    name = Column(String(255), nullable=False)
    platform = Column(String(100), nullable=True)  # HackTheBox, TryHackMe, VulnHub, etc.
    difficulty = Column(String(50), nullable=True)  # easy, medium, hard, insane
    os_type = Column(String(50), nullable=True)  # linux, windows, other
    ip_address = Column(String(50), nullable=True)
    
    # Статус прохождения
    status = Column(String(50), default="not_started")  # not_started, in_progress, pwned, retired
    rank = Column(Integer, nullable=True)  # Место в рейтинге
    points = Column(Integer, default=0)  # Очки за машину
    
    # Этапы взлома
    user_flags = Column(JSON, nullable=True, default=list)  # Найденные пользовательские флаги
    root_flags = Column(JSON, nullable=True, default=list)  # Найденные root флаги
    user_methods = Column(Text, nullable=True)  # Методы получения user доступа
    root_methods = Column(Text, nullable=True)  # Методы получения root доступа
    
    # Разведка
    nmap_results = Column(Text, nullable=True)  # Результаты Nmap
    services_found = Column(JSON, nullable=True, default=list)  # Найденные сервисы
    vulnerabilities = Column(JSON, nullable=True, default=list)  # Найденные уязвимости
    
    # Заметки и writeup
    notes = Column(Text, nullable=True)  # Заметки в процессе
    writeup = Column(Text, nullable=True)  # Полный writeup
    screenshots = Column(JSON, nullable=True, default=list)  # Ссылки на скриншоты
    
    # Временные метки
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Связи
    project = relationship("Project", backref="ctf_machines")
    
    def to_dict(self):
        """Преобразование в словарь."""
        return {
            "id": self.id,
            "uuid": self.uuid,
            "project_id": self.project_id,
            "name": self.name,
            "platform": self.platform,
            "difficulty": self.difficulty,
            "os_type": self.os_type,
            "ip_address": self.ip_address,
            "status": self.status,
            "rank": self.rank,
            "points": self.points,
            "user_flags": self.user_flags,
            "root_flags": self.root_flags,
            "user_methods": self.user_methods,
            "root_methods": self.root_methods,
            "nmap_results": self.nmap_results,
            "services_found": self.services_found,
            "vulnerabilities": self.vulnerabilities,
            "notes": self.notes,
            "writeup": self.writeup,
            "screenshots": self.screenshots,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class ProjectGitSync(Base):
    """Модель для настройки Git синхронизации проекта."""
    
    __tablename__ = "project_git_sync"
    
    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(String(36), unique=True, nullable=False, index=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True, unique=True)
    
    # Настройки Git
    repo_url = Column(String(500), nullable=False)  # URL репозитория
    branch = Column(String(100), default="main")  # Ветка
    auth_type = Column(String(50), default="ssh")  # ssh, token, password
    
    # Аутентификация
    ssh_key_path = Column(String(500), nullable=True)  # Путь к SSH ключу
    token = Column(String(255), nullable=True)  # Токен доступа (encrypted)
    username = Column(String(100), nullable=True)  # Имя пользователя
    
    # Пути в репозитории
    reports_path = Column(String(255), default="reports")  # Путь для отчетов
    artifacts_path = Column(String(255), default="artifacts")  # Путь для артефактов
    ctf_path = Column(String(255), default="ctf")  # Путь для CTF writeups
    
    # Статус синхронизации
    last_sync = Column(DateTime(timezone=True), nullable=True)
    sync_status = Column(String(50), default="never")  # never, success, failed, syncing
    last_error = Column(Text, nullable=True)
    
    # Настройки
    auto_sync = Column(Boolean, default=False)  # Автосинхронизация
    sync_on_save = Column(Boolean, default=True)  # Синхронизация при сохранении
    
    # Временные метки
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Связи
    project = relationship("Project", backref="git_sync")
    
    def to_dict(self):
        """Преобразование в словарь."""
        return {
            "id": self.id,
            "uuid": self.uuid,
            "project_id": self.project_id,
            "repo_url": self.repo_url,
            "branch": self.branch,
            "auth_type": self.auth_type,
            "ssh_key_path": self.ssh_key_path,
            "token": "***" if self.token else None,  # Не показываем токен
            "username": self.username,
            "reports_path": self.reports_path,
            "artifacts_path": self.artifacts_path,
            "ctf_path": self.ctf_path,
            "last_sync": self.last_sync.isoformat() if self.last_sync else None,
            "sync_status": self.sync_status,
            "last_error": self.last_error,
            "auto_sync": self.auto_sync,
            "sync_on_save": self.sync_on_save,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


# Добавим обратную связь в модель Group
# Это будет сделано в models/group.py через back_populates
