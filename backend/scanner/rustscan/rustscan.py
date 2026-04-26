 # scanner/rustscan/rustscan.py
"""
Модуль сканирования портов с использованием утилиты Rustscan.
Поддерживает автоматический запуск Nmap на найденных открытых портах.
Результаты сохраняются в базу данных и обновляют информацию об активах.
"""
import subprocess
import re
import os
import time
from datetime import datetime
from backend.db.session import db
from backend.models.asset import Asset
from backend.models.scan import ScanJob
from backend.models.log import ActivityLog
from backend.models.service import ServiceInventory
from backend.utils import MOSCOW_TZ
from backend.services.scan_queue_manager import scan_queue_manager

class RustscanScanner:
    """Класс для выполнения сканирования через Rustscan"""
    
    def __init__(self, app):
        self.app = app
        self.process = None
        self.current_job_id = None
    
    def scan(self, job_id, target, ports='', custom_args='', run_nmap_after=False, nmap_args=''):
        """
        Запуск сканирования Rustscan.
        
        :param job_id: ID задания в БД
        :param target: Цель (IP или CIDR)
        :param ports: Диапазон портов (например, 1-65535)
        :param custom_args: Дополнительные аргументы rustscan
        :param run_nmap_after: Флаг запуска Nmap после завершения
        :param nmap_args: Аргументы для последующего Nmap (после --)
        """
        self.current_job_id = job_id
        
        # Подготовка директории для вывода
        output_dir = os.path.join(os.getcwd(), 'scanner_output', str(job_id))
        os.makedirs(output_dir, exist_ok=True)
        output_file = os.path.join(output_dir, 'rustscan_output.txt')
        
        try:
            self._update_job_status('running', started=True)
            
            # Формирование команды
            # Добавляем --ulimit и уменьшаем batch size для стабильной работы в контейнере
            cmd = ['rustscan', '-a', target, '--ulimit', '5000', '-b', '1000']
            
            if ports:
                cmd.extend(['-p', ports])
            
            # Обработка custom_args
            # Если пользователь передал аргументы для nmap через '--', разделяем их
            nmap_suffix = ''
            if custom_args:
                if '--' in custom_args:
                    parts = custom_args.split('--', 1)
                    rust_args = parts[0].strip()
                    nmap_suffix = parts[1].strip()
                    if rust_args:
                        cmd.extend(rust_args.split())
                else:
                    cmd.extend(custom_args.split())
            
            # Приоритет явных аргументов nmap из формы над теми, что в custom_args
            if nmap_args:
                nmap_suffix = nmap_args
            
            # Добавляем аргументы для grepable вывода, если нужно парсить
            # Rustscan по умолчанию выводит список портов в формате: IP -> [port1, port2]
            # Мы будем парсить stdout
            
            print(f"🚀 Запуск Rustscan: {' '.join(cmd)}")
            
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )
            
            full_output = []
            
            # Чтение вывода в реальном времени
            while True:
                if self._should_stop():
                    self.process.terminate()
                    self._update_job_status('stopped')
                    return
                
                line = self.process.stdout.readline()
                if not line and self.process.poll() is not None:
                    break
                
                if line:
                    line = line.strip()
                    full_output.append(line)
                    print(line) # Логирование в консоль сервера
            
            exit_code = self.process.wait()
            
            # Сохранение вывода
            output_text = '\n'.join(full_output)
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(output_text)
            
            if exit_code != 0 and not self._should_stop():
                raise Exception(f"Rustscan завершился с кодом {exit_code}")
            
            # Парсинг результатов
            found_ports_map = self._parse_rustscan_results(output_text)
            
            if not found_ports_map:
                self._update_job_status('completed', output_file=output_file)
                print(f"⚠️ Открытые порты не найдены для {target}")
                return

            # Обновление БД активами и портами
            self._save_results(job_id, found_ports_map)
            
            self._update_job_status('completed', output_file=output_file)
            print(f"✅ Rustscan завершен. Задание #{job_id}")
            
            # Автоматический запуск Nmap если требуется
            if run_nmap_after and found_ports_map:
                self._queue_nmap_after_rustscan(job_id, target, found_ports_map, nmap_suffix)
                
        except Exception as e:
            print(f"❌ Ошибка Rustscan: {e}")
            self._update_job_status('failed', error=str(e))
        finally:
            self.process = None

    def _parse_rustscan_results(self, output):
        """
        Парсинг вывода Rustscan.
        Ожидает формат: IP -> [port1, port2, ...]
        Возвращает dict: { 'ip': [port1, port2], ... }
        """
        results = {}
        # Регулярка для поиска строк вида "192.168.1.1 -> [80, 443, 8080]"
        pattern = r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\s*->\s*\[(.*?)\]'
        
        for match in re.finditer(pattern, output):
            ip = match.group(1)
            ports_str = match.group(2)
            ports = []
            for p in ports_str.split(','):
                p = p.strip()
                if p.isdigit():
                    ports.append(int(p))
            
            if ports:
                if ip not in results:
                    results[ip] = []
                results[ip].extend(ports)
        
        return results

    def _save_results(self, job_id, found_ports_map):
        """Сохранение результатов в БД и обновление активов"""
        with self.app.app_context():
            job = ScanJob.query.get(job_id)
            if not job:
                return

            for ip, ports in found_ports_map.items():
                # Поиск или создание актива
                asset = Asset.query.filter_by(ip_address=ip).first()
                if not asset:
                    asset = Asset(ip_address=ip)
                    db.session.add(asset)
                    db.session.flush()
                
                # Обновление портов
                # Сортируем и убираем дубликаты
                unique_ports = sorted(list(set(ports)))
                
                # Обновляем поле rustscan_ports
                asset.update_ports('rustscan', unique_ports)
                
                # Создаем заглушки сервисов (без деталей, так как rustscan только сканирует порты)
                # Детали будут добавлены при последующем запуске nmap
                existing_ports = {s.port for s in asset.services}
                new_services_count = 0
                
                for port in unique_ports:
                    if port not in existing_ports:
                        service = ServiceInventory(
                            asset_id=asset.id,
                            port=port,
                            protocol='tcp',
                            state='open',
                            service_name='unknown',
                            discovered_at=datetime.now(MOSCOW_TZ)
                        )
                        db.session.add(service)
                        new_services_count += 1
                
                # Логирование
                log = ActivityLog(
                    asset_id=asset.id,
                    event_type='ports_discovered',
                    description=f"Rustscan обнаружил {len(unique_ports)} открытых портов",
                    details={'ports': unique_ports, 'new_services': new_services_count}
                )
                db.session.add(log)
                
                # Обновляем связь с заданием (опционально, если нужно хранить прямую связь результата с активом в ScanResult)
                # В данной реализации мы обновляем напрямую Asset и ServiceInventory

            db.session.commit()

    def _queue_nmap_after_rustscan(self, original_job_id, target, found_ports_map, nmap_args_suffix):
        """Создание задачи Nmap в очередь на основе результатов Rustscan"""
        with self.app.app_context():
            # Формируем строку портов для всех найденных IP
            # Если целевой хост один, берем его порты. Если сеть - объединяем или создаем задачи на каждый IP?
            # Rustscan обычно возвращает список IP. Для простоты возьмем первый IP или объединим порты если IP один.
            # В контексте задачи "run_nmap_after", обычно предполагается сканирование того же таргета.
            # Если target был CIDR, found_ports_map содержит несколько IP.
            # Nmap может принять список IP и порты для каждого? Нет, -p общие для всех.
            # Стратегия: Если найден один IP, запускаем для него. Если много - создаем задачу на весь диапазон с объединенным списком портов (может быть долго) 
            # ИЛИ создаем отдельные задачи на каждый IP.
            # Выберем вариант: создание одной задачи с перечислением всех найденных IP и уникальным набором портов.
            
            all_ips = list(found_ports_map.keys())
            all_ports_set = set()
            for p_list in found_ports_map.values():
                all_ports_set.update(p_list)
            
            ports_str = ','.join(map(str, sorted(all_ports_set)))
            
            # Формируем цель: если IP один, то он. Если много, то через пробел или исходный CIDR если он был
            # Лучше использовать конкретные IP, чтобы не сканировать закрытые хосты снова
            nmap_target = ' '.join(all_ips)
            
            # Создаем новое задание
            new_job = ScanJob(
                scan_type='nmap',
                target=nmap_target,
                status='pending',
                created_at=datetime.now(MOSCOW_TZ),
                parameters={
                    'ports': ports_str,
                    'scripts': '',
                    'custom_args': nmap_args_suffix,
                    'known_ports_only': False,
                    'parent_job_id': original_job_id # Связь с родителем
                }
            )
            
            db.session.add(new_job)
            db.session.commit()
            
            # Добавляем в очередь
            scan_queue_manager.add_to_queue(
                job_id=new_job.id,
                scan_type='nmap',
                target=nmap_target,
                ports=ports_str,
                scripts='',
                custom_args=nmap_args_suffix,
                known_ports_only=False,
                group_ids=None
            )
            
            print(f"📋 Задача Nmap #{new_job.id} добавлена в очередь после Rustscan #{original_job_id}")

    def stop(self):
        """Остановка процесса"""
        if self.process:
            self.process.terminate()
            self.process = None
        if self.current_job_id:
            self._update_job_status('stopped')

    def pause(self):
        """Пауза (заглушка)"""
        pass

    def resume(self):
        """Возобновление (заглушка)"""
        pass

    def _should_stop(self):
        """Проверка флага остановки"""
        if not self.current_job_id:
            return False
        with self.app.app_context():
            job = ScanJob.query.get(self.current_job_id)
            return job and job.status == 'stopping'

    def _update_job_status(self, status, started=False, output_file=None, error=None):
        """Обновление статуса в БД"""
        with self.app.app_context():
            job = ScanJob.query.get(self.current_job_id)
            if job:
                job.status = status
                if started:
                    job.started_at = datetime.now(MOSCOW_TZ)
                if output_file:
                    job.output_file = output_file
                if error:
                    job.error_message = error
                if status in ['completed', 'failed', 'stopped']:
                    job.completed_at = datetime.now(MOSCOW_TZ)
                db.session.commit()