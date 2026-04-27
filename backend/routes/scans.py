from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks, UploadFile, File, Body
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional, Dict
from backend.db.session import get_db
from backend.services.scan_service import ScanService
from backend.schemas.scan import ScanCreate, ScanUpdate, ScanResponse
import json
from datetime import datetime, timezone
from pydantic import BaseModel

router = APIRouter(tags=["scans"])
scans_router = router  # Алиас для совместимости импортов


class NmapScanRequest(BaseModel):
    target: Optional[str] = None
    ports: Optional[str] = None
    scripts: Optional[str] = None
    custom_args: Optional[str] = None
    known_ports_only: bool = False
    group_ids: Optional[List[int]] = None


class RustscanRequest(BaseModel):
    target: str
    ports: Optional[str] = None
    custom_args: Optional[str] = None
    run_nmap_after: bool = False
    nmap_args: Optional[str] = None


# ==========================================
# Специфичные маршруты (должны быть перед параметризированными!)
# ==========================================

@router.get("/status")
async def get_scans_status(db: AsyncSession = Depends(get_db)):
    """Получить статус очередей сканирований и историю заданий."""
    from backend.models.scan import ScanJob, Scan
    from sqlalchemy.orm import selectinload
    
    # Получаем все задачи сканирования
    jobs_query = select(ScanJob).options(
        selectinload(ScanJob.scan)
    ).order_by(ScanJob.created_at.desc()).limit(50)
    
    jobs_result = await db.execute(jobs_query)
    jobs = list(jobs_result.scalars().all())
    
    # Формируем очереди
    nmap_rustscan_queue = []
    utilities_queue = []
    
    for job in jobs:
        job_info = {
            "job_id": job.id,
            "scan_type": job.job_type,
            "target": job.scan.target if job.scan else "Unknown",
            "status": job.status
        }
        
        if job.job_type in ['nmap', 'rustscan']:
            nmap_rustscan_queue.append(job_info)
        else:
            utilities_queue.append(job_info)
    
    # Фильтруем активные задачи для очередей
    active_nmap = [j for j in nmap_rustscan_queue if j['status'] in ['pending', 'running', 'queued']]
    active_utilities = [j for j in utilities_queue if j['status'] in ['pending', 'running', 'queued']]
    
    # Текущая задача (первая running)
    current_nmap = next((j for j in active_nmap if j['status'] == 'running'), None)
    current_utility = next((j for j in active_utilities if j['status'] == 'running'), None)
    
    # Очередь задач (без running)
    queued_nmap = [j for j in active_nmap if j['status'] != 'running']
    queued_utilities = [j for j in active_utilities if j['status'] != 'running']
    
    # Формируем recent_jobs (последние 20 задач)
    recent_jobs = []
    for job in jobs[:20]:
        recent_jobs.append({
            "id": job.id,
            "scan_type": job.job_type,
            "target": job.scan.target if job.scan else "Unknown",
            "status": job.status,
            "progress": getattr(job.scan, 'progress', 0) if job.scan else 0,
            "created_at": job.created_at.isoformat() if job.created_at else None
        })
    
    return {
        "queues": {
            "nmap_rustscan": {
                "queue_length": len(queued_nmap),
                "current_job_id": current_nmap["job_id"] if current_nmap else None,
                "is_running": current_nmap is not None,
                "queued_jobs": queued_nmap
            },
            "utilities": {
                "queue_length": len(queued_utilities),
                "current_job_id": current_utility["job_id"] if current_utility else None,
                "is_running": current_utility is not None,
                "queued_jobs": queued_utilities
            }
        },
        "recent_jobs": recent_jobs
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
    request: NmapScanRequest,
    background_tasks: BackgroundTasks = None,
    db: AsyncSession = Depends(get_db)
):
    """Запустить сканирование Nmap."""
    from backend.models.scan import Scan, ScanJob
    from datetime import datetime, timezone
    import logging
    
    logger = logging.getLogger(__name__)
    logger.info(f"=== Получен запрос на Nmap сканирование ===")
    logger.info(f"Target: {request.target}")
    logger.info(f"Ports: {request.ports}")
    logger.info(f"Known ports only: {request.known_ports_only}")
    logger.info(f"Group IDs: {request.group_ids}")
    
    target = request.target or ""
    
    # Создаём запись сканирования
    new_scan = Scan(
        name=f"Nmap scan: {target[:50] if target else 'known ports'}",
        target=target or "known_ports_only",
        scan_type="nmap",
        status="pending",
        progress=0,
        created_at=datetime.now(timezone.utc)
    )
    
    db.add(new_scan)
    await db.commit()
    await db.refresh(new_scan)
    logger.info(f"Создана запись сканирования ID={new_scan.id}")
    
    # Создаём задачу сканирования
    new_job = ScanJob(
        scan_id=new_scan.id,
        job_type="nmap",
        status="pending",
        created_at=datetime.now(timezone.utc)
    )
    
    db.add(new_job)
    await db.commit()
    await db.refresh(new_job)
    logger.info(f"Создана задача сканирования ID={new_job.id}")
    logger.info(f"=== Сканирование успешно запущено ===")
    
    return {"message": f"Nmap сканирование запущено для {target}", "status": "queued", "job_id": new_job.id}


