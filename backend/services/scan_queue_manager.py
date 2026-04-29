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

from backend.scanner import NmapScanner, RustscanScanner, DigScanner
from backend.db.session import async_session_maker

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
        from backend.models.scan import ScanJob
        
        logger.info(f"Добавление задачи сканирования {scan_job_id} ({scan_type})")
        
        # Обновляем статус задачи - она уже в статусе "queued" из routes
        job = await db.get(ScanJob, scan_job_id)
        if not job:
            raise ValueError(f"Задача сканирования {scan_job_id} не найдена")
        
        job.parameters = parameters
        await db.commit()
        
        # Создаём асинхронную задачу, передавая только необходимые данные
        task = asyncio.create_task(
            self._run_scan(scan_job_id, scan_type, targets, parameters)
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
        scan_job_id: int,
        scan_type: str,
        targets: List[str],
        parameters: Dict[str, Any]
    ):
        """Выполнить сканирование."""
        from backend.models.scan import ScanJob, ScanResult
        from utils import get_moscow_time
        
        # Создаём новую сессию БД для фоновой задачи
        async with async_session_maker() as db:
            try:
                job = await db.get(ScanJob, scan_job_id)
                if not job:
                    logger.error(f"Задача {scan_job_id} не найдена в БД")
                    return
                
                job.status = "running"
                job.started_at = datetime.utcnow()
                await db.commit()
                
                logger.info(f"Начало сканирования {scan_job_id}: {scan_type} для {len(targets)} целей")
                
                # Выбираем сканер
                scanner = None
                if scan_type == 'nmap':
                    scanner = NmapScanner()
                elif scan_type == 'rustscan':
                    scanner = RustscanScanner()
                elif scan_type == 'dig':
                    scanner = DigScanner()
                
                if not scanner:
                    raise ValueError(f"Неизвестный тип сканирования: {scan_type}")
                
                # Выполняем сканирование для каждой цели
                for idx, target in enumerate(targets):
                    if not self._running or scan_job_id not in self._tasks:
                        logger.warning(f"Сканирование {scan_job_id} прервано")
                        break
                    
                    # Обновление прогресса
                    self._progress[scan_job_id]["current"] = idx + 1
                    
                    try:
                        # Вызов реального сканера
                        if scan_type == 'nmap':
                            result_data = await scanner.scan(
                                db=db,
                                job_id=scan_job_id,
                                target=target,
                                ports=parameters.get('ports', ''),
                                scripts=parameters.get('scripts', ''),
                                custom_args=parameters.get('custom_args', ''),
                                known_ports_only=parameters.get('known_ports_only', False),
                                group_ids=parameters.get('group_ids')
                            )
                        elif scan_type == 'rustscan':
                            result_data = await scanner.scan(
                                db=db,
                                job_id=scan_job_id,
                                target=target,
                                ports=parameters.get('ports', ''),
                                custom_args=parameters.get('custom_args', ''),
                                group_ids=parameters.get('group_ids')
                            )
                        elif scan_type == 'dig':
                            result_data = await scanner.scan(
                                db=db,
                                job_id=scan_job_id,
                                target=target,
                                record_type=parameters.get('record_types', 'A'),
                                custom_args=parameters.get('cli_args', '')
                            )
                        else:
                            raise ValueError(f"Неизвестный тип сканирования: {scan_type}")
                        
                        # Сохранение результата
                        if result_data and result_data.get('status') == 'completed' and 'result' in result_data:
                            parsed = result_data['result']
                            result = ScanResult(
                                scan_id=job.scan_id,
                                ip_address=target,
                                hostname=parsed.get('hostname', target),
                                ports=parsed.get('ports', []),
                                raw_output=result_data.get('raw_output', str(result_data)),
                                scanned_at=datetime.utcnow()
                            )
                            db.add(result)
                            await db.commit()
                            
                    except Exception as scan_error:
                        logger.error(f"Ошибка сканирования {target}: {scan_error}", exc_info=True)
                        # Продолжаем сканирование остальных целей
                    
                    # Небольшая задержка между сканированиями
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
                    job.status = "cancelled"
                    job.error_message = "Сканирование было отменено пользователем"
                    await db.commit()
                raise
            except Exception as e:
                logger.error(f"Ошибка при выполнении сканирования {scan_job_id}: {e}", exc_info=True)
                job = await db.get(ScanJob, scan_job_id)
                if job:
                    job.status = "failed"
                    job.error_message = str(e)
                    job.completed_at = datetime.utcnow()
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
    
    async def remove_from_queue(self, scan_job_id: int):
        """Удалить задачу из очереди (отменить если выполняется)."""
        return await self.stop_scan(scan_job_id)
    
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
    
    async def remove_from_queue(self, scan_job_id: int):
        """Удалить задачу из очереди (заглушка для совместимости)."""
        # Для утилит пока не реализовано управление задачами по ID
        logger.warning(f"remove_from_queue вызван для UtilityScanQueueManager с job_id={scan_job_id}")
        return False


# Глобальные экземпляры
scan_queue_manager = ScanQueueManager()
utility_scan_queue_manager = UtilityScanQueueManager()
