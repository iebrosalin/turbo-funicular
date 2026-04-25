from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from typing import List, Optional
from datetime import datetime
from app.models.scan import Scan
from app.schemas.scan import ScanCreate, ScanUpdate


class ScanService:
    """Сервис для управления сканированиями."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def get_all(self) -> List[Scan]:
        """Получить все сканирования."""
        query = select(Scan).options(selectinload(Scan.group)).order_by(Scan.created_at.desc())
        result = await self.db.execute(query)
        return list(result.scalars().all())
    
    async def get_active(self) -> List[Scan]:
        """Получить активные сканирования."""
        query = select(Scan).where(Scan.status.in_(["pending", "running"])).order_by(Scan.created_at.desc())
        result = await self.db.execute(query)
        return list(result.scalars().all())
    
    async def get_by_id(self, scan_id: int) -> Optional[Scan]:
        """Получить сканирование по ID."""
        query = select(Scan).where(Scan.id == scan_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()
    
    async def create(self, scan_data: ScanCreate) -> Scan:
        """Создать новое сканирование."""
        scan = Scan(**scan_data.model_dump())
        self.db.add(scan)
        await self.db.flush()
        await self.db.refresh(scan)
        return scan
    
    async def update(self, scan_id: int, scan_data: ScanUpdate) -> Optional[Scan]:
        """Обновить сканирование."""
        scan = await self.get_by_id(scan_id)
        if not scan:
            return None
        
        update_data = scan_data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(scan, field, value)
        
        # Автоматически устанавливаем время завершения при изменении статуса
        if scan_data.status == "completed" and not scan.completed_at:
            scan.completed_at = datetime.utcnow()
        elif scan_data.status == "running" and not scan.started_at:
            scan.started_at = datetime.utcnow()
        
        await self.db.flush()
        await self.db.refresh(scan)
        return scan
    
    async def delete(self, scan_id: int) -> bool:
        """Удалить сканирование."""
        query = delete(Scan).where(Scan.id == scan_id)
        result = await self.db.execute(query)
        await self.db.flush()
        return result.rowcount > 0
