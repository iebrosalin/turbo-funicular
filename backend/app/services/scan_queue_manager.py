"""
Менеджер очередей сканирований.
Управление фоновыми задачами Nmap, Rustscan, Dig.
"""
import asyncio
import logging
from datetime import datetime
from typing import Dict, Optional, Any, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

logger = logging.getLogger(__name__)


class ScanQueueManager:
    """Менеджер очереди сканирований."""
    
    def __init__(self):
        self._tasks: Dict[int, asyncio.Task] = {}
        self._progress: Dict[int, Dict[str, Any]] = {}
        self._running = False
    
    async def start(self):
        """Запустить менеджер очереди."""
        self._running = True
        logger.info("ScanQueueManager запущен")
    
    async def stop(self):
        """Остановить менеджер очереди и все задачи."""
        self._running = False
        for task_id, task in list(self._tasks.items()):
            if not task.done():
                task.cancel()
                logger.info(f"Задача сканирования {task_id} отменена")
        await asyncio.gather(*self._tasks.values(), return_exceptions=True)
        self._tasks.clear()
        logger.info("ScanQueueManager остановлен")
    
    async def add_scan(
        self,
        db: AsyncSession,
        scan_job_id: int,
        scan_type: str,
        targets: List[str],
        parameters: Dict[str, Any]
    ):
        """Добавить задачу сканирования в очередь."""
        from app.models.scan import ScanJob
        
        logger.info(f"Добавление задачи сканирования {scan_job_id} ({scan_type})")
        
        # Обновляем статус задачи
        job = await db.get(ScanJob, scan_job_id)
        if not job:
            raise ValueError(f"Задача сканирования {scan_job_id} не найдена")
        
        job.status = "pending"
        job.parameters = parameters
        await db.commit()
        
        # Создаём асинхронную задачу
        task = asyncio.create_task(
            self._run_scan(db, scan_job_id, scan_type, targets, parameters)
        )
        self._tasks[scan_job_id] = task
        self._progress[scan_job_id] = {
            "total": len(targets),
            "current": 0,
            "started_at": datetime.utcnow()
        }
        
        return task
    
    async def _run_scan(
        self,
        db: AsyncSession,
        scan_job_id: int,
        scan_type: str,
        targets: List[str],
        parameters: Dict[str, Any]
    ):
        """Выполнить сканирование."""
        from app.models.scan import ScanJob, ScanResult
        from app.utils.helpers import get_moscow_time
        
        try:
            job = await db.get(ScanJob, scan_job_id)
            if not job:
                return
            
            job.status = "running"
            job.started_at = datetime.utcnow()
            await db.commit()
            
            logger.info(f"Начало сканирования {scan_job_id}: {scan_type} для {len(targets)} целей")
            
            # Имитация выполнения (в реальности здесь вызов scanner)
            for idx, target in enumerate(targets):
                if not self._running or scan_job_id not in self._tasks:
                    logger.warning(f"Сканирование {scan_job_id} прервано")
                    break
                
                # Обновление прогресса
                self._progress[scan_job_id]["current"] = idx + 1
                
                # Здесь должна быть логика вызова сканера
                # result = await run_scanner(scan_type, target, parameters)
                
                # Сохранение результата (заглушка)
                result = ScanResult(
                    scan_job_id=scan_job_id,
                    asset_ip=target,
                    hostname=None,
                    ports=[],
                    raw_output=f"Scan result for {target}",
                    scanned_at=get_moscow_time()
                )
                db.add(result)
                await db.commit()
                
                # Небольшая задержка для имитации работы
                await asyncio.sleep(0.1)
            
            # Завершение задачи
            job = await db.get(ScanJob, scan_job_id)
            if job:
                job.status = "completed"
                job.completed_at = datetime.utcnow()
                job.progress = 100.0
                await db.commit()
            
            logger.info(f"Сканирование {scan_job_id} завершено")
            
        except asyncio.CancelledError:
            logger.info(f"Сканирование {scan_job_id} отменено")
            job = await db.get(ScanJob, scan_job_id)
            if job:
                job.status = "failed"
                await db.commit()
            raise
        except Exception as e:
            logger.error(f"Ошибка при выполнении сканирования {scan_job_id}: {e}")
            job = await db.get(ScanJob, scan_job_id)
            if job:
                job.status = "failed"
                await db.commit()
        finally:
            self._tasks.pop(scan_job_id, None)
            self._progress.pop(scan_job_id, None)
    
    async def stop_scan(self, scan_job_id: int):
        """Остановить конкретное сканирование."""
        if scan_job_id in self._tasks:
            task = self._tasks[scan_job_id]
            if not task.done():
                task.cancel()
                logger.info(f"Задача сканирования {scan_job_id} отменена пользователем")
            return True
        return False
    
    def get_progress(self, scan_job_id: int) -> Optional[Dict[str, Any]]:
        """Получить прогресс сканирования."""
        return self._progress.get(scan_job_id)
    
    def is_running(self, scan_job_id: int) -> bool:
        """Проверить, выполняется ли сканирование."""
        return scan_job_id in self._tasks and not self._tasks[scan_job_id].done()


class UtilityScanQueueManager:
    """Менеджер очереди утилитных сканирований (Dig, простые проверки)."""
    
    def __init__(self):
        self._tasks: Dict[str, asyncio.Task] = {}
        self._running = False
    
    async def start(self):
        """Запустить менеджер."""
        self._running = True
        logger.info("UtilityScanQueueManager запущен")
    
    async def stop(self):
        """Остановить менеджера."""
        self._running = False
        for task_id, task in list(self._tasks.items()):
            if not task.done():
                task.cancel()
        await asyncio.gather(*self._tasks.values(), return_exceptions=True)
        self._tasks.clear()
        logger.info("UtilityScanQueueManager остановлен")
    
    async def run_utility_scan(
        self,
        db: AsyncSession,
        utility_type: str,
        target: str,
        parameters: Dict[str, Any]
    ) -> Any:
        """Выполнить утилитное сканирование."""
        task_id = f"{utility_type}_{target}_{datetime.utcnow().timestamp()}"
        
        async def _run():
            # Здесь логика выполнения утилиты
            logger.info(f"Выполнение утилиты {utility_type} для {target}")
            await asyncio.sleep(0.5)  # Имитация работы
            return {"status": "completed", "data": f"Result for {target}"}
        
        task = asyncio.create_task(_run())
        self._tasks[task_id] = task
        
        try:
            result = await task
            return result
        finally:
            self._tasks.pop(task_id, None)


# Глобальные экземпляры
scan_queue_manager = ScanQueueManager()
utility_scan_queue_manager = UtilityScanQueueManager()
