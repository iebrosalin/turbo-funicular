# utils/scan_queue.py
"""
Модуль управления очередью сканирований
Обеспечивает последовательный запуск задач nmap/rustscan в отдельной очереди
и остальных утилит сканирования в другой очереди
"""
import threading
import time
from datetime import datetime
from extensions import db
from models import ScanJob
from utils import MOSCOW_TZ

class ScanQueueManager:
    """Менеджер очереди сканирований для nmap/rustscan"""
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self.queue = []
        self.current_job_id = None
        self.is_running = False
        self.worker_thread = None
        self.stop_flag = False
        self.job_lock = threading.Lock()
        
    def start_worker(self, app):
        """Запуск рабочего потока обработки очереди"""
        if self.worker_thread and self.worker_thread.is_alive():
            return
        
        self.stop_flag = False
        self.worker_thread = threading.Thread(target=self._worker_loop, args=(app,), daemon=True)
        self.worker_thread.start()
        print("🔄 Менеджер очереди nmap/rustscan запущен")
    
    def stop_worker(self):
        """Остановка рабочего потока"""
        self.stop_flag = True
        if self.worker_thread:
            self.worker_thread.join(timeout=5)
    
    def add_to_queue(self, job_id, scan_type, target, ports='', scripts='', custom_args='', 
                     run_nmap_after=False, nmap_args='', known_ports_only=False, group_ids=None):
        """Добавление задачи в очередь"""
        with self.job_lock:
            task = {
                'job_id': job_id,
                'scan_type': scan_type,
                'target': target,
                'ports': ports,
                'scripts': scripts,
                'custom_args': custom_args,
                'run_nmap_after': run_nmap_after,
                'nmap_args': nmap_args,
                'known_ports_only': known_ports_only,
                'group_ids': group_ids,
                'created_at': datetime.now(MOSCOW_TZ)
            }
            self.queue.append(task)
            
            # Обновляем статус задачи
            try:
                job = ScanJob.query.get(job_id)
                if job:
                    job.status = 'pending'
                    db.session.commit()
            except Exception as e:
                print(f"❌ Ошибка обновления статуса задачи {job_id}: {e}")
                db.session.rollback()
            
            print(f"📋 Задача #{job_id} ({scan_type}) добавлена в очередь nmap/rustscan (позиция {len(self.queue)})")
            return job_id
    
    def remove_from_queue(self, job_id):
        """Удаление задачи из очереди"""
        with self.job_lock:
            for i, task in enumerate(self.queue):
                if task['job_id'] == job_id:
                    self.queue.pop(i)
                    print(f"🗑️ Задача #{job_id} удалена из очереди nmap/rustscan")
                    return True
        return False
    
    def get_queue_status(self):
        """Получение статуса очереди"""
        with self.job_lock:
            return {
                'queue_length': len(self.queue),
                'current_job_id': self.current_job_id,
                'is_running': self.is_running,
                'queued_jobs': [
                    {
                        'job_id': t['job_id'],
                        'scan_type': t['scan_type'],
                        'target': t['target'],
                        'position': i + 1
                    }
                    for i, t in enumerate(self.queue)
                ]
            }
    
    def _worker_loop(self, app):
        """Основной цикл обработки очереди"""
        while not self.stop_flag:
            task = None
            
            with self.job_lock:
                if not self.is_running and self.queue:
                    task = self.queue.pop(0)
                    self.current_job_id = task['job_id']
                    self.is_running = True
            
            if task:
                try:
                    with app.app_context():
                        self._execute_task(app, task)
                except Exception as e:
                    print(f"❌ Ошибка выполнения задачи {task['job_id']}: {e}")
                    import traceback
                    traceback.print_exc()
                    
                    with app.app_context():
                        try:
                            job = ScanJob.query.get(task['job_id'])
                            if job:
                                job.status = 'failed'
                                job.error_message = f"Ошибка очереди: {str(e)}"
                                job.completed_at = datetime.now(MOSCOW_TZ)
                                db.session.commit()
                        except Exception as db_err:
                            print(f"❌ Ошибка БД: {db_err}")
                            db.session.rollback()
                finally:
                    with self.job_lock:
                        self.current_job_id = None
                        self.is_running = False
            else:
                time.sleep(1)
    
    def _execute_task(self, app, task):
        """Выполнение задачи сканирования"""
        job_id = task['job_id']
        scan_type = task['scan_type']
        target = task['target']
        ports = task['ports']
        scripts = task['scripts']
        custom_args = task['custom_args']
        run_nmap_after = task.get('run_nmap_after', False)
        nmap_args = task.get('nmap_args', '')
        known_ports_only = task.get('known_ports_only', False)
        group_ids = task.get('group_ids', None)
        
        print(f"▶️ Запуск задачи #{job_id}: {scan_type} для {target}")
        
        # Обновляем статус перед запуском
        try:
            job = ScanJob.query.get(job_id)
            if job:
                job.status = 'running'
                job.started_at = datetime.now(MOSCOW_TZ)
                db.session.commit()
        except Exception as e:
            print(f"❌ Ошибка обновления статуса: {e}")
            db.session.rollback()
        
        # Импортируем классы сканеров
        from scanner.nmap.scanner import NmapScanner
        from scanner.rustscan.scanner import RustscanScanner
        
        if scan_type == 'rustscan':
            scanner = RustscanScanner(app)
            scanner.scan(job_id, target, ports, custom_args, run_nmap_after, nmap_args)
            
        elif scan_type == 'nmap':
            scanner = NmapScanner(app)
            scanner.scan(job_id, target, ports, scripts, custom_args, known_ports_only, group_ids)
        
        print(f"✅ Задача #{job_id} завершена")
    
    def _parse_rustscan_for_nmap(self, rustscan_output):
        """Парсинг вывода rustscan для получения списка портов"""
        ports = set()
        
        for line in rustscan_output.strip().split('\n'):
            line = line.strip()
            if '->' in line:
                parts = line.split('->')
                if len(parts) > 1:
                    ports_str = parts[1].strip().replace('[', '').replace(']', '')
                    for p in ports_str.split(','):
                        p = p.strip()
                        if p.isdigit():
                            ports.add(p)
        
        return ','.join(sorted(ports, key=lambda x: int(x))) if ports else ''


