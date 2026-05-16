from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Body
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from sqlalchemy.orm import selectinload
from typing import List, Optional
import os
import uuid
import hashlib
import logging
from datetime import datetime, timezone

from backend.db.session import get_db
from backend.db.project_db_manager import project_db_manager, get_project_db
from backend.models.project import Project, ProjectReport, ProjectArtifact, ProjectScanSession, CTFMachine, ProjectGitSync, project_groups
from backend.models.group import Group
from backend.schemas.project import (
    ProjectCreate, ProjectUpdate, ProjectResponse,
    ProjectReportCreate, ProjectReportUpdate, ProjectReportResponse,
    ProjectArtifactCreate, ProjectArtifactUpdate, ProjectArtifactResponse,
    ProjectScanSessionCreate, ProjectScanSessionUpdate, ProjectScanSessionResponse,
    CTFMachineCreate, CTFMachineUpdate, CTFMachineResponse,
    ProjectGitSyncCreate, ProjectGitSyncUpdate, ProjectGitSyncResponse
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/projects", tags=["Projects"])


# ===== Helper Functions =====

def calculate_file_checksum(file_path: str) -> str:
    """Вычислить SHA256 хэш файла."""
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()


def get_artifact_storage_path() -> str:
    """Получить путь к хранилищу артефактов."""
    base_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "artifacts")
    os.makedirs(base_path, exist_ok=True)
    return base_path


# ===== Project Routes =====

@router.get("", response_model=List[ProjectResponse])
async def get_projects(
    skip: int = 0,
    limit: int = 100,
    status_filter: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """Получить список всех проектов."""
    query = select(Project).options(
        selectinload(Project.groups),
        selectinload(Project.reports),
        selectinload(Project.artifacts)
    )
    
    if status_filter:
        query = query.where(Project.status == status_filter)
    
    query = query.offset(skip).limit(limit)
    result = await db.execute(query)
    projects = result.scalars().all()
    
    return projects


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(project_id: int, db: AsyncSession = Depends(get_db)):
    """Получить проект по ID."""
    query = select(Project).where(Project.id == project_id).options(
        selectinload(Project.groups),
        selectinload(Project.reports),
        selectinload(Project.artifacts),
        selectinload(Project.scan_sessions)
    )
    result = await db.execute(query)
    project = result.scalar_one_or_none()
    
    if not project:
        raise HTTPException(status_code=404, detail="Проект не найден")
    
    return project


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    project_data: ProjectCreate,
    db: AsyncSession = Depends(get_db)
):
    """Создать новый проект."""
    # Создаём проект
    project = Project(
        name=project_data.name,
        description=project_data.description,
        customer=project_data.customer,
        project_type=project_data.project_type,
        status=project_data.status.value if project_data.status else "planning",
        priority=project_data.priority.value if project_data.priority else "medium",
        start_date=project_data.start_date,
        end_date=project_data.end_date,
    )
    
    db.add(project)
    await db.flush()
    
    # Привязываем группы если указаны
    if project_data.group_ids:
        groups_query = select(Group).where(Group.id.in_(project_data.group_ids))
        groups_result = await db.execute(groups_query)
        groups = groups_result.scalars().all()
        project.groups.extend(groups)
    
    await db.commit()
    await db.refresh(project)
    
    # Создаем отдельную базу данных для проекта
    try:
        await project_db_manager.create_project_database(project.id)
        logger.info(f"✅ Создана БД для проекта {project.id}")
    except Exception as e:
        logger.error(f"⚠️ Ошибка создания БД для проекта {project.id}: {e}")
        # Не прерываем создание проекта, просто логируем ошибку
    
    return project


