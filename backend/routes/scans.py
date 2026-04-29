from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks, UploadFile, File, Body, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from typing import List, Optional, Dict, AsyncGenerator
import asyncio
import json
import logging
from backend.db.session import get_db, async_session_maker
from backend.services.scan_service import ScanService
from backend.schemas.scan import ScanCreate, ScanUpdate, ScanResponse
from backend.models.scan import ScanJob
from datetime import datetime, timezone
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# Middleware для логирования всех входящих запросов к сканированиям
async def log_scan_request(request: Request, call_next):
    """Логирование входящих запросов для отладки."""
    if request.url.path.startswith('/api/scans/') and request.method == 'POST':
        logger.info("=" * 80)
        logger.info(f"ВХОДЯЩИЙ ЗАПРОС: {request.method} {request.url.path}")
        logger.info(f"Headers: {dict(request.headers)}")
        try:
            body = await request.body()
            logger.info(f"Body: {body.decode('utf-8')}")
        except Exception as e:
            logger.warning(f"Не удалось прочитать тело запроса: {e}")
        logger.info("=" * 80)
    return await call_next(request)

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


class DigScanRequest(BaseModel):
    targets_text: str
    dns_server: Optional[str] = None
    cli_args: Optional[str] = None
    record_types: Optional[str] = None


# ==========================================
# Специфичные маршруты (должны быть перед параметризированными!)
# ==========================================

@router.get("/status")
async def get_scans_status(db: AsyncSession = Depends(get_db)):
    """Получить статус очередей сканирований и историю заданий."""
    from models.scan import ScanJob, Scan
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


async def scan_event_generator() -> AsyncGenerator[str, None]:
    """Генератор событий для SSE (Server-Sent Events)."""
    last_statuses = {}
    
    while True:
        try:
            # Создаем сессию явно для каждой итерации
            async with async_session_maker() as db:
                # Получаем все активные задачи
                query = select(ScanJob).where(
                    ScanJob.status.in_(['pending', 'running', 'queued'])
                ).options(selectinload(ScanJob.scan))
                
                result = await db.execute(query)
                jobs = result.scalars().all()
                
                for job in jobs:
                    current_status = {
                        "id": job.id,
                        "status": job.status,
                        "progress": getattr(job.scan, 'progress', 0) if job.scan else 0,
                        "error_message": job.error_message
                    }
                    
                    # Отправляем событие только если статус изменился
                    if job.id not in last_statuses or last_statuses[job.id] != current_status:
                        event_data = json.dumps(current_status)
                        yield f"data: {event_data}\n\n"
                        last_statuses[job.id] = current_status
                
                # Удаляем из last_statuses завершенные задачи
                active_ids = {job.id for job in jobs}
                for job_id in list(last_statuses.keys()):
                    if job_id not in active_ids:
                        del last_statuses[job_id]
                    
        except Exception as e:
            logger.error(f"Error in SSE generator: {e}")
        
        await asyncio.sleep(2)  # Проверка каждые 2 секунды


