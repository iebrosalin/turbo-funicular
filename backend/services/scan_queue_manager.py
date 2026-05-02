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
    """Менеджер очереди сканирований с поддержкой эксклюзивных и параллельных задач."""
    
    def __init__(self):
        self._tasks: Dict[int, asyncio.Task] = {}
        self._progress: Dict[int, Dict[str, Any]] = {}
        self._running = False
        # Очередь для эксклюзивных задач (Nmap) - выполняется только одна
        self._exclusive_queue: asyncio.Queue = asyncio.Queue()
        # Очередь для параллельных задач (Rustscan, Dig) - могут выполняться несколько
        self._parallel_queue: asyncio.Queue = asyncio.Queue()
        # Максимальное количество параллельных задач
        self._max_parallel_tasks = 3
        # Счетчик текущих параллельных задач
        self._parallel_task_count = 0
        self._queue_processor_task: Optional[asyncio.Task] = None
    
    async def start(self):
        """Запустить менеджер очереди."""
        self._running = True
        # Запускаем обработчик очередей
        self._queue_processor_task = asyncio.create_task(self._process_queues())
        logger.info("ScanQueueManager запущен")
    
    async def stop(self):
        """Остановить менеджер очереди и все задачи."""
        self._running = False
        
        # Отменяем задачу обработки очередей
        if self._queue_processor_task and not self._queue_processor_task.done():
            self._queue_processor_task.cancel()
            try:
                await self._queue_processor_task
            except asyncio.CancelledError:
                pass
        
        # Отменяем все активные задачи
        for task_id, task in list(self._tasks.items()):
            if not task.done():
                task.cancel()
                logger.info(f"Задача сканирования {task_id} отменена")
        
        await asyncio.gather(*self._tasks.values(), return_exceptions=True)
        self._tasks.clear()
        logger.info("ScanQueueManager остановлен")
    
    async def _process_queues(self):
        """Обработчик очередей - распределяет задачи на выполнение."""
        while self._running:
            try:
                # Проверяем эксклюзивную очередь (приоритет)
                if not self._exclusive_queue.empty():
                    # Если нет активных эксклюзивных задач, берем из очереди
                    has_exclusive_running = any(
                        job_id in self._tasks and not self._tasks[job_id].done()
                        for job_id, _ in list(self._exclusive_queue._queue)
                    )
                    
                    if not has_exclusive_running:
                        try:
                            job_id, scan_type, targets, parameters, db_session = self._exclusive_queue.get_nowait()
                            logger.info(f"Запуск эксклюзивной задачи {job_id} ({scan_type})")
                            task = asyncio.create_task(
                                self._run_scan(job_id, scan_type, targets, parameters, db_session)
                            )
                            self._tasks[job_id] = task
                        except asyncio.QueueEmpty:
                            pass
                
                # Проверяем параллельную очередь
                if not self._parallel_queue.empty() and self._parallel_task_count < self._max_parallel_tasks:
                    try:
                        job_id, scan_type, targets, parameters, db_session = self._parallel_queue.get_nowait()
                        logger.info(f"Запуск параллельной задачи {job_id} ({scan_type}), текущих: {self._parallel_task_count}/{self._max_parallel_tasks}")
                        task = asyncio.create_task(
                            self._run_scan(job_id, scan_type, targets, parameters, db_session)
                        )
                        self._tasks[job_id] = task
                        self._parallel_task_count += 1
                    except asyncio.QueueEmpty:
                        pass
                
                # Небольшая задержка чтобы не блокировать цикл событий
                await asyncio.sleep(0.5)
                
            except Exception as e:
                logger.error(f"Ошибка в обработчике очередей: {e}", exc_info=True)
                await asyncio.sleep(1)
    
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
        
        # Определяем тип очереди на основе типа сканирования
        # Nmap - эксклюзивная задача (только одна одновременно)
        # Rustscan и Dig - параллельные задачи (могут выполняться несколько)
        is_exclusive = scan_type == 'nmap'
        
        # Создаем новую сессию БД для фоновой задачи
        from backend.db.session import async_session_maker
        async with async_session_maker() as new_db:
            scan_params = (scan_job_id, scan_type, targets, parameters, None)
            
            if is_exclusive:
                logger.info(f"Задача {scan_job_id} добавлена в эксклюзивную очередь")
                await self._exclusive_queue.put(scan_params)
            else:
                logger.info(f"Задача {scan_job_id} добавлена в параллельную очередь")
                await self._parallel_queue.put(scan_params)
        
        self._progress[scan_job_id] = {
            "total": len(targets),
            "current": 0,
            "started_at": datetime.utcnow(),
            "status": "queued"
        }
        
        return True
    
    async def _run_scan(
        self,
        scan_job_id: int,
        scan_type: str,
        targets: List[str],
        parameters: Dict[str, Any],
        db_session = None
    ):
        """Выполнить сканирование."""
        from backend.models.scan import ScanJob, ScanResult
        from backend.utils import get_moscow_time
        
        logger.info(f"[DEBUG] _run_scan вызван для job_id={scan_job_id}, scan_type={scan_type}, targets={targets}")
        
        # Создаём новую сессию БД для фоновой задачи
        async with async_session_maker() as db:
            try:
                logger.info(f"[DEBUG] Попытка получения задачи {scan_job_id} из БД")
                job = await db.get(ScanJob, scan_job_id)
                if not job:
                    logger.error(f"[DEBUG] Задача {scan_job_id} не найдена в БД")
                    logger.error(f"[DEBUG] Все задачи в БД: {[j.id async for j in (await db.execute(select(ScanJob))).scalars().all()]}")
                    return
                
                logger.info(f"[DEBUG] Задача {scan_job_id} найдена, текущий статус: {job.status}")
                job.status = "running"
                job.started_at = datetime.utcnow()
                await db.commit()
                logger.info(f"[DEBUG] Статус задачи {scan_job_id} обновлён на 'running'")
                
                logger.info(f"Начало сканирования {scan_job_id}: {scan_type} для {len(targets)} целей")
                
                # Выбираем сканер
                scanner = None
                if scan_type == 'nmap':
                    scanner = NmapScanner()
                    logger.info(f"[DEBUG] Создан NmapScanner")
                elif scan_type == 'rustscan':
                    scanner = RustscanScanner()
                    logger.info(f"[DEBUG] Создан RustscanScanner")
                elif scan_type == 'dig':
                    scanner = DigScanner()
                    logger.info(f"[DEBUG] Создан DigScanner")
                
                if not scanner:
                    raise ValueError(f"Неизвестный тип сканирования: {scan_type}")
                
                # Выполняем сканирование для каждой цели
                for idx, target in enumerate(targets):
                    if not self._running or scan_job_id not in self._tasks:
                        logger.warning(f"[DEBUG] Сканирование {scan_job_id} прервано на цели {idx+1}/{len(targets)}")
                        break
                    
                    # Обновление прогресса
                    self._progress[scan_job_id]["current"] = idx + 1
                    logger.info(f"[DEBUG] Обработка цели {idx+1}/{len(targets)}: {target}")
                    
                    try:
                        # Вызов реального сканера
                        if scan_type == 'nmap':
                            logger.info(f"[DEBUG] Запуск NmapScanner.scan для {target}")
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
                            logger.info(f"[DEBUG] Запуск RustscanScanner.scan для {target}")
                            # Передаем аргументы для nmap если нужно запустить после rustscan
                            result_data = await scanner.scan(
                                db=db,
                                job_id=scan_job_id,
                                target=target,
                                ports=parameters.get('ports', ''),
                                custom_args=parameters.get('custom_args', ''),
                                run_nmap_after=parameters.get('run_nmap_after', False),
                                nmap_args=parameters.get('nmap_args', ''),
                                group_ids=parameters.get('group_ids')
                            )
                        elif scan_type == 'dig':
                            logger.info(f"[DEBUG] Запуск DigScanner.scan для {target}, record_type={parameters.get('record_types', 'A')}")
                            result_data = await scanner.scan(
                                db=db,
                                job_id=scan_job_id,
                                target=target,
                                record_type=parameters.get('record_types', 'A'),
                                custom_args=parameters.get('cli_args', ''),
                                group_ids=parameters.get('group_ids')
                            )
                            logger.info(f"[DEBUG] DigScanner.scan вернул: {result_data}")
                        else:
                            raise ValueError(f"Неизвестный тип сканирования: {scan_type}")
                        
                        # Сохранение результата
                        if result_data and result_data.get('status') == 'completed' and 'result' in result_data:
                            logger.info(f"[DEBUG] Результат сканирования получен: status=completed, result={result_data['result']}")
                            parsed = result_data['result']
                            
                            # Получаем scan_id из job
                            current_scan_id = job.scan_id
                            if not current_scan_id:
                                # Если scan_id не загружен, получаем его отдельно
                                from sqlalchemy import select
                                stmt = select(ScanJob.scan_id).where(ScanJob.id == scan_job_id)
                                res = await db.execute(stmt)
                                current_scan_id = res.scalar_one_or_none()
                            
                            result = ScanResult(
                                scan_id=current_scan_id,
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
                
                logger.info(f"[DEBUG] Сканирование {scan_job_id} завершено успешно")
                logger.info(f"Сканирование {scan_job_id} завершено")
                
                # Уменьшаем счетчик параллельных задач если это была параллельная задача
                if scan_type in ['rustscan', 'dig']:
                    self._parallel_task_count = max(0, self._parallel_task_count - 1)
                    logger.info(f"Параллельная задача {scan_job_id} завершена, осталось: {self._parallel_task_count}/{self._max_parallel_tasks}")
                
            except asyncio.CancelledError:
                logger.info(f"[DEBUG] Сканирование {scan_job_id} отменено пользователем")
                logger.info(f"Сканирование {scan_job_id} отменено")
                job = await db.get(ScanJob, scan_job_id)
                if job:
                    job.status = "cancelled"
                    job.error_message = "Сканирование было отменено пользователем"
                    await db.commit()
                raise
            except Exception as e:
                import traceback
                error_traceback = traceback.format_exc()
                logger.error(f"[DEBUG] Ошибка при выполнении сканирования {scan_job_id}: {e}")
                logger.error(f"[DEBUG] Трассировка: {error_traceback}")
                logger.error(f"Ошибка при выполнении сканирования {scan_job_id}: {e}", exc_info=True)
                job = await db.get(ScanJob, scan_job_id)
                if job:
                    job.status = "failed"
                    job.error_message = str(e)
                    job.completed_at = datetime.utcnow()
                    await db.commit()
            finally:
                logger.info(f"[DEBUG] Очистка задач из _tasks и _progress для {scan_job_id}")
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
        """Удалить задачу из очереди (отмена задачи)."""
        from sqlalchemy import select
        from backend.models.scan import ScanJob
        
        try:
            # Находим задачу в БД
            query = select(ScanJob).where(ScanJob.id == scan_job_id)
            result = await self._db.execute(query)
            job = result.scalar_one_or_none()
            
            if not job:
                logger.warning(f"Задача с ID {scan_job_id} не найдена в БД")
                return False
            
            # Если задача выполняется - пытаемся остановить процесс
            if job.status == 'running' and scan_job_id in self._tasks:
                task_info = self._tasks[scan_job_id]
                if task_info['task']:
                    task_info['task'].cancel()
                    try:
                        await task_info['task']
                    except asyncio.CancelledError:
                        pass
                    logger.info(f"Задача {scan_job_id} была отменена")
            
            # Обновляем статус в БД
            job.status = 'cancelled'
            job.completed_at = datetime.now(timezone.utc)
            await self._db.commit()
            
            logger.info(f"Задача {scan_job_id} успешно удалена из очереди")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка при удалении задачи {scan_job_id}: {e}")
            return False
        finally:
            self._tasks.pop(scan_job_id, None)


# Глобальные экземпляры
scan_queue_manager = ScanQueueManager()
utility_scan_queue_manager = UtilityScanQueueManager()