@router.put("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: int,
    project_data: ProjectUpdate,
    db: AsyncSession = Depends(get_db)
):
    """Обновить проект."""
    query = select(Project).where(Project.id == project_id)
    result = await db.execute(query)
    project = result.scalar_one_or_none()
    
    if not project:
        raise HTTPException(status_code=404, detail="Проект не найден")
    
    # Обновляем поля
    update_data = project_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if field == "group_ids":
            continue  # Обрабатываем отдельно
        if hasattr(project, field):
            if isinstance(value, Enum):
                setattr(project, field, value.value)
            else:
                setattr(project, field, value)
    
    # Обновляем группы если указаны
    if project_data.group_ids is not None:
        groups_query = select(Group).where(Group.id.in_(project_data.group_ids))
        groups_result = await db.execute(groups_query)
        groups = groups_result.scalars().all()
        project.groups = groups
    
    await db.commit()
    await db.refresh(project)
    
    return project


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(project_id: int, db: AsyncSession = Depends(get_db)):
    """Удалить проект."""
    query = select(Project).where(Project.id == project_id)
    result = await db.execute(query)
    project = result.scalar_one_or_none()
    
    if not project:
        raise HTTPException(status_code=404, detail="Проект не найден")
    
    # Удаляем базу данных проекта если она существует
    try:
        await project_db_manager.delete_project_database(project_id)
        logger.info(f"✅ Удалена БД для проекта {project_id}")
    except Exception as e:
        logger.error(f"⚠️ Ошибка удаления БД для проекта {project_id}: {e}")
    
    await db.delete(project)
    await db.commit()
    
    return None


# ===== Project Report Routes =====

@router.get("/{project_id}/reports", response_model=List[ProjectReportResponse])
async def get_project_reports(project_id: int, db: AsyncSession = Depends(get_db)):
    """Получить все отчёты проекта."""
    # Проверяем существование проекта
    project_query = select(Project).where(Project.id == project_id)
    project_result = await db.execute(project_query)
    project = project_result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Проект не найден")
    
    # Используем БД проекта для получения отчётов
    async with project_db_manager.get_project_session(project_id) as project_db:
        query = select(ProjectReport).order_by(
            ProjectReport.created_at.desc()
        )
        result = await project_db.execute(query)
        reports = result.scalars().all()
    
    return reports


@router.get("/{project_id}/reports/{report_id}", response_model=ProjectReportResponse)
async def get_project_report(project_id: int, report_id: int, db: AsyncSession = Depends(get_db)):
    """Получить отчёт по ID."""
    # Проверяем существование проекта
    project_query = select(Project).where(Project.id == project_id)
    project_result = await db.execute(project_query)
    project = project_result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Проект не найден")
    
    # Используем БД проекта
    async with project_db_manager.get_project_session(project_id) as project_db:
        query = select(ProjectReport).where(ProjectReport.id == report_id)
        result = await project_db.execute(query)
        report = result.scalar_one_or_none()
    
    if not report:
        raise HTTPException(status_code=404, detail="Отчёт не найден")
    
    return report


@router.post("/{project_id}/reports", response_model=ProjectReportResponse, status_code=status.HTTP_201_CREATED)
async def create_project_report(
    project_id: int,
    report_data: ProjectReportCreate,
    db: AsyncSession = Depends(get_db)
):
    """Создать новый отчёт для проекта."""
    # Проверяем существование проекта
    project_query = select(Project).where(Project.id == project_id)
    project_result = await db.execute(project_query)
    project = project_result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Проект не найден")
    
    # Создаём отчёт в БД проекта
    async with project_db_manager.get_project_session(project_id) as project_db:
        report = ProjectReport(
            project_id=project_id,
            title=report_data.title,
            report_type=report_data.report_type.value if report_data.report_type else "general",
            content=report_data.content,
            is_final=report_data.is_final,
            tags=report_data.tags or [],
            obsidian_tags=report_data.obsidian_tags,
        )
        
        project_db.add(report)
        await project_db.commit()
        await project_db.refresh(report)
    
    return report


