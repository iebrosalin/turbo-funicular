# scanner/nmap/nmap.py
"""
Модуль сканирования с использованием утилиты Nmap.
Поддерживает сканирование конкретных портов, скрипты NSE, определение ОС и версий сервисов.
Реализует логику сканирования только известных портов для выбранных групп активов.
Извлекает информацию о SSL-сертификатах.
"""
import subprocess
import os
import xml.etree.ElementTree as ET
import re
from datetime import datetime
from backend.db.session import db
from backend.models.asset import Asset
from backend.models.service import ServiceInventory
from backend.models.scan import ScanJob, ScanResult
from backend.models.log import ActivityLog
from backend.models.group import AssetGroup
from backend.utils import MOSCOW_TZ

class NmapScanner:
    """Класс для выполнения сканирования через Nmap"""
    
    def __init__(self, app):
        self.app = app
        self.process = None
        self.current_job_id = None
    
    def scan(self, job_id, target, ports='', scripts='', custom_args='', known_ports_only=False, group_ids=None):
        """
        Запуск сканирования Nmap.
        
        :param job_id: ID задания в БД
        :param target: Цель (IP, CIDR, hostname)
        :param ports: Диапазон портов
        :param scripts: Скрипты NSE
        :param custom_args: Дополнительные аргументы
        :param known_ports_only: Флаг сканирования только известных портов из групп
        :param group_ids: Список ID групп для режима known_ports_only
        """
        self.current_job_id = job_id
        
        # Подготовка директории
        output_dir = os.path.join(os.getcwd(), 'scanner_output', str(job_id))
        os.makedirs(output_dir, exist_ok=True)
        base_name = os.path.join(output_dir, 'nmap')
        
        try:
            self._update_job_status('running', started=True)
            
            final_targets = target
            final_ports = ports
            
            # Логика "Только известные порты"
            if known_ports_only and group_ids:
                print(f"🔍 Режим известных портов для групп: {group_ids}")
                targets_map = self._get_targets_with_known_ports(group_ids)
                
                if not targets_map:
                    raise Exception("Не найдено активов с открытыми портами в выбранных группах")
                
                # Формируем список целей: IP:port1,port2 IP2:port3...
                # Nmap поддерживает формат -p <ports> <host>, но для разных портов на разных хостах
                # лучше использовать формат host:port или запускать несколько раз.
                # Оптимально: сгруппировать по наборам портов или использовать формат "IP -p PORTS" в цикле?
                # Nmap CLI не поддерживает разные порты для разных хостов в одной команде легко.
                # Стратегия: Если набор портов одинаковый или похожий, можно объединить.
                # Для простоты реализации: создадим временный файл списка хостов с портами в формате, понятном nmap?
                # Нет, nmap не умеет "host1:80,443 host2:22".
                # Решение: Запускать сканирование последовательно для каждого уникального набора портов или для каждого хоста отдельно.
                # Чтобы не усложнять очередь, запустим один процесс nmap с объединением всех портов (-p all_unique) на всех хостах.
                # Это менее эффективно, но проще. Или лучше: разбить на подзадачи?
                # Выберем компромисс: передадим все IPs как цели, а в -p объединим ВСЕ уникальные порты из всех активов.
                # Это гарантирует проверку всех нужных портов, хотя и просканирует лишние на некоторых хостах.
                
                all_ips = set()
                all_known_ports = set()
                
                for ip, ports_list in targets_map.items():
                    all_ips.add(ip)
                    all_known_ports.update(ports_list)
                
                final_targets = ' '.join(list(all_ips))
                final_ports = ','.join(map(str, sorted(all_known_ports)))
                print(f"🎯 Цели: {len(all_ips)} хостов, Порты: {len(final_ports.split(','))} уникальных")
            
            # Формирование команды
            cmd = ['nmap']
            
            # Порты
            if final_ports:
                cmd.extend(['-p', final_ports])
            
            # Скрипты
            if scripts:
                cmd.extend(['--script', scripts])
            
            # Обязательные аргументы для детального вывода
            if '-sV' not in custom_args:
                cmd.append('-sV') # Version detection
            if '-O' not in custom_args:
                cmd.append('-O') # OS detection
            
            # Форматы вывода
            cmd.extend(['-oX', f'{base_name}.xml'])
            cmd.extend(['-oN', f'{base_name}.nmap'])
            # Grepable format (-oG) устарел, но иногда полезен. Добавим если нужно.
            
            # Кастомные аргументы
            if custom_args:
                # Валидация и безопасное добавление
                args_list = self._validate_custom_args(custom_args)
                cmd.extend(args_list)
            
            # Цели (в конце)
            cmd.extend(final_targets.split())
            
            print(f"🚀 Запуск Nmap: {' '.join(cmd)}")
            
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )
            
            full_output = []
            
            # Чтение вывода
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
                    # Прогресс можно парсить из строк вида "Completed ..."
                    if 'Completed' in line or 'Stats:' in line:
                        # Простая эвристика прогресса
                        pass 
                    print(line)
            
            exit_code = self.process.wait()
            
            if exit_code != 0 and not self._should_stop():
                # Nmap может вернуть 1 если хосты недоступны, это не всегда критично
                if exit_code > 1:
                    raise Exception(f"Nmap завершился с кодом {exit_code}")
            
            # Парсинг XML результатов
            xml_file = f'{base_name}.xml'
            if os.path.exists(xml_file):
                self._parse_nmap_results(job_id, xml_file, known_ports_only, targets_map if known_ports_only else None)
            else:
                raise Exception("Файл XML результатов не создан")
            
            # Сохранение текстового отчета как основного вывода
            txt_file = f'{base_name}.nmap'
            self._update_job_status('completed', output_file=txt_file)
            print(f"✅ Nmap завершен. Задание #{job_id}")
            
        except Exception as e:
            print(f"❌ Ошибка Nmap: {e}")
            self._update_job_status('failed', error=str(e))
        finally:
            self.process = None

    def _validate_custom_args(self, args_str):
        """Базовая валидация аргументов"""
        # Запрещаем опасные конструкции, если нужно
        # Разбиваем на список
        return args_str.split()

    def _get_targets_with_known_ports(self, group_ids):
        """
        Получение активов из групп и их открытых портов.
        Возвращает dict: { 'ip': [port1, port2], ... }
        """
        targets = {}
        with self.app.app_context():
            groups = AssetGroup.query.filter(AssetGroup.id.in_(group_ids)).all()
            asset_ids = set()
            for g in groups:
                for a in g.assets:
                    asset_ids.add(a.id)
            
            assets = Asset.query.filter(Asset.id.in_(asset_ids)).all()
            for asset in assets:
                if asset.open_ports:
                    targets[asset.ip_address] = asset.open_ports
        return targets

    def _parse_nmap_results(self, job_id, xml_file, known_ports_only=False, expected_targets=None):
        """Парсинг XML файла Nmap и обновление БД"""
        tree = ET.parse(xml_file)
        root = tree.getroot()
        
        with self.app.app_context():
            job = ScanJob.query.get(job_id)
            if not job:
                return
            
            hosts_count = 0
            for host in root.findall('host'):
                # Статус хоста
                status_elem = host.find('status')
                if status_elem is None or status_elem.get('state') != 'up':
                    continue
                
                # IP адрес
                addr_elem = host.find('address')
                if addr_elem is None:
                    continue
                ip = addr_elem.get('addr')
                
                # Hostname
                hostname = None
                hostnames = host.find('hostnames')
                if hostnames is not None:
                    h_elem = hostnames.find('hostname')
                    if h_elem is not None:
                        hostname = h_elem.get('name')
                
                # OS
                os_match = None
                os_accuracy = 0
                os_elem = host.find('os')
                if os_elem is not None:
                    os_match_elem = os_elem.find('osmatch')
                    if os_match_elem is not None:
                        os_match = os_match_elem.get('name')
                        try:
                            os_accuracy = int(os_match_elem.get('accuracy', 0))
                        except ValueError:
                            pass
                
                # Порты и сервисы
                ports_elem = host.find('ports')
                found_ports = []
                services_updated = 0
                
                if ports_elem is not None:
                    for port in ports_elem.findall('port'):
                        port_id = port.get('portid')
                        protocol = port.get('protocol')
                        state_elem = port.find('state')
                        state = state_elem.get('state') if state_elem is not None else 'unknown'
                        
                        if state == 'open':
                            port_num = int(port_id)
                            found_ports.append(port_num)
                            
                            # Детали сервиса
                            service_elem = port.find('service')
                            service_name = 'unknown'
                            product = ''
                            version = ''
                            extra_info = ''
                            script_output = ''
                            
                            # SSL данные
                            ssl_subject = None
                            ssl_issuer = None
                            ssl_not_before = None
                            ssl_not_after = None
                            
                            if service_elem is not None:
                                service_name = service_elem.get('name', 'unknown')
                                product = service_elem.get('product', '')
                                version = service_elem.get('version', '')
                                extra_info = service_elem.get('extrainfo', '')
                                
                                # Поиск скрипта ssl-cert
                                for script in service_elem.findall('script'):
                                    if script.get('id') == 'ssl-cert':
                                        output = script.get('output', '')
                                        script_output += output + "\n"
                                        
                                        # Парсинг таблицы из вывода скрипта (упрощенно)
                                        # Ищем Subject, Issuer, dates
                                        # В реальном проекте лучше парсить XML внутри script/table elem если есть
                                        # Здесь используем regex на output строку
                                        
                                        subj_match = re.search(r'Subject: (.+?)(?:\n|Issuer:|$)', output)
                                        if subj_match:
                                            ssl_subject = subj_match.group(1).strip()
                                        
                                        iss_match = re.search(r'Issuer: (.+?)(?:\n|Validity|$)', output)
                                        if iss_match:
                                            ssl_issuer = iss_match.group(1).strip()
                                        
                                        # Даты сложнее парсить из текста, попробуем найти элементы table
                                        for table in script.findall('table'):
                                            # Логика парсинга таблицы XML
                                            pass 

                            # Обновление актива
                            asset = Asset.query.filter_by(ip_address=ip).first()
                            if not asset:
                                asset = Asset(ip_address=ip, hostname=hostname)
                                db.session.add(asset)
                                db.session.flush()
                            else:
                                if hostname and not asset.hostname:
                                    asset.hostname = hostname
                                if os_match and not asset.os_family:
                                    asset.os_family = os_match.split()[0] # Первое слово
                                    asset.os_version = ' '.join(os_match.split()[1:])
                            
                            # Обновление портов источника nmap
                            # Нужно аккуратно обновить список, не дублируя
                            current_nmap_ports = set(asset.nmap_ports or [])
                            current_nmap_ports.add(port_num)
                            asset.update_ports('nmap', list(current_nmap_ports))
                            
                            # Обновление/Создание сервиса
                            service = ServiceInventory.query.filter_by(
                                asset_id=asset.id, 
                                port=port_num, 
                                protocol=protocol
                            ).first()
                            
                            if not service:
                                service = ServiceInventory(
                                    asset_id=asset.id,
                                    port=port_num,
                                    protocol=protocol,
                                    state='open',
                                    service_name=service_name,
                                    product=product,
                                    version=version,
                                    extra_info=extra_info,
                                    script_output=script_output.strip(),
                                    ssl_subject=ssl_subject,
                                    ssl_issuer=ssl_issuer,
                                    # ssl_not_before/after требуют сложного парсинга даты из строки
                                    discovered_at=datetime.now(MOSCOW_TZ)
                                )
                                db.session.add(service)
                                services_updated += 1
                            else:
                                # Обновление существующего
                                service.state = 'open'
                                service.service_name = service_name
                                service.product = product
                                service.version = version
                                service.extra_info = extra_info
                                if script_output.strip():
                                    service.script_output = script_output.strip()
                                if ssl_subject:
                                    service.ssl_subject = ssl_subject
                                if ssl_issuer:
                                    service.ssl_issuer = ssl_issuer
                            
                            # Лог события
                            log = ActivityLog(
                                asset_id=asset.id,
                                event_type='service_detected',
                                description=f"Обнаружен сервис {service_name} на порту {port_num}",
                                details={'product': product, 'version': version}
                            )
                            db.session.add(log)
                
                hosts_count += 1
            
            db.session.commit()
            print(f"📊 Обработано хостов: {hosts_count}")

    def stop(self):
        """Остановка процесса"""
        if self.process:
            self.process.terminate()
            self.process = None
        if self.current_job_id:
            self._update_job_status('stopped')

    def pause(self):
        """Пауза (Nmap поддерживает SIGSTOP, но в Python сложно реализовать корректно без PGRP)"""
        pass

    def resume(self):
        """Возобновление"""
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