@router.get("/events")
async def scan_events(request: Request):
    """Endpoint для Server-Sent Events (SSE) - потоковая передача статуса сканирований."""
    
    async def generate():
        async for event in scan_event_generator():
            # Проверяем, не отключился ли клиент
            if await request.is_disconnected():
                break
            yield event
    
    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # Отключаем буферизацию nginx
        }
    )


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
    from models.scan import Scan, ScanJob
    from services.scan_queue_manager import scan_queue_manager
    from datetime import datetime, timezone
    import logging
    
    logger = logging.getLogger(__name__)
    logger.info("=" * 60)
    logger.info("=== ПОЛУЧЕН ЗАПРОС НА NMAP СКАНИРОВАНИЕ ===")
    logger.info("=" * 60)
    logger.info(f"Входящие данные запроса:")
    logger.info(f"  - target: {request.target}")
    logger.info(f"  - ports: {request.ports}")
    logger.info(f"  - scripts: {request.scripts}")
    logger.info(f"  - custom_args: {request.custom_args}")
    logger.info(f"  - known_ports_only: {request.known_ports_only}")
    logger.info(f"  - group_ids: {request.group_ids}")
    logger.info(f"Raw request data: {request.dict()}")
    
    target = request.target or ""
    
    try:
        # Создаём запись сканирования
        logger.info(f"\n[Шаг 1/4] Создание записи сканирования в БД...")
        new_scan = Scan(
            name=f"Nmap scan: {target[:50] if target else 'known ports'}",
            target=target or "known_ports_only",
            scan_type="nmap",
            status="queued",
            progress=0,
            created_at=datetime.now(timezone.utc)
        )
        
        db.add(new_scan)
        await db.commit()
        await db.refresh(new_scan)
        logger.info(f"✓ Запись сканирования создана: ID={new_scan.id}, name={new_scan.name}, target={new_scan.target}")
        
        # Создаём задачу сканирования
        logger.info(f"\n[Шаг 2/4] Создание задачи сканирования (ScanJob)...")
        new_job = ScanJob(
            scan_id=new_scan.id,
            job_type="nmap",
            status="queued",
            created_at=datetime.now(timezone.utc)
        )
        
        db.add(new_job)
        await db.commit()
        await db.refresh(new_job)
        logger.info(f"✓ Задача сканирования создана: ID={new_job.id}, scan_id={new_job.scan_id}, job_type={new_job.job_type}")
        
        # Добавляем задачу в очередь выполнения
        logger.info(f"\n[Шаг 3/4] Подготовка параметров для очереди...")
        targets_list = [target] if target else []
        parameters = {
            "ports": request.ports,
            "scripts": request.scripts,
            "custom_args": request.custom_args,
            "known_ports_only": request.known_ports_only,
            "group_ids": request.group_ids
        }
        logger.info(f"  - targets_list: {targets_list}")
        logger.info(f"  - parameters: {parameters}")
        
        logger.info(f"\n[Шаг 4/4] Добавление задачи в ScanQueueManager...")
        await scan_queue_manager.add_scan(
            db=db,
            scan_job_id=new_job.id,
            scan_type="nmap",
            targets=targets_list,
            parameters=parameters
        )
        logger.info(f"✓ Задача {new_job.id} успешно добавлена в очередь ScanQueueManager")
        
        logger.info("\n" + "=" * 60)
        logger.info("=== СКАНИРОВАНИЕ УСПЕШНО ЗАПУЩЕНО ===")
        logger.info(f"Job ID: {new_job.id}")
        logger.info(f"Scan ID: {new_scan.id}")
        logger.info("=" * 60)
        
        return {"message": f"Nmap сканирование запущено для {target}", "status": "queued", "job_id": new_job.id, "scan_id": new_scan.id}
    
    except Exception as e:
        logger.error(f"\n❌ КРИТИЧЕСКАЯ ОШИБКА при запуске сканирования: {e}", exc_info=True)
        logger.error(f"Тип ошибки: {type(e).__name__}")
        import traceback
        logger.error(f"Traceback:\n{traceback.format_exc()}")
        
        # Попытка откатить состояние в БД если возможно
        try:
            if 'new_job' in locals():
                new_job.status = "failed"
                new_job.error_message = str(e)
                await db.commit()
                logger.info(f"Статус задачи {new_job.id} обновлен на 'failed'")
        except Exception as rollback_error:
            logger.error(f"Ошибка при обновлении статуса задачи: {rollback_error}")
        
        raise HTTPException(status_code=500, detail=f"Ошибка запуска сканирования: {str(e)}")


