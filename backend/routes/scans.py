from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks, UploadFile, File, Body, Request, Form
from fastapi.responses import StreamingResponse, HTMLResponse
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
    group_ids: Optional[List[int]] = None


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


@router.post("/import-nmap-xml")
async def import_xml_scan(
    file: UploadFile = File(...),
    group_id: Optional[int] = Form(None),
    db: AsyncSession = Depends(get_db)
):
    """Импортировать XML результаты сканирования (nmap)."""
    import tempfile
    import os
    from backend.utils.nmap_xml_importer import NmapXmlImporter
    
    try:
        # Сохраняем файл во временное хранилище
        with tempfile.NamedTemporaryFile(delete=False, suffix='.xml') as tmp_file:
            content = await file.read()
            tmp_file.write(content)
            tmp_path = tmp_file.name
        
        try:
            # Импортируем данные из XML
            importer = NmapXmlImporter(db)
            count = await importer.import_file(tmp_path, group_id=group_id)
            
            return {"message": f"Импорт успешно завершен", "count": count, "filename": file.filename}
        finally:
            # Удаляем временный файл
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
                
    except Exception as e:
        logger.error(f"Ошибка импорта XML: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Ошибка импорта XML: {str(e)}")


@router.post("/nmap")
async def run_nmap_scan(
    request: NmapScanRequest,
    background_tasks: BackgroundTasks = None,
    db: AsyncSession = Depends(get_db)
):
    """Запустить сканирование Nmap."""
    from backend.models.scan import Scan, ScanJob
    from backend.services.scan_queue_manager import scan_queue_manager
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
    from backend.models.scan import Scan, ScanJob
    from backend.services.scan_queue_manager import scan_queue_manager
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
    target: str = Form(...),
    args: str = Form(...),
    scan_type: str = Form("dig"),
    save_assets: bool = Form(False),
    background_tasks: BackgroundTasks = None,
    db: AsyncSession = Depends(get_db)
):
    """Запустить DNS сканирование (dig)."""
    from backend.models.scan import Scan, ScanJob
    from backend.services.scan_queue_manager import scan_queue_manager
    from datetime import datetime, timezone
    import logging
    
    logger = logging.getLogger(__name__)
    logger.info("=" * 60)
    logger.info("=== ПОЛУЧЕН ЗАПРОС НА DIG СКАНИРОВАНИЕ ===")
    logger.info("=" * 60)
    logger.info(f"Входящие данные запроса:")
    logger.info(f"  - target: {target}")
    logger.info(f"  - args: {args}")
    logger.info(f"  - scan_type: {scan_type}")
    logger.info(f"  - save_assets: {save_assets}")
    
    # Парсим аргументы из строки args
    # Формат: "ANY @8.8.8.8 domain.com" или "ANY domain.com"
    parts = args.split()
    record_types = ""
    dns_server = None
    cli_args = ""
    
    for part in parts:
        if part.startswith('@'):
            dns_server = part[1:]  # Убираем '@'
        elif part.upper() in ['A', 'AAAA', 'MX', 'NS', 'TXT', 'CNAME', 'SOA', 'PTR', 'ANY', 'SRV']:
            record_types = part.upper()
        else:
            # Это может быть домен или дополнительные аргументы
            if '.' in part and not part.startswith('-'):
                # Это домен
                pass
            elif part.startswith('-'):
                cli_args += f" {part}"
    
    try:
        # Создаём запись сканирования
        logger.info(f"\n[Шаг 1/4] Создание записи сканирования в БД...")
        new_scan = Scan(
            name=f"Dig scan: {target[:50]}",
            target=target,
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
        targets_list = [t.strip() for t in target.split(',') if t.strip()]
        parameters = {
            "dns_server": dns_server,
            "cli_args": cli_args.strip(),
            "record_types": record_types,
            "group_ids": None
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
        
        return {"message": f"Dig сканирование запущено для {target}", "status": "queued", "job_id": new_job.id, "scan_id": new_scan.id, "id": new_job.id}
    
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


# ==========================================
# Маршруты очереди сканирований (scan-queue)
# ==========================================

@router.get("/scan-queue")
async def get_scan_queue(db: AsyncSession = Depends(get_db)):
    """Получить очередь сканирований."""
    from backend.models.scan import ScanJob
    from sqlalchemy.orm import selectinload
    from sqlalchemy import select
    
    # Получаем все активные задачи
    query = select(ScanJob).options(
        selectinload(ScanJob.scan)
    ).where(
        ScanJob.status.in_(['pending', 'running', 'queued'])
    ).order_by(ScanJob.created_at.desc())
    
    result = await db.execute(query)
    jobs = result.scalars().all()
    
    queue_items = []
    for job in jobs:
        queue_items.append({
            "job_id": job.id,
            "scan_id": job.scan_id,
            "job_type": job.job_type,
            "status": job.status,
            "target": job.scan.target if job.scan else "Unknown",
            "created_at": job.created_at.isoformat() if job.created_at else None,
            "error_message": job.error_message
        })
    
    return queue_items


@router.get("/scan-queue/{job_id}")
async def get_scan_queue_job(job_id: int, db: AsyncSession = Depends(get_db)):
    """Получить задачу из очереди сканирований."""
    from backend.models.scan import ScanJob
    from sqlalchemy.orm import selectinload
    from sqlalchemy import select
    
    query = select(ScanJob).options(
        selectinload(ScanJob.scan)
    ).where(ScanJob.id == job_id)
    
    result = await db.execute(query)
    job = result.scalar_one_or_none()
    
    if not job:
        raise HTTPException(status_code=404, detail=f"Задача сканирования с ID {job_id} не найдена")
    
    return {
        "job_id": job.id,
        "scan_id": job.scan_id,
        "job_type": job.job_type,
        "status": job.status,
        "target": job.scan.target if job.scan else "Unknown",
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
        "error_message": job.error_message
    }


@router.delete("/scan-queue/{job_id}")
async def cancel_scan_queue_job(job_id: int, db: AsyncSession = Depends(get_db)):
    """Отменить задачу в очереди сканирований."""
    from backend.models.scan import ScanJob
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
    from backend.models.scan import ScanJob
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
    from backend.models.scan import ScanJob
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
    from backend.models.scan import ScanJob, Scan
    from sqlalchemy import select
    from backend.services.scan_queue_manager import scan_queue_manager
    
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
    """Повторить задачу сканирования (создать новую задачу с теми же параметрами)."""
    from backend.models.scan import ScanJob, Scan
    from sqlalchemy import select
    from backend.services.scan_queue_manager import scan_queue_manager
    import datetime
    
    # Получаем задачу с связанным сканированием
    query = select(ScanJob).where(ScanJob.id == job_id).options(selectinload(ScanJob.scan))
    result = await db.execute(query)
    job = result.scalar_one_or_none()
    
    if not job:
        raise HTTPException(status_code=404, detail=f"Задача сканирования с ID {job_id} не найдена")
    
    # Можно перезапустить только завершенные или неудачные задачи
    if job.status not in ['completed', 'failed', 'stopped', 'cancelled']:
        raise HTTPException(status_code=400, detail=f"Невозможно перезапустить задачу со статусом {job.status}")
    
    # Получаем параметры из старого сканирования
    old_scan = job.scan
    if not old_scan:
        raise HTTPException(status_code=400, detail="Сканирование не найдено для этой задачи")
    
    # Создаем новое сканирование с теми же параметрами
    new_scan = Scan(
        name=old_scan.name,
        target=old_scan.target,
        scan_type=old_scan.scan_type,
        status='queued',
        progress=0,
        group_id=old_scan.group_id,
    )
    db.add(new_scan)
    await db.flush()  # Чтобы получить ID нового сканирования
    
    # Создаем новую задачу для нового сканирования
    new_job = ScanJob(
        scan_id=new_scan.id,
        job_type=job.job_type,
        status='queued',
        error_message=None,
        created_at=datetime.datetime.utcnow(),
        started_at=None,
        completed_at=None,
        worker_id=None,
        parameters=job.parameters,
    )
    db.add(new_job)
    await db.commit()
    
    # Добавляем новую задачу в очередь
    targets = [new_scan.target] if new_scan.target else []
    
    await scan_queue_manager.add_scan(
        db=db,
        scan_job_id=new_job.id,
        scan_type=new_job.job_type,
        targets=targets,
        parameters=new_scan.parameters or {}
    )
    
    return {"message": f"Создана новая задача {new_job.id} для сканирования {new_scan.id}", "job_id": new_job.id, "scan_id": new_scan.id}


@router.get("/scan-job/{job_id}/download/{format}")
async def download_scan_job_result(job_id: int, format: str, db: AsyncSession = Depends(get_db)):
    """Скачать результаты задачи сканирования в указанном формате."""
    from sqlalchemy import select
    from backend.models.scan import ScanJob, ScanResult
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
        raise HTTPException(status_code=400, detail=f"Неподдерживаемый формат: {format}. Доступные: raw, json, csv")


@router.get("/scan/{scan_id}/download/{format}")
async def download_scan_result(scan_id: int, format: str, db: AsyncSession = Depends(get_db)):
    """Скачать результаты сканирования по scan_id в указанном формате."""
    from sqlalchemy import select
    from backend.models.scan import Scan, ScanResult
    from sqlalchemy.orm import selectinload
    
    # Получаем сканирование
    scan_query = select(Scan).where(Scan.id == scan_id).options(selectinload(Scan.jobs))
    scan_result = await db.execute(scan_query)
    scan = scan_result.scalar_one_or_none()
    
    if not scan:
        raise HTTPException(status_code=404, detail="Сканирование не найдено")
    
    # Получаем все результаты для этого сканирования
    results_query = select(ScanResult).where(ScanResult.scan_id == scan_id)
    results_result = await db.execute(results_query)
    results = results_result.scalars().all()
    
    if not results:
        raise HTTPException(status_code=404, detail="Результаты сканирования не найдены")
    
    # Форматируем результат в зависимости от запрошенного формата
    if format == "csv":
        import csv
        import io
        
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Заголовок
        writer.writerow(['IP Address', 'Hostname', 'Port', 'Protocol', 'State', 'Service', 'OS Info'])
        
        for result in results:
            ports = result.ports or []
            if isinstance(ports, list):
                for port_info in ports:
                    if isinstance(port_info, dict):
                        writer.writerow([
                            result.ip_address,
                            result.hostname or '',
                            port_info.get('port', ''),
                            port_info.get('protocol', 'tcp'),
                            port_info.get('state', 'open'),
                            port_info.get('service', ''),
                            result.os_info or ''
                        ])
                    elif isinstance(port_info, (int, str)):
                        writer.writerow([
                            result.ip_address,
                            result.hostname or '',
                            port_info,
                            'tcp',
                            'open',
                            '',
                            result.os_info or ''
                        ])
            else:
                writer.writerow([
                    result.ip_address,
                    result.hostname or '',
                    '',
                    '',
                    '',
                    '',
                    result.os_info or ''
                ])
        
        return StreamingResponse(
            iter([output.getvalue().encode('utf-8')]),
            media_type="text/csv",
            headers={
                "Content-Disposition": f'attachment; filename="scan_{scan_id}.csv"'
            }
        )
    
    elif format == "json":
        import json
        data = [
            {
                "ip_address": r.ip_address,
                "hostname": r.hostname,
                "ports": r.ports,
                "services": r.services,
                "os_info": r.os_info,
                "status": r.status
            }
            for r in results
        ]
        return StreamingResponse(
            iter([json.dumps(data, indent=2).encode('utf-8')]),
            media_type="application/json",
            headers={
                "Content-Disposition": f'attachment; filename="scan_{scan_id}.json"'
            }
        )
    
    elif format == "raw":
        raw_output = ""
        for result in results:
            if result.raw_output:
                raw_output += f"# Host: {result.ip_address}\n"
                raw_output += result.raw_output
                raw_output += "\n\n"
        
        if not raw_output:
            import json
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
                "Content-Disposition": f'attachment; filename="scan_{scan_id}_raw.txt"'
            }
        )
    
    else:
        raise HTTPException(status_code=400, detail=f"Неподдерживаемый формат: {format}. Доступные: raw, json, csv")


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
    
    # Запуск сканирования в фоне через менеджер очередей
    # Фоновая задача запускается автоматически при добавлении в очередь
    
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

# -----------------------------------------------------------------------------
# Страница истории сканирований
# -----------------------------------------------------------------------------

@router.get("/history", response_class=HTMLResponse)
async def scan_history_page(request: Request):
    """Страница истории сканирований."""
    return templates.TemplateResponse("scan_history.html", {"request": request})