@router.put("/{project_id}/reports/{report_id}", response_model=ProjectReportResponse)
async def update_project_report(
    project_id: int,
    report_id: int,
    report_data: ProjectReportUpdate,
    db: AsyncSession = Depends(get_db)
):
    """Обновить отчёт."""
    # Проверяем существование проекта
    project_query = select(Project).where(Project.id == project_id)
    project_result = await db.execute(project_query)
    project = project_result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Проект не найден")
    
    # Используем БД проекта
    async with project_db_manager.get_project_session(project_id) as project_db:
        query = select(ProjectReport).where(ProjectReport.id == report_id)
        result = await project_db.execute(query)
        report = result.scalar_one_or_none()
        
        if not report:
            raise HTTPException(status_code=404, detail="Отчёт не найден")
        
        # Обновляем поля
        update_data = report_data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            if hasattr(report, field):
                if isinstance(value, Enum):
                    setattr(report, field, value.value)
                else:
                    setattr(report, field, value)
        
        # Автоинкремент версии при обновлении контента
        if report_data.content is not None and report_data.version is None:
            report.version += 1
        
        await project_db.commit()
        await project_db.refresh(report)
    
    return report


@router.delete("/{project_id}/reports/{report_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project_report(project_id: int, report_id: int, db: AsyncSession = Depends(get_db)):
    """Удалить отчёт."""
    # Проверяем существование проекта
    project_query = select(Project).where(Project.id == project_id)
    project_result = await db.execute(project_query)
    project = project_result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Проект не найден")
    
    # Используем БД проекта
    async with project_db_manager.get_project_session(project_id) as project_db:
        query = select(ProjectReport).where(ProjectReport.id == report_id)
        result = await project_db.execute(query)
        report = result.scalar_one_or_none()
        
        if not report:
            raise HTTPException(status_code=404, detail="Отчёт не найден")
        
        await project_db.delete(report)
        await project_db.commit()
    
    return None


@router.get("/{project_id}/reports/{report_id}/export")
async def export_project_report(project_id: int, report_id: int, db: AsyncSession = Depends(get_db)):
    """Экспортировать отчёт в Markdown файл (для Obsidian)."""
    # Проверяем существование проекта
    project_query = select(Project).where(Project.id == project_id)
    project_result = await db.execute(project_query)
    project = project_result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Проект не найден")
    
    # Используем БД проекта
    async with project_db_manager.get_project_session(project_id) as project_db:
        query = select(ProjectReport).where(ProjectReport.id == report_id)
        result = await project_db.execute(query)
        report = result.scalar_one_or_none()
    
    if not report:
        raise HTTPException(status_code=404, detail="Отчёт не найден")
    
    # Формируем Markdown контент с Front Matter для Obsidian
    front_matter = []
    front_matter.append("---")
    front_matter.append(f"title: {report.title}")
    front_matter.append(f"created: {report.created_at.strftime('%Y-%m-%d %H:%M')}")
    if report.updated_at:
        front_matter.append(f"updated: {report.updated_at.strftime('%Y-%m-%d %H:%M')}")
    if report.tags:
        front_matter.append(f"tags: [{', '.join(report.tags)}]")
    if report.obsidian_tags:
        front_matter.append(f"obsidian_tags: {report.obsidian_tags}")
    front_matter.append("---")
    front_matter.append("")
    
    markdown_content = "\n".join(front_matter) + report.content
    
    # Возвращаем как файл
    filename = f"{report.title.replace(' ', '_')}.md"
    
    return StreamingResponse(
        iter([markdown_content.encode('utf-8')]),
        media_type="text/markdown",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


# ===== Project Artifact Routes =====

@router.get("/{project_id}/artifacts", response_model=List[ProjectArtifactResponse])
async def get_project_artifacts(project_id: int, db: AsyncSession = Depends(get_db)):
    """Получить все артефакты проекта."""
    # Проверяем существование проекта
    project_query = select(Project).where(Project.id == project_id)
    project_result = await db.execute(project_query)
    project = project_result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Проект не найден")
    
    # Используем БД проекта
    async with project_db_manager.get_project_session(project_id) as project_db:
        query = select(ProjectArtifact).order_by(
            ProjectArtifact.created_at.desc()
        )
        result = await project_db.execute(query)
        artifacts = result.scalars().all()
    
    return artifacts


@router.post("/{project_id}/artifacts", response_model=ProjectArtifactResponse, status_code=status.HTTP_201_CREATED)
async def upload_project_artifact(
    project_id: int,
    file: UploadFile = File(...),
    name: Optional[str] = Body(None),
    description: Optional[str] = Body(None),
    artifact_type: Optional[str] = Body("file"),
    category: Optional[str] = Body(None),
    tags: Optional[List[str]] = Body(None),
    scan_id: Optional[int] = Body(None),
    db: AsyncSession = Depends(get_db)
):
    """Загрузить артефакт для проекта."""
    # Проверяем существование проекта
    project_query = select(Project).where(Project.id == project_id)
    project_result = await db.execute(project_query)
    project = project_result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Проект не найден")
    
    # Сохраняем файл
    storage_path = get_artifact_storage_path()
    project_uuid = str(uuid.uuid4())
    file_extension = os.path.splitext(file.filename)[1] if file.filename else ""
    unique_filename = f"{project_uuid}{file_extension}"
    file_path = os.path.join(storage_path, unique_filename)
    
    # Читаем и сохраняем файл
    content = await file.read()
    with open(file_path, "wb") as f:
        f.write(content)
    
    # Вычисляем хэш
    checksum = hashlib.sha256(content).hexdigest()
    
    # Создаём запись об артефакте в БД проекта
    async with project_db_manager.get_project_session(project_id) as project_db:
        artifact = ProjectArtifact(
            project_id=project_id,
            name=name or file.filename or "unnamed",
            description=description,
            artifact_type=artifact_type or "file",
            file_path=file_path,
            file_size=len(content),
            mime_type=file.content_type,
            checksum=checksum,
            category=category,
            tags=tags or [],
            scan_id=scan_id,
            uploaded_at=datetime.now(timezone.utc),
        )
        
        project_db.add(artifact)
        await project_db.commit()
        await project_db.refresh(artifact)
    
    return artifact


@router.get("/{project_id}/artifacts/{artifact_id}")
async def download_project_artifact(project_id: int, artifact_id: int, db: AsyncSession = Depends(get_db)):
    """Скачать артефакт."""
    # Проверяем существование проекта
    project_query = select(Project).where(Project.id == project_id)
    project_result = await db.execute(project_query)
    project = project_result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Проект не найден")
    
    # Используем БД проекта
    async with project_db_manager.get_project_session(project_id) as project_db:
        query = select(ProjectArtifact).where(ProjectArtifact.id == artifact_id)
        result = await project_db.execute(query)
        artifact = result.scalar_one_or_none()
    
    if not artifact:
        raise HTTPException(status_code=404, detail="Артефакт не найден")
    
    if not os.path.exists(artifact.file_path):
        raise HTTPException(status_code=404, detail="Файл не найден на диске")
    
    return FileResponse(
        artifact.file_path,
        media_type=artifact.mime_type or "application/octet-stream",
        filename=artifact.name
    )


@router.delete("/{project_id}/artifacts/{artifact_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project_artifact(project_id: int, artifact_id: int, db: AsyncSession = Depends(get_db)):
    """Удалить артефакт."""
    # Проверяем существование проекта
    project_query = select(Project).where(Project.id == project_id)
    project_result = await db.execute(project_query)
    project = project_result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Проект не найден")
    
    # Используем БД проекта
    async with project_db_manager.get_project_session(project_id) as project_db:
        query = select(ProjectArtifact).where(ProjectArtifact.id == artifact_id)
        result = await project_db.execute(query)
        artifact = result.scalar_one_or_none()
        
        if not artifact:
            raise HTTPException(status_code=404, detail="Артефакт не найден")
        
        # Удаляем файл с диска
        if os.path.exists(artifact.file_path):
            os.remove(artifact.file_path)
        
        await project_db.delete(artifact)
        await project_db.commit()
    
    return None


# ===== Project Scan Session Routes =====

@router.get("/{project_id}/sessions", response_model=List[ProjectScanSessionResponse])
async def get_project_scan_sessions(project_id: int, db: AsyncSession = Depends(get_db)):
    """Получить все сессии сканирования проекта."""
    # Проверяем существование проекта
    project_query = select(Project).where(Project.id == project_id)
    project_result = await db.execute(project_query)
    project = project_result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Проект не найден")
    
    # Используем БД проекта
    async with project_db_manager.get_project_session(project_id) as project_db:
        query = select(ProjectScanSession).order_by(
            ProjectScanSession.created_at.desc()
        )
        result = await project_db.execute(query)
        sessions = result.scalars().all()
    
    return sessions


@router.post("/{project_id}/sessions", response_model=ProjectScanSessionResponse, status_code=status.HTTP_201_CREATED)
async def create_project_scan_session(
    project_id: int,
    session_data: ProjectScanSessionCreate,
    db: AsyncSession = Depends(get_db)
):
    """Создать новую сессию сканирования для проекта."""
    # Проверяем существование проекта
    project_query = select(Project).where(Project.id == project_id)
    project_result = await db.execute(project_query)
    project = project_result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Проект не найден")
    
    # Создаём сессию в БД проекта
    async with project_db_manager.get_project_session(project_id) as project_db:
        session = ProjectScanSession(
            project_id=project_id,
            name=session_data.name,
            description=session_data.description,
            session_type=session_data.session_type.value if session_data.session_type else "manual",
            utilities_used=session_data.utilities_used or [],
            parameters=session_data.parameters or {},
            targets=session_data.targets or [],
            results_summary=session_data.results_summary,
            scan_ids=session_data.scan_ids or [],
        )
        
        project_db.add(session)
        await project_db.commit()
        await project_db.refresh(session)
    
    return session


@router.put("/{project_id}/sessions/{session_id}", response_model=ProjectScanSessionResponse)
async def update_project_scan_session(
    project_id: int,
    session_id: int,
    session_data: ProjectScanSessionUpdate,
    db: AsyncSession = Depends(get_db)
):
    """Обновить сессию сканирования."""
    # Проверяем существование проекта
    project_query = select(Project).where(Project.id == project_id)
    project_result = await db.execute(project_query)
    project = project_result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Проект не найден")
    
    # Используем БД проекта
    async with project_db_manager.get_project_session(project_id) as project_db:
        query = select(ProjectScanSession).where(ProjectScanSession.id == session_id)
        result = await project_db.execute(query)
        session = result.scalar_one_or_none()
        
        if not session:
            raise HTTPException(status_code=404, detail="Сессия не найдена")
        
        # Обновляем поля
        update_data = session_data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            if hasattr(session, field):
                if isinstance(value, Enum):
                    setattr(session, field, value.value)
                else:
                    setattr(session, field, value)
        
        await project_db.commit()
        await project_db.refresh(session)
    
    return session


@router.delete("/{project_id}/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project_scan_session(project_id: int, session_id: int, db: AsyncSession = Depends(get_db)):
    """Удалить сессию сканирования."""
    # Проверяем существование проекта
    project_query = select(Project).where(Project.id == project_id)
    project_result = await db.execute(project_query)
    project = project_result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Проект не найден")
    
    # Используем БД проекта
    async with project_db_manager.get_project_session(project_id) as project_db:
        query = select(ProjectScanSession).where(ProjectScanSession.id == session_id)
        result = await project_db.execute(query)
        session = result.scalar_one_or_none()
        
        if not session:
            raise HTTPException(status_code=404, detail="Сессия не найдена")
        
        await project_db.delete(session)
        await project_db.commit()
    
    return None