@router.post("/rustscan")
async def run_rustscan(
    request: RustscanRequest,
    background_tasks: BackgroundTasks = None,
    db: AsyncSession = Depends(get_db)
):
    """Запустить сканирование Rustscan."""
    from models.scan import Scan, ScanJob
    from services.scan_queue_manager import scan_queue_manager
    from datetime import datetime, timezone
    import logging
    
    logger = logging.getLogger(__name__)
    logger.info("=" * 60)
    logger.info("=== ПОЛУЧЕН ЗАПРОС НА RUSTSCAN ===")
    logger.info("=" * 60)
    logger.info(f"Входящие данные запроса:")
    logger.info(f"  - target: {request.target}")
    logger.info(f"  - ports: {request.ports}")
    logger.info(f"  - custom_args: {request.custom_args}")
    logger.info(f"  - run_nmap_after: {request.run_nmap_after}")
    logger.info(f"  - nmap_args: {request.nmap_args}")
    logger.info(f"Raw request data: {request.dict()}")
    
    try:
        # Создаём запись сканирования
        logger.info(f"\n[Шаг 1/4] Создание записи сканирования в БД...")
        new_scan = Scan(
            name=f"Rustscan: {request.target[:50]}",
            target=request.target,
            scan_type="rustscan",
            status="queued",
            progress=0,
            created_at=datetime.now(timezone.utc)
        )
        
        db.add(new_scan)
        await db.commit()
        await db.refresh(new_scan)
        logger.info(f"✓ Запись сканирования создана: ID={new_scan.id}, target={new_scan.target}")
        
        # Создаём задачу сканирования
        logger.info(f"\n[Шаг 2/4] Создание задачи сканирования (ScanJob)...")
        new_job = ScanJob(
            scan_id=new_scan.id,
            job_type="rustscan",
            status="queued",
            created_at=datetime.now(timezone.utc)
        )
        
        db.add(new_job)
        await db.commit()
        await db.refresh(new_job)
        logger.info(f"✓ Задача сканирования создана: ID={new_job.id}, scan_id={new_job.scan_id}")
        
        # Добавляем задачу в очередь выполнения
        logger.info(f"\n[Шаг 3/4] Подготовка параметров для очереди...")
        targets_list = [request.target] if request.target else []
        parameters = {
            "ports": request.ports,
            "custom_args": request.custom_args,
            "run_nmap_after": request.run_nmap_after,
            "nmap_args": request.nmap_args
        }
        logger.info(f"  - targets_list: {targets_list}")
        logger.info(f"  - parameters: {parameters}")
        
        logger.info(f"\n[Шаг 4/4] Добавление задачи в ScanQueueManager...")
        await scan_queue_manager.add_scan(
            db=db,
            scan_job_id=new_job.id,
            scan_type="rustscan",
            targets=targets_list,
            parameters=parameters
        )
        logger.info(f"✓ Задача {new_job.id} успешно добавлена в очередь ScanQueueManager")
        
        logger.info("\n" + "=" * 60)
        logger.info("=== RUSTSCAN УСПЕШНО ЗАПУЩЕН ===")
        logger.info(f"Job ID: {new_job.id}")
        logger.info(f"Scan ID: {new_scan.id}")
        logger.info("=" * 60)
        
        return {"message": f"Rustscan запущен для {request.target}", "status": "queued", "job_id": new_job.id, "scan_id": new_scan.id}
    
    except Exception as e:
        logger.error(f"\n❌ КРИТИЧЕСКАЯ ОШИБКА при запуске Rustscan: {e}", exc_info=True)
        logger.error(f"Тип ошибки: {type(e).__name__}")
        import traceback
        logger.error(f"Traceback:\n{traceback.format_exc()}")
        
        try:
            if 'new_job' in locals():
                new_job.status = "failed"
                new_job.error_message = str(e)
                await db.commit()
                logger.info(f"Статус задачи {new_job.id} обновлен на 'failed'")
        except Exception as rollback_error:
            logger.error(f"Ошибка при обновлении статуса задачи: {rollback_error}")
        
        raise HTTPException(status_code=500, detail=f"Ошибка запуска сканирования: {str(e)}")


