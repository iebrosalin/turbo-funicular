# scanner/dig/dig.py
"""
Модуль сканирования DNS с использованием утилиты dig.
Поддерживает все основные типы записей (A, AAAA, MX, TXT, NS, CNAME, SOA, PTR, SRV).
Сохраняет результаты в базу данных и обновляет информацию об активах.
"""
import subprocess
import re
import os
from datetime import datetime
from extensions import db
from models import Asset, ScanJob, ActivityLog
from utils import MOSCOW_TZ

class DigScanner:
    """Класс для выполнения DNS-сканирования через dig"""
    
    def __init__(self, app):
        self.app = app
        self.process = None
        self.current_job_id = None
    
    def scan(self, job_id, targets_text, dns_server='77.88.8.8', cli_args='', record_types=None):
        """
        Запуск сканирования DNS для списка целей.
        
        :param job_id: ID задания в БД
        :param targets_text: Список целей (каждая с новой строки)
        :param dns_server: DNS сервер для запросов (например, 8.8.8.8)
        :param cli_args: Дополнительные аргументы dig (+short, +trace и т.д.)
        :param record_types: Список типов записей для проверки (если None, то все основные)
        """
        self.current_job_id = job_id
        
        if record_types is None or len(record_types) == 0:
            record_types = ['A', 'AAAA', 'MX', 'TXT', 'NS', 'CNAME', 'SOA', 'PTR', 'SRV']
        
        targets = [t.strip() for t in targets_text.splitlines() if t.strip()]
        
        if not targets:
            self._update_job_status('failed', error="Список целей пуст")
            return

        # Подготовка директории для вывода
        output_dir = os.path.join(os.getcwd(), 'scanner_output', str(job_id))
        os.makedirs(output_dir, exist_ok=True)
        output_file = os.path.join(output_dir, 'dig_output.txt')
        
        try:
            self._update_job_status('running', started=True)
            
            all_results = {}
            full_output_lines = []
            
            for i, target in enumerate(targets):
                if self._should_stop():
                    self._update_job_status('stopped')
                    return
                
                progress = int(((i + 1) / len(targets)) * 100)
                self._update_job_progress(progress)
                
                print(f"🔍 Сканирование DNS для: {target}")
                
                target_results = {'records': {}, 'names': set()}
                
                for rtype in record_types:
                    if self._should_stop():
                        break
                    
                    cmd = ['dig']
                    
                    # Добавляем сервер, если указан и не является частью target
                    if dns_server and not dns_server.startswith('@'):
                        cmd.append(f'@{dns_server}')
                    elif dns_server.startswith('@'):
                        cmd.append(dns_server)
                        
                    cmd.extend([target, rtype])
                    
                    # Добавляем пользовательские аргументы
                    if cli_args:
                        # Безопасное разбиение аргументов
                        extra_args = cli_args.split()
                        # Фильтрация опасных аргументов (например, выполнение команд)
                        safe_args = [arg for arg in extra_args if not arg.startswith('+cmd=')]
                        cmd.extend(safe_args)
                    
                    try:
                        result = subprocess.run(
                            cmd,
                            capture_output=True,
                            text=True,
                            timeout=30
                        )
                        
                        output = result.stdout
                        full_output_lines.append(f"; --- {target} {rtype} ---")
                        full_output_lines.append(output)
                        
                        parsed = self._parse_dig_output(output, rtype, target)
                        if parsed:
                            if rtype not in target_results['records']:
                                target_results['records'][rtype] = []
                            target_results['records'][rtype].extend(parsed)
                            
                            # Сбор имен для поля dns_names
                            if rtype in ['A', 'AAAA', 'CNAME']:
                                for rec in parsed:
                                    if 'name' in rec:
                                        target_results['names'].add(rec['name'])
                                    if 'data' in rec and rtype == 'CNAME':
                                        target_results['names'].add(rec['data'])
                                    
                    except subprocess.TimeoutExpired:
                        full_output_lines.append(f"; Timeout for {target} {rtype}")
                    except Exception as e:
                        full_output_lines.append(f"; Error for {target} {rtype}: {str(e)}")
                
                all_results[target] = target_results
            
            # Сохранение полного вывода в файл
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write('\n'.join(full_output_lines))
            
            # Обновление БД
            self._save_results(job_id, all_results, output_file)
            
            self._update_job_status('completed', output_file=output_file)
            print(f"✅ Сканирование DNS завершено. Задание #{job_id}")
            
        except Exception as e:
            print(f"❌ Ошибка сканирования DNS: {e}")
            self._update_job_status('failed', error=str(e))
    
    def _parse_dig_output(self, output, record_type, query_target):
        """Парсинг вывода dig для конкретного типа записи"""
        records = []
        lines = output.split('\n')
        
        in_answer = False
        current_ttl = None
        
        for line in lines:
            line = line.strip()
            
            # Пропуск комментариев и заголовков
            if line.startswith(';') or not line:
                if 'ANSWER SECTION' in line:
                    in_answer = True
                elif 'QUERY SECTION' in line or 'AUTHORITY SECTION' in line:
                    in_answer = False
                continue
            
            if not in_answer:
                continue
            
            # Разбор строки записи
            # Формат: NAME TTL CLASS TYPE DATA
            parts = line.split()
            if len(parts) >= 5:
                try:
                    name = parts[0]
                    ttl = int(parts[1])
                    # rclass = parts[2] # Обычно IN
                    rtype = parts[3]
                    data = ' '.join(parts[4:])
                    
                    if rtype == record_type:
                        record = {
                            'name': name.rstrip('.'),
                            'ttl': ttl,
                            'type': rtype,
                            'data': data.rstrip('.')
                        }
                        records.append(record)
                except (ValueError, IndexError):
                    continue
        
        return records

    def _save_results(self, job_id, results, output_file_path):
        """Сохранение результатов в БД и обновление активов"""
        with self.app.app_context():
            job = ScanJob.query.get(job_id)
            if not job:
                return

            for target, data in results.items():
                # Нормализация target (удаление @server если есть)
                clean_target = target.split('@')[0] if '@' in target else target
                
                # Поиск или создание актива
                asset = Asset.query.filter_by(ip_address=clean_target).first()
                if not asset:
                    # Пробуем найти по имени, если target - домен
                    # Или создаем новый, если это домен и мы хотим его хранить как актив
                    # Для простоты создаем запись с доменом в hostname, IP пока unknown
                    # В реальном сценарии лучше сначала резолвить домен в IP
                    import socket
                    try:
                        ip_addr = socket.gethostbyname(clean_target)
                        asset = Asset.query.filter_by(ip_address=ip_addr).first()
                        if not asset:
                            asset = Asset(ip_address=ip_addr, hostname=clean_target)
                            db.session.add(asset)
                            db.session.flush() # Чтобы получить ID
                    except socket.gaierror:
                        # Не удалось резолвить, создаем фиктивный или пропускаем
                        # Для DNS сканирования доменов без IP создадим запись с IP='domain'
                        # Но модель требует IP. Создадим с заглушкой или пропустим.
                        # Лучше создать актив с IP из A записи, если она есть в результатах
                        a_records = data['records'].get('A', [])
                        if a_records:
                            ip_addr = a_records[0]['data']
                            asset = Asset.query.filter_by(ip_address=ip_addr).first()
                            if not asset:
                                asset = Asset(ip_address=ip_addr, hostname=clean_target)
                                db.session.add(asset)
                                db.session.flush()
                        else:
                            continue # Пропускаем, если нет IP

                # Обновление DNS данных
                if data['records']:
                    # Объединяем с существующими записями
                    existing_records = asset.dns_records or {}
                    for rtype, recs in data['records'].items():
                        if rtype not in existing_records:
                            existing_records[rtype] = []
                        # Добавляем только уникальные
                        current_data = [r.get('data') for r in existing_records[rtype]]
                        for rec in recs:
                            if rec.get('data') not in current_data:
                                existing_records[rtype].append(rec)
                    
                    asset.dns_records = existing_records
                    asset.last_dns_scan = datetime.now(MOSCOW_TZ)
                    
                    # Обновление dns_names и fqdn
                    all_names = set(asset.dns_names or [])
                    all_names.update(data['names'])
                    if clean_target not in all_names:
                        all_names.add(clean_target)
                    asset.dns_names = list(all_names)
                    
                    # Установка FQDN если есть CNAME или просто первое имя
                    cname_records = existing_records.get('CNAME', [])
                    if cname_records:
                        asset.fqdn = cname_records[0].get('data', asset.fqdn)
                    elif not asset.fqdn and all_names:
                        asset.fqdn = next(iter(all_names))

                # Логирование
                log = ActivityLog(
                    asset_id=asset.id,
                    event_type='dns_scan_completed',
                    description=f"Выполнено DNS сканирование. Найдено записей: {sum(len(v) for v in data['records'].values())}",
                    details={'types': list(data['records'].keys())}
                )
                db.session.add(log)

            db.session.commit()

    def stop(self):
        """Остановка текущего процесса сканирования"""
        if self.process:
            self.process.terminate()
            self.process = None
        if self.current_job_id:
            self._update_job_status('stopped')

    def pause(self):
        """Пауза сканирования (заглушка, dig не поддерживает нативную паузу)"""
        pass

    def resume(self):
        """Возобновление сканирования"""
        pass

    def _should_stop(self):
        """Проверка флага остановки в БД"""
        if not self.current_job_id:
            return False
        with self.app.app_context():
            job = ScanJob.query.get(self.current_job_id)
            return job and job.status == 'stopping'

    def _update_job_status(self, status, started=False, output_file=None, error=None):
        """Безопасное обновление статуса задания из потока"""
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

    def _update_job_progress(self, progress):
        """Обновление прогресса выполнения"""
        with self.app.app_context():
            job = ScanJob.query.get(self.current_job_id)
            if job:
                job.progress = progress
                db.session.commit()