@router.post("/rustscan")
async def run_rustscan(
    request: RustscanRequest,
    background_tasks: BackgroundTasks = None,
    db: AsyncSession = Depends(get_db)
):
    """Запустить сканирование Rustscan."""
    from backend.models.scan import Scan, ScanJob
    from datetime import datetime, timezone
    import logging
    
    logger = logging.getLogger(__name__)
    logger.info(f"=== Получен запрос на Rustscan ===")
    logger.info(f"Target: {request.target}")
    logger.info(f"Ports: {request.ports}")
    logger.info(f"Run nmap after: {request.run_nmap_after}")
    
    # Создаём запись сканирования
    new_scan = Scan(
        name=f"Rustscan: {request.target[:50]}",
        target=request.target,
        scan_type="rustscan",
        status="pending",
        progress=0,
        created_at=datetime.now(timezone.utc)
    )
    
    db.add(new_scan)
    await db.commit()
    await db.refresh(new_scan)
    logger.info(f"Создана запись сканирования ID={new_scan.id}")
    
    # Создаём задачу сканирования
    new_job = ScanJob(
        scan_id=new_scan.id,
        job_type="rustscan",
        status="pending",
        created_at=datetime.now(timezone.utc)
    )
    
    db.add(new_job)
    await db.commit()
    await db.refresh(new_job)
    logger.info(f"Создана задача сканирования ID={new_job.id}")
    logger.info(f"=== Rustscan успешно запущен ===")
    
    return {"message": f"Rustscan запущен для {request.target}", "status": "queued", "job_id": new_job.id}


@router.post("/dig")
async def run_dig_scan(
    request: dict = Body(...),
    background_tasks: BackgroundTasks = None,
    db: AsyncSession = Depends(get_db)
):
    """Запустить DNS сканирование (dig)."""
    targets_text = request.get("targets_text", "")
    dns_server = request.get("dns_server")
    cli_args = request.get("cli_args")
    record_types = request.get("record_types")
    
    # Создаем новую задачу сканирования в БД
    from backend.models.scan import Scan
    from datetime import datetime
    
    new_scan = Scan(
        name=f"DNS scan: {targets_text[:50]}",
        target=targets_text,
        scan_type="dig",
        status="queued",
        created_at=datetime.now(timezone.utc)
    )
    
    db.add(new_scan)
    await db.commit()
    await db.refresh(new_scan)
    
    return {"message": "DNS сканирование запущено", "status": "queued", "job_id": new_scan.id}


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
    from backend.models.scan import ScanJob
    from sqlalchemy.orm import selectinload
    
    query = select(ScanJob).options(
        selectinload(ScanJob.scan)
    ).order_by(ScanJob.created_at.desc())
    
    result = await db.execute(query)
    jobs = list(result.scalars().all())
    
    return [{
        "id": job.id,
        "scan_id": job.scan_id,
        "job_type": job.job_type,
        "status": job.status,
        "target": job.scan.target if job.scan else "Unknown",
        "progress": getattr(job.scan, 'progress', 0) if job.scan else 0,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "completed_at": job.completed_at.isoformat() if job.completed_at else None
    } for job in jobs]


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