@router.post("/dig")
async def run_dig_scan(
    request: DigScanRequest,
    background_tasks: BackgroundTasks = None,
    db: AsyncSession = Depends(get_db)
):
    """Запустить DNS сканирование (dig)."""
    from models.scan import Scan, ScanJob
    from services.scan_queue_manager import scan_queue_manager
    from datetime import datetime, timezone
    import logging
    
    logger = logging.getLogger(__name__)
    logger.info("=" * 60)
    logger.info("=== ПОЛУЧЕН ЗАПРОС НА DIG СКАНИРОВАНИЕ ===")
    logger.info("=" * 60)
    logger.info(f"Входящие данные запроса:")
    logger.info(f"  - targets_text: {request.targets_text}")
    logger.info(f"  - dns_server: {request.dns_server}")
    logger.info(f"  - cli_args: {request.cli_args}")
    logger.info(f"  - record_types: {request.record_types}")
    logger.info(f"Raw request data: {request.dict()}")
    
    try:
        # Создаём запись сканирования
        logger.info(f"\n[Шаг 1/4] Создание записи сканирования в БД...")
        new_scan = Scan(
            name=f"Dig scan: {request.targets_text[:50]}",
            target=request.targets_text,
            scan_type="dig",
            status="queued",
            progress=0,
            created_at=datetime.now(timezone.utc)
        )
        
        db.add(new_scan)
        await db.commit()
        await db.refresh(new_scan)
        logger.info(f"✓ Запись сканирования создана: ID={new_scan.id}, target={new_scan.target}")
        
        # Создаём задачу сканирования
        logger.info(f"\n[Шаг 2/4] Создание задачи сканирования (ScanJob)...")
        new_job = ScanJob(
            scan_id=new_scan.id,
            job_type="dig",
            status="queued",
            created_at=datetime.now(timezone.utc)
        )
        
        db.add(new_job)
        await db.commit()
        await db.refresh(new_job)
        logger.info(f"✓ Задача сканирования создана: ID={new_job.id}, scan_id={new_job.scan_id}")
        
        # Добавляем задачу в очередь выполнения
        logger.info(f"\n[Шаг 3/4] Подготовка параметров для очереди...")
        targets_list = [t.strip() for t in request.targets_text.split(',') if t.strip()]
        parameters = {
            "dns_server": request.dns_server,
            "cli_args": request.cli_args,
            "record_types": request.record_types
        }
        logger.info(f"  - targets_list: {targets_list}")
        logger.info(f"  - parameters: {parameters}")
        
        logger.info(f"\n[Шаг 4/4] Добавление задачи в ScanQueueManager...")
        await scan_queue_manager.add_scan(
            db=db,
            scan_job_id=new_job.id,
            scan_type="dig",
            targets=targets_list,
            parameters=parameters
        )
        logger.info(f"✓ Задача {new_job.id} успешно добавлена в очередь ScanQueueManager")
        
        logger.info("\n" + "=" * 60)
        logger.info("=== DIG СКАНИРОВАНИЕ УСПЕШНО ЗАПУЩЕНО ===")
        logger.info(f"Job ID: {new_job.id}")
        logger.info(f"Scan ID: {new_scan.id}")
        logger.info("=" * 60)
        
        return {"message": f"Dig сканирование запущено для {request.targets_text}", "status": "queued", "job_id": new_job.id, "scan_id": new_scan.id}
    
    except Exception as e:
        logger.error(f"\n❌ КРИТИЧЕСКАЯ ОШИБКА при запуске Dig сканирования: {e}", exc_info=True)
        logger.error(f"Тип ошибки: {type(e).__name__}")
        import traceback
        logger.error(f"Traceback:\n{traceback.format_exc()}")
        
        try:
            if 'new_job' in locals():
                new_job.status = "failed"
                new_job.error_message = str(e)
                await db.commit()
                logger.info(f"Статус задачи {new_job.id} обновлен на 'failed'")
        except Exception as rollback_error:
            logger.error(f"Ошибка при обновлении статуса задачи: {rollback_error}")
        
        raise HTTPException(status_code=500, detail=f"Ошибка запуска сканирования: {str(e)}")


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
    from models.scan import ScanJob
    from sqlalchemy import select
    
    # Проверяем существование задачи
    query = select(ScanJob).where(ScanJob.id == job_id)
    result = await db.execute(query)
    job = result.scalar_one_or_none()
    
    if not job:
        raise HTTPException(status_code=404, detail=f"Задача сканирования с ID {job_id} не найдена")
    
    # Удаляем задачу
    await db.delete(job)
    await db.commit()
    
    return {"message": f"Задача {job_id} отменена", "job_id": job_id}


