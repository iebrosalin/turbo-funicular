from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks, UploadFile, File, Body
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional, Dict, Any
from backend.db.session import get_db
from backend.services.scan_service import ScanService
from backend.schemas.scan import ScanCreate, ScanUpdate, ScanResponse
import json

router = APIRouter(tags=["scans"])
scans_router = router  # Алиас для совместимости импортов


# ==========================================
# Специфичные маршруты (должны быть перед параметризированными!)
# ==========================================

@router.get("/status")
async def get_active_scans_status(db: AsyncSession = Depends(get_db)):
    """Получить статус активных сканирований и очередей."""
    service = ScanService(db)
    scans = await service.get_active()
    
    # Возвращаем структуру, ожидаемую фронтендом
    return {
        "queues": {
            "nmap_rustscan": {
                "queue_length": 0,
                "current_job_id": None,
                "is_running": False,
                "queued_jobs": []
            },
            "utilities": {
                "queue_length": 0,
                "current_job_id": None,
                "is_running": False,
                "queued_jobs": []
            }
        },
        "recent_jobs": [],
        "active_scans": scans
    }


@router.get("/active", response_model=List[ScanResponse])
async def get_active_scans(db: AsyncSession = Depends(get_db)):
    """Получить активные сканирования."""
    service = ScanService(db)
    scans = await service.get_active()
    return scans


@router.get("/history", response_model=List[ScanResponse])
async def get_scan_history(db: AsyncSession = Depends(get_db)):
    """Получить историю сканирований (алиас для корня)."""
    service = ScanService(db)
    scans = await service.get_all()
    return scans


# ==========================================
# Маршруты для импорта и запуска сканирований
# ==========================================

@router.post("/import")
async def import_scan(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db)
):
    """Импортировать результаты сканирования из файла."""
    try:
        content = await file.read()
        # Здесь должна быть логика парсинга файла
        return {"message": "Файл загружен", "filename": file.filename, "size": len(content)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка импорта: {str(e)}")


@router.post("/import-xml")
async def import_xml_scan(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db)
):
    """Импортировать XML результаты сканирования (nmap)."""
    try:
        content = await file.read()
        # Здесь должна быть логика парсинга Nmap XML
        return {"message": "XML файл загружен", "filename": file.filename}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка импорта XML: {str(e)}")


@router.post("/nmap")
async def run_nmap_scan(
    target: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """Запустить сканирование Nmap."""
    # Заглушка для реального сканирования
    return {"message": f"Nmap сканирование запущено для {target}", "status": "queued"}


@router.post("/rustscan")
async def run_rustscan(
    target: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """Запустить сканирование Rustscan."""
    # Заглушка для реального сканирования
    return {"message": f"Rustscan запущен для {target}", "status": "queued"}


@router.post("/dig")
async def run_dig_scan(
    request_data: Dict[str, Any] = Body(...),
    background_tasks: BackgroundTasks = None,
    db: AsyncSession = Depends(get_db)
):
    """Запустить DNS сканирование (dig)."""
    # Заглушка для реального сканирования
    target = request_data.get("targets_text", "unknown")
    return {"message": f"DNS сканирование запущено для {target}", "status": "queued"}


# ==========================================
# Маршруты очереди сканирований (scan-queue)
# ==========================================

@router.get("/scan-queue")
async def get_scan_queue(db: AsyncSession = Depends(get_db)):
    """Получить очередь сканирований."""
    # Заглушка - возвращаем пустой список
    return []


@router.get("/scan-queue/{job_id}")
async def get_scan_queue_job(job_id: int, db: AsyncSession = Depends(get_db)):
    """Получить задачу из очереди сканирований."""
    # Заглушка
    raise HTTPException(status_code=404, detail="Задача не найдена")


@router.delete("/scan-queue/{job_id}")
async def cancel_scan_queue_job(job_id: int, db: AsyncSession = Depends(get_db)):
    """Отменить задачу в очереди сканирований."""
    return {"message": f"Задача {job_id} отменена"}


# ==========================================
# Маршруты задач сканирований (scan-job)
# ==========================================

@router.get("/scan-job")
async def get_scan_jobs(db: AsyncSession = Depends(get_db)):
    """Получить все задачи сканирований."""
    # Заглушка - возвращаем пустой список
    return []


@router.get("/scan-job/{job_id}")
async def get_scan_job(job_id: int, db: AsyncSession = Depends(get_db)):
    """Получить задачу сканирования."""
    # Заглушка
    raise HTTPException(status_code=404, detail="Задача не найдена")


@router.delete("/scan-job/{job_id}")
async def delete_scan_job(job_id: int, db: AsyncSession = Depends(get_db)):
    """Удалить задачу сканирования."""
    return {"message": f"Задача {job_id} удалена"}


@router.post("/scan-job/{job_id}/stop")
async def stop_scan_job(job_id: int, db: AsyncSession = Depends(get_db)):
    """Остановить задачу сканирования."""
    return {"message": f"Задача {job_id} остановлена"}


@router.post("/scan-job/{job_id}/retry")
async def retry_scan_job(job_id: int, db: AsyncSession = Depends(get_db)):
    """Повторить задачу сканирования."""
    return {"message": f"Задача {job_id} повторена"}


@router.get("/scan-job/{job_id}/download/{format}")
async def download_scan_job_result(job_id: int, format: str, db: AsyncSession = Depends(get_db)):
    """Скачать результаты задачи сканирования в указанном формате."""
    # Заглушка
    raise HTTPException(status_code=404, detail="Результаты не найдены")


# ==========================================
# Основные маршруты сканирований (параметризированные - должны быть в конце!)
# ==========================================

@router.get("", response_model=List[ScanResponse])
async def get_scans(db: AsyncSession = Depends(get_db)):
    """Получить все сканирования (алиас для /history)."""
    service = ScanService(db)
    scans = await service.get_all()
    return scans


@router.get("/{scan_id}/results", response_model=ScanResponse)
async def get_scan_results(scan_id: int, db: AsyncSession = Depends(get_db)):
    """Получить результаты сканирования по ID (алиас для /{scan_id})."""
    service = ScanService(db)
    scan = await service.get_by_id(scan_id)
    if not scan:
        raise HTTPException(status_code=404, detail="Сканирование не найдено")
    return scan


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
