"""
Менеджер управления базами данных проектов.
Каждый проект имеет свою собственную SQLite базу данных для изоляции данных.
"""
import os
import asyncio
from pathlib import Path
from typing import Optional, Dict
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from contextlib import asynccontextmanager
import logging

from backend.core.config import settings

logger = logging.getLogger(__name__)


class ProjectDatabaseManager:
    """Менеджер баз данных проектов."""
    
    def __init__(self):
        self.projects_dir = Path(settings.INSTANCE_DIR) / "projects"
        self.projects_dir.mkdir(parents=True, exist_ok=True)
        
        # Кэш подключений к БД проектов
        self._project_engines: Dict[int, any] = {}
        self._project_async_engines: Dict[int, any] = {}
        self._project_session_makers: Dict[int, any] = {}
        self._project_async_session_makers: Dict[int, any] = {}
    
    def get_project_db_path(self, project_id: int) -> Path:
        """Получить путь к базе данных проекта."""
        return self.projects_dir / f"project_{project_id}.db"
    
    def get_project_db_url(self, project_id: int) -> str:
        """Получить URL базы данных проекта."""
        db_path = self.get_project_db_path(project_id)
        return f"sqlite+aiosqlite:///{db_path}"
    
    def get_project_sync_db_url(self, project_id: int) -> str:
        """Получить синхронный URL базы данных проекта."""
        db_path = self.get_project_db_path(project_id)
        return f"sqlite:///{db_path}"
    
    async def get_project_engine(self, project_id: int):
        """Получить асинхронный движок БД проекта."""
        if project_id not in self._project_async_engines:
            db_url = self.get_project_db_url(project_id)
            engine = create_async_engine(
                db_url,
                echo=False,
                pool_pre_ping=True,
                connect_args={"check_same_thread": False}
            )
            self._project_async_engines[project_id] = engine
            logger.info(f"✅ Создан асинхронный движок для проекта {project_id}")
        return self._project_async_engines[project_id]
    
    def get_project_sync_engine(self, project_id: int):
        """Получить синхронный движок БД проекта."""
        if project_id not in self._project_engines:
            db_url = self.get_project_sync_db_url(project_id)
            engine = create_engine(
                db_url,
                echo=False,
                pool_pre_ping=True,
                connect_args={"check_same_thread": False}
            )
            self._project_engines[project_id] = engine
            logger.info(f"✅ Создан синхронный движок для проекта {project_id}")
        return self._project_engines[project_id]
    
    async def get_project_session_maker(self, project_id: int):
        """Получить фабрику сессий для проекта."""
        if project_id not in self._project_async_session_makers:
            engine = await self.get_project_engine(project_id)
            session_maker = async_sessionmaker(
                engine,
                class_=AsyncSession,
                expire_on_commit=False,
                autocommit=False,
                autoflush=True
            )
            self._project_async_session_makers[project_id] = session_maker
        return self._project_async_session_makers[project_id]
    
    def get_project_sync_session_maker(self, project_id: int):
        """Получить синхронную фабрику сессий для проекта."""
        if project_id not in self._project_session_makers:
            engine = self.get_project_sync_engine(project_id)
            session_maker = sessionmaker(
                bind=engine,
                autocommit=False,
                expire_on_commit=False
            )
            self._project_session_makers[project_id] = session_maker
        return self._project_session_makers[project_id]
    
    @asynccontextmanager
    async def get_project_session(self, project_id: int):
        """Контекстный менеджер для получения сессии БД проекта."""
        session_maker = await self.get_project_session_maker(project_id)
        async with session_maker() as session:
            try:
                yield session
                await session.commit()
            except Exception as e:
                await session.rollback()
                logger.error(f"Ошибка в сессии проекта {project_id}: {e}")
                raise
            finally:
                await session.close()
    
    @asynccontextmanager
    def get_project_sync_session(self, project_id: int):
        """Контекстный менеджер для получения синхронной сессии БД проекта."""
        session_maker = self.get_project_sync_session_maker(project_id)
        with session_maker() as session:
            try:
                yield session
                session.commit()
            except Exception as e:
                session.rollback()
                logger.error(f"Ошибка в синхронной сессии проекта {project_id}: {e}")
                raise
            finally:
                session.close()
    
    async def create_project_database(self, project_id: int):
        """Создать базу данных для проекта."""
        from backend.db.base import Base
        from backend.models.project import ProjectReport, ProjectArtifact, ProjectScanSession
        
        sync_engine = self.get_project_sync_engine(project_id)
        
        # Создаем все таблицы
        Base.metadata.create_all(bind=sync_engine)
        
        logger.info(f"✅ База данных создана для проекта {project_id}")
        return self.get_project_db_path(project_id)
    
    async def delete_project_database(self, project_id: int):
        """Удалить базу данных проекта."""
        db_path = self.get_project_db_path(project_id)
        
        # Закрываем подключения если они есть
        if project_id in self._project_async_engines:
            await self._project_async_engines[project_id].dispose()
            del self._project_async_engines[project_id]
        
        if project_id in self._project_engines:
            self._project_engines[project_id].dispose()
            del self._project_engines[project_id]
        
        # Очищаем кэш сессий
        self._project_async_session_makers.pop(project_id, None)
        self._project_session_makers.pop(project_id, None)
        
        # Удаляем файл БД
        if db_path.exists():
            db_path.unlink()
            logger.info(f"✅ База данных удалена для проекта {project_id}")
        
        return True
    
    def project_database_exists(self, project_id: int) -> bool:
        """Проверить существует ли база данных проекта."""
        db_path = self.get_project_db_path(project_id)
        return db_path.exists()
    
    async def close_all(self):
        """Закрыть все подключения к проектным БД."""
        for project_id, engine in list(self._project_async_engines.items()):
            await engine.dispose()
        
        for project_id, engine in list(self._project_engines.items()):
            engine.dispose()
        
        self._project_async_engines.clear()
        self._project_engines.clear()
        self._project_async_session_makers.clear()
        self._project_session_makers.clear()
        
        logger.info("✅ Все подключения к проектным БД закрыты")


# Глобальный экземпляр менеджера
project_db_manager = ProjectDatabaseManager()


async def get_project_db(project_id: int):
    """Dependency для получения сессии БД проекта."""
    async with project_db_manager.get_project_session(project_id) as session:
        yield session