# ==========================================
# Маршруты задач сканирований (scan-job)
# ==========================================

@router.get("/scan-job")
async def get_scan_jobs(db: AsyncSession = Depends(get_db)):
    """Получить все задачи сканирований."""
    from models.scan import ScanJob
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
    from models.scan import ScanJob
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload
    
    # Получаем задачу с связанным сканированием
    query = select(ScanJob).where(ScanJob.id == job_id).options(selectinload(ScanJob.scan))
    result = await db.execute(query)
    job = result.scalar_one_or_none()
    
    if not job:
        raise HTTPException(status_code=404, detail=f"Задача сканирования с ID {job_id} не найдена")
    
    return {
        "id": job.id,
        "scan_id": job.scan_id,
        "job_type": job.job_type,
        "status": job.status,
        "error_message": job.error_message,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "scan": {
            "id": job.scan.id if job.scan else None,
            "name": job.scan.name if job.scan else None,
            "target": job.scan.target if job.scan else None,
            "scan_type": job.scan.scan_type if job.scan else None,
            "status": job.scan.status if job.scan else None,
            "progress": job.scan.progress if job.scan else 0,
        } if job.scan else None
    }


@router.delete("/scan-job/{job_id}")
async def delete_scan_job(job_id: int, db: AsyncSession = Depends(get_db)):
    """Удалить задачу сканирования."""
    from models.scan import ScanJob
    from sqlalchemy import select
    
    # Проверяем существование задачи
    query = select(ScanJob).where(ScanJob.id == job_id)
    result = await db.execute(query)
    job = result.scalar_one_or_none()
    
    if not job:
        raise HTTPException(status_code=404, detail=f"Задача сканирования с ID {job_id} не найдена")
    
    # Удаляем задачу
    await db.delete(job)
    await db.commit()
    
    return {"message": f"Задача {job_id} удалена", "job_id": job_id}


@router.post("/scan-job/{job_id}/stop")
async def stop_scan_job(job_id: int, db: AsyncSession = Depends(get_db)):
    """Остановить задачу сканирования."""
    from models.scan import ScanJob, Scan
    from sqlalchemy import select
    from services.scan_queue_manager import scan_queue_manager
    
    # Получаем задачу
    query = select(ScanJob).where(ScanJob.id == job_id).options(selectinload(ScanJob.scan))
    result = await db.execute(query)
    job = result.scalar_one_or_none()
    
    if not job:
        raise HTTPException(status_code=404, detail=f"Задача сканирования с ID {job_id} не найдена")
    
    # Можно остановить только running или pending задачи
    if job.status not in ['running', 'pending', 'queued']:
        raise HTTPException(status_code=400, detail=f"Невозможно остановить задачу со статусом {job.status}")
    
    # Обновляем статус задачи
    job.status = 'stopped'
    if job.scan:
        job.scan.status = 'stopped'
    
    # Удаляем из очереди менеджера если там есть
    await scan_queue_manager.remove_from_queue(job_id)
    
    await db.commit()
    
    return {"message": f"Задача {job_id} остановлена", "job_id": job_id}


