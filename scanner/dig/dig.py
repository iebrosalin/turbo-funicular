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
from models import Asset, ScanJob, ActivityLog, AssetGroup
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

        # Проверка на короткий формат (+short) - просто список записей без заголовков
        is_short_format = all(
            not line.strip().startswith(';') and
            not line.strip().startswith(';;') and
            'SECTION' not in line
            for line in lines if line.strip()
        )

        if is_short_format:
            # Короткий формат: каждая строка - это значение записи
            for line in lines:
                line = line.strip()
                if line and not line.startswith(';'):
                    # Для MX записей формат: priority server
                    if record_type == 'MX':
                        parts = line.split()
                        if len(parts) >= 2:
                            records.append({
                                'name': query_target.rstrip('.'),
                                'ttl': 0,
                                'type': record_type,
                                'data': parts[1].rstrip('.')
                            })
                    else:
                        records.append({
                            'name': query_target.rstrip('.'),
                            'ttl': 0,
                            'type': record_type,
                            'data': line.rstrip('.')
                        })
            return records

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

            # Получаем группу "Без группы"
            no_group = AssetGroup.query.filter_by(name="Без группы").first()
            if not no_group:
                # Если группы не существует, создаем её
                no_group = AssetGroup(name="Без группы", group_type="manual")
                db.session.add(no_group)
                db.session.flush()



            # Список для хранения всех пар (IP, данные) для последующей группировки
            ip_data_list = []

            for target, data in results.items():
                # Нормализация target (удаление @server если есть)
                clean_target = target.split('@')[0] if '@' in target else target

                # Сбор ВСЕХ IP-адресов из A, AAAA и MX записей
                all_ips = set()

                # Получаем записи
                a_records = data['records'].get('A', [])
                aaaa_records = data['records'].get('AAAA', [])
                mx_records = data['records'].get('MX', [])

                # 1. Если есть A записи - добавляем ВСЕ IP из A записей
                if a_records:
                    for rec in a_records:
                        all_ips.add(rec['data'])
                # 2. Если нет A, но есть AAAA - добавляем ВСЕ IP из AAAA записей
                elif aaaa_records:
                    for rec in aaaa_records:
                        all_ips.add(rec['data'])
                # 3. Если нет ни A, ни AAAA, но есть MX - резолвим имена серверов в IP
                elif mx_records:
                    for mx_rec in mx_records:
                        mx_data = mx_rec.get('data', '')
                        mx_parts = mx_data.split()
                        if len(mx_parts) >= 2:
                            mx_server = mx_parts[1]
                        else:
                            mx_server = mx_data

                        # Резолвинг MX сервера в IP
                        try:
                            import socket
                            ip_addr = socket.gethostbyname(mx_server.rstrip('.'))
                            all_ips.add(ip_addr)
                        except socket.gaierror:
                            continue

                # Если нет ни одного IP, пропускаем target
                if not all_ips:
                    continue

                # Для каждого IP создаём запись для последующей обработки
                for ip_addr in all_ips:
                    ip_data_list.append({
                        'ip': ip_addr,
                        'target': clean_target,
                        'names': data['names'],
                        'records': data['records']
                    })

            # Группировка данных по IP-адресам для создания/обновления активов
            ip_to_names = {}
            ip_to_records = {}
            ip_to_targets = {}

            for item in ip_data_list:
                ip_addr = item['ip']

                if ip_addr not in ip_to_names:
                    ip_to_names[ip_addr] = set()
                    ip_to_records[ip_addr] = {}
                    ip_to_targets[ip_addr] = set()

                # Добавляем имена доменов
                ip_to_names[ip_addr].update(item['names'])
                ip_to_names[ip_addr].add(item['target'])

                # Добавляем target в список целей для этого IP
                ip_to_targets[ip_addr].add(item['target'])

                # Объединяем DNS записи
                for rtype, recs in item['records'].items():
                    if rtype not in ip_to_records[ip_addr]:
                        ip_to_records[ip_addr][rtype] = []
                    current_data = [r.get('data') for r in ip_to_records[ip_addr][rtype]]
                    for rec in recs:
                        if rec.get('data') not in current_data:
                            ip_to_records[ip_addr][rtype].append(rec)

            # Обработка всех сгруппированных данных по IP
            for ip_addr, names in ip_to_names.items():
                # Поиск или создание актива по IP
                asset = Asset.query.filter_by(ip_address=ip_addr).first()
                if not asset:
                    # Создаем новый актив
                    # Используем первое имя как hostname
                    # Актив создается в группе "Без группы"
                    hostname = next(iter(names))
                    asset = Asset(ip_address=ip_addr, hostname=hostname)
                    asset.groups = [no_group]
                    db.session.add(asset)
                    db.session.flush()
                else:
                    # Актив уже существует - оставляем его только в группе "Без группы"
                    # Удаляем все другие группы и оставляем только "Без группы"
                    asset.groups = [no_group]

                # Обновление DNS данных (объединяем с существующими)
                existing_records = asset.dns_records or {}
                for rtype, recs in ip_to_records[ip_addr].items():
                    if rtype not in existing_records:
                        existing_records[rtype] = []
                    current_data = [r.get('data') for r in existing_records[rtype]]
                    for rec in recs:
                        if rec.get('data') not in current_data:
                            existing_records[rtype].append(rec)

                asset.dns_records = existing_records
                asset.last_dns_scan = datetime.now(MOSCOW_TZ)

                # Обновление dns_names - добавляем все имена для этого IP
                all_names = set(asset.dns_names or [])
                all_names.update(names)
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
                    description=f"Выполнено DNS сканирование. Доменных имен: {len(names)}, записей: {sum(len(v) for v in ip_to_records[ip_addr].values())}",
                    details={'types': list(ip_to_records[ip_addr].keys()), 'domains': list(names)}
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
