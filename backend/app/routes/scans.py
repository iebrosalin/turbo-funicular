from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from app.db.session import get_db
from app.services.scan_service import ScanService
from app.schemas.scan import ScanCreate, ScanUpdate, ScanResponse

router = APIRouter(prefix="/api/scans", tags=["scans"])


@router.get("", response_model=List[ScanResponse])
async def get_scans(db: AsyncSession = Depends(get_db)):
    """Получить все сканирования."""
    service = ScanService(db)
    scans = await service.get_all()
    return scans


@router.get("/active", response_model=List[ScanResponse])
async def get_active_scans(db: AsyncSession = Depends(get_db)):
    """Получить активные сканирования."""
    service = ScanService(db)
    scans = await service.get_active()
    return scans


@router.get("/{scan_id}", response_model=ScanResponse)
async def get_scan(scan_id: int, db: AsyncSession = Depends(get_db)):
    """Получить сканирование по ID."""
    service = ScanService(db)
    scan = await service.get_by_id(scan_id)
    if not scan:
        raise HTTPException(status_code=404, detail="Сканирование не найдено")
    return scan


@router.post("", response_model=ScanResponse, status_code=status.HTTP_201_CREATED)
async def create_scan(
    scan_data: ScanCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """Создать новое сканирование."""
    service = ScanService(db)
    scan = await service.create(scan_data)
    
    # Запуск сканирования в фоне (заглушка для реальной логики)
    # background_tasks.add_task(run_scan_task, scan.id)
    
    return scan


@router.put("/{scan_id}", response_model=ScanResponse)
async def update_scan(scan_id: int, scan_data: ScanUpdate, db: AsyncSession = Depends(get_db)):
    """Обновить сканирование."""
    service = ScanService(db)
    scan = await service.update(scan_id, scan_data)
    if not scan:
        raise HTTPException(status_code=404, detail="Сканирование не найдено")
    return scan


@router.delete("/{scan_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_scan(scan_id: int, db: AsyncSession = Depends(get_db)):
    """Удалить сканирование."""
    service = ScanService(db)
    success = await service.delete(scan_id)
    if not success:
        raise HTTPException(status_code=404, detail="Сканирование не найдено")