@router.post("/scan-job/{job_id}/retry")
async def retry_scan_job(job_id: int, db: AsyncSession = Depends(get_db)):
    """Повторить задачу сканирования."""
    from models.scan import ScanJob, Scan
    from sqlalchemy import select
    from services.scan_queue_manager import scan_queue_manager
    
    # Получаем задачу с связанным сканированием
    query = select(ScanJob).where(ScanJob.id == job_id).options(selectinload(ScanJob.scan))
    result = await db.execute(query)
    job = result.scalar_one_or_none()
    
    if not job:
        raise HTTPException(status_code=404, detail=f"Задача сканирования с ID {job_id} не найдена")
    
    # Можно перезапустить только завершенные или неудачные задачи
    if job.status not in ['completed', 'failed', 'stopped', 'cancelled']:
        raise HTTPException(status_code=400, detail=f"Невозможно перезапустить задачу со статусом {job.status}")
    
    # Обновляем статусы
    job.status = 'queued'
    job.error_message = None
    job.completed_at = None
    if job.scan:
        job.scan.status = 'queued'
        job.scan.progress = 0
    
    await db.commit()
    
    # Добавляем задачу обратно в очередь
    targets = [job.scan.target] if job.scan and job.scan.target else []
    parameters = {}
    
    await scan_queue_manager.add_scan(
        db=db,
        scan_job_id=job.id,
        scan_type=job.job_type,
        targets=targets,
        parameters=parameters
    )
    
    return {"message": f"Задача {job_id} перезапущена", "job_id": job_id}


@router.get("/scan-job/{job_id}/download/{format}")
async def download_scan_job_result(job_id: int, format: str, db: AsyncSession = Depends(get_db)):
    """Скачать результаты задачи сканирования в указанном формате."""
    from sqlalchemy import select
    from models.scan import ScanJob, ScanResult
    from sqlalchemy.orm import selectinload
    import json
    
    # Получаем задачу сканирования
    job_query = select(ScanJob).where(ScanJob.id == job_id).options(selectinload(ScanJob.scan))
    job_result = await db.execute(job_query)
    job = job_result.scalar_one_or_none()
    
    if not job:
        raise HTTPException(status_code=404, detail="Задача сканирования не найдена")
    
    # Получаем результаты сканирования для этой задачи
    results_query = select(ScanResult).where(ScanResult.scan_job_id == job_id)
    results_result = await db.execute(results_query)
    results = results_result.scalars().all()
    
    if not results:
        # Пробуем получить результаты по scan_id если нет по job_id
        results_query = select(ScanResult).where(ScanResult.scan_id == job.scan_id)
        results_result = await db.execute(results_query)
        results = results_result.scalars().all()
    
    if not results:
        raise HTTPException(status_code=404, detail="Результаты сканирования не найдены")
    
    # Форматируем результат в зависимости от запрошенного формата
    if format == "raw":
        # Сырой вывод всех результатов
        raw_output = ""
        for result in results:
            if result.raw_output:
                raw_output += f"# Host: {result.ip_address}\n"
                raw_output += result.raw_output
                raw_output += "\n\n"
        
        if not raw_output:
            # Если нет raw_output, возвращаем JSON в виде текста
            raw_output = json.dumps([
                {
                    "ip_address": r.ip_address,
                    "ports": r.ports,
                    "services": r.services,
                    "hostname": r.hostname,
                    "os_info": r.os_info
                }
                for r in results
            ], indent=2)
        
        return StreamingResponse(
            iter([raw_output.encode('utf-8')]),
            media_type="text/plain",
            headers={
                "Content-Disposition": f'attachment; filename="scan_{job_id}_raw.txt"'
            }
        )
    
    elif format == "json":
        # JSON формат
        data = [
            {
                "ip_address": r.ip_address,
                "ports": r.ports,
                "services": r.services,
                "hostname": r.hostname,
                "os_info": r.os_info,
                "status": r.status
            }
            for r in results
        ]
        return StreamingResponse(
            iter([json.dumps(data, indent=2).encode('utf-8')]),
            media_type="application/json",
            headers={
                "Content-Disposition": f'attachment; filename="scan_{job_id}.json"'
            }
        )
    
    else:
        raise HTTPException(status_code=400, detail=f"Неподдерживаемый формат: {format}. Доступные: raw, json")


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