# Глобальный экземпляр менеджера очереди nmap/rustscan
scan_queue_manager = ScanQueueManager()


class UtilityScanQueueManager:
    """Менеджер очереди для остальных утилит сканирования (nslookup и др.)"""
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self.queue = []
        self.current_job_id = None
        self.is_running = False
        self.worker_thread = None
        self.stop_flag = False
        self.job_lock = threading.Lock()
        
    def start_worker(self, app):
        """Запуск рабочего потока обработки очереди"""
        if self.worker_thread and self.worker_thread.is_alive():
            return
        
        self.stop_flag = False
        self.worker_thread = threading.Thread(target=self._worker_loop, args=(app,), daemon=True)
        self.worker_thread.start()
        print("🔄 Менеджер очереди утилит запущен")
    
    def stop_worker(self):
        """Остановка рабочего потока"""
        self.stop_flag = True
        if self.worker_thread:
            self.worker_thread.join(timeout=5)
    
    def add_to_queue(self, job_id, scan_type, target, **kwargs):
        """Добавление задачи в очередь"""
        with self.job_lock:
            task = {
                'job_id': job_id,
                'scan_type': scan_type,
                'target': target,
                'kwargs': kwargs,
                'created_at': datetime.now(MOSCOW_TZ)
            }
            self.queue.append(task)
            
            # Обновляем статус задачи
            try:
                job = ScanJob.query.get(job_id)
                if job:
                    job.status = 'pending'
                    db.session.commit()
            except Exception as e:
                print(f"❌ Ошибка обновления статуса задачи {job_id}: {e}")
                db.session.rollback()
            
            print(f"📋 Задача #{job_id} ({scan_type}) добавлена в очередь утилит (позиция {len(self.queue)})")
            return job_id
    
    def remove_from_queue(self, job_id):
        """Удаление задачи из очереди"""
        with self.job_lock:
            for i, task in enumerate(self.queue):
                if task['job_id'] == job_id:
                    self.queue.pop(i)
                    print(f"🗑️ Задача #{job_id} удалена из очереди утилит")
                    return True
        return False
    
    def get_queue_status(self):
        """Получение статуса очереди"""
        with self.job_lock:
            return {
                'queue_length': len(self.queue),
                'current_job_id': self.current_job_id,
                'is_running': self.is_running,
                'queued_jobs': [
                    {
                        'job_id': t['job_id'],
                        'scan_type': t['scan_type'],
                        'target': t['target'],
                        'position': i + 1
                    }
                    for i, t in enumerate(self.queue)
                ]
            }
    
    def _worker_loop(self, app):
        """Основной цикл обработки очереди"""
        while not self.stop_flag:
            task = None
            
            with self.job_lock:
                if not self.is_running and self.queue:
                    task = self.queue.pop(0)
                    self.current_job_id = task['job_id']
                    self.is_running = True
            
            if task:
                try:
                    with app.app_context():
                        self._execute_task(app, task)
                except Exception as e:
                    print(f"❌ Ошибка выполнения задачи {task['job_id']}: {e}")
                    import traceback
                    traceback.print_exc()
                    
                    with app.app_context():
                        try:
                            job = ScanJob.query.get(task['job_id'])
                            if job:
                                job.status = 'failed'
                                job.error_message = f"Ошибка очереди: {str(e)}"
                                job.completed_at = datetime.now(MOSCOW_TZ)
                                db.session.commit()
                        except Exception as db_err:
                            print(f"❌ Ошибка БД: {db_err}")
                            db.session.rollback()
                finally:
                    with self.job_lock:
                        self.current_job_id = None
                        self.is_running = False
            else:
                time.sleep(1)
    
    def _execute_task(self, app, task):
        """Выполнение задачи сканирования"""
        job_id = task['job_id']
        scan_type = task['scan_type']
        target = task['target']
        kwargs = task.get('kwargs', {})
        
        print(f"▶️ Запуск задачи #{job_id}: {scan_type} для {target}")
        
        # Обновляем статус перед запуском
        try:
            job = ScanJob.query.get(job_id)
            if job:
                job.status = 'running'
                job.started_at = datetime.now(MOSCOW_TZ)
                db.session.commit()
        except Exception as e:
            print(f"❌ Ошибка обновления статуса: {e}")
            db.session.rollback()
        
        # Импортируем классы сканеров
        from scanner.dig.scanner import DigScanner
        
        if scan_type == 'nslookup':  # Оставляем для обратной совместимости, но используем dig
            targets_text = kwargs.get('targets_text', '')
            dns_server = kwargs.get('dns_server', '77.88.8.8')
            cli_args = kwargs.get('cli_args', '')
            record_types = kwargs.get('record_types', None)
            scanner = DigScanner(app)
            scanner.scan(job_id, targets_text, dns_server, cli_args, record_types)
        elif scan_type == 'dig':
            targets_text = kwargs.get('targets_text', '')
            dns_server = kwargs.get('dns_server', '77.88.8.8')
            cli_args = kwargs.get('cli_args', '')
            record_types = kwargs.get('record_types', None)
            scanner = DigScanner(app)
            scanner.scan(job_id, targets_text, dns_server, cli_args, record_types)
        
        print(f"✅ Задача #{job_id} завершена")


# Глобальный экземпляр менеджера очереди утилит
utility_scan_queue_manager = UtilityScanQueueManager()
