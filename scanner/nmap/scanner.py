"""
Модуль для сканирования с помощью Nmap.
"""
import os
import re
import subprocess
import time
import json
import xml.etree.ElementTree as ET
from datetime import datetime
from extensions import db
from models import ScanJob, Asset, ScanResult, ServiceInventory
from utils import log_asset_change, detect_device_role_and_tags, MOSCOW_TZ


def update_job(job_id, **kwargs):
    """Безопасное обновление статуса задания в фоновом потоке"""
    try:
        db.session.remove()
        job = ScanJob.query.get(job_id)
        if not job:
            print(f"⚠️ Job {job_id} не найден в БД")
            return
        for k, v in kwargs.items():
            setattr(job, k, v)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print(f"❌ Ошибка БД при обновлении job {job_id}: {e}")


class NmapScanner:
    """Класс для выполнения сканирования Nmap"""
    
    def __init__(self, app):
        self.app = app
    
    def scan(self, scan_job_id, target, ports='-', scripts='', custom_args='', known_ports_only=False, group_ids=None):
        """
        Фоновое выполнение Nmap
        
        Args:
            scan_job_id: ID задачи сканирования
            target: Цель сканирования (IP, CIDR или группа)
            ports: Порты для сканирования
            scripts: Скрипты Nmap
            custom_args: Дополнительные аргументы
            known_ports_only: Если True, сканировать только известные порты активов
            group_ids: Список ID групп для получения известных портов
        """
        with self.app.app_context():
            try:
                db.session.remove()
                
                # Обработка цели
                targets = self._parse_targets(target)
                
                # Если сканирование только известных портов
                if known_ports_only and group_ids:
                    targets_with_ports = self._get_targets_with_known_ports(group_ids)
                    if not targets_with_ports:
                        update_job(scan_job_id, status='failed', progress=100,
                                  error_message="Не найдено активов с известными портами в выбранных группах",
                                  completed_at=datetime.now(MOSCOW_TZ))
                        return
                    
                    # Запускаем сканирование для каждого актива с его портами
                    return self._scan_known_ports(scan_job_id, targets_with_ports, custom_args)
                
                # Валидация аргументов
                is_valid, error_msg, parsed_args = self._validate_custom_args(custom_args)
                if not is_valid:
                    update_job(scan_job_id, status='failed', progress=100,
                              error_message=f"Ошибка валидации аргументов:\n{error_msg}",
                              completed_at=datetime.now(MOSCOW_TZ))
                    print(f"❌ Ошибка валидации аргументов nmap job {scan_job_id}: {error_msg}")
                    return
                
                update_job(scan_job_id, status='running', progress=5, total_hosts=len(targets),
                          hosts_processed=0, current_target='Инициализация...')
                
                # Подготовка директории и команды
                ts = datetime.now(MOSCOW_TZ).strftime('%Y%m%d_%H%M%S')
                res_dir = os.path.join('scan_results', f'nmap_{ts}')
                os.makedirs(res_dir, exist_ok=True)
                base = os.path.join(res_dir, 'scan')
                
                cmd = ['nmap', target]
                cmd.extend(parsed_args['rustscan'] + parsed_args['nmap'])
                if '-p' not in custom_args and ports and ports != '-':
                    cmd.extend(['-p', ports])
                for def_arg in ['-sV', '-sC', '-O', '-v']:
                    if def_arg not in custom_args:
                        cmd.append(def_arg)
                if not any(a in custom_args for a in ['-oA', '-oX', '-oG', '-oN']):
                    cmd.extend(['-oA', base])

                cmd_str = ' '.join(cmd)
                print(f"🚀 Запуск nmap job {scan_job_id}")
                print(f"   📜 Команда: {cmd_str}")
                print(f"   🎯 Цель: {target}")
                
                process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1)
                start_time = time.time()

                for line in iter(process.stdout.readline, ''):
                    line = line.strip()
                    if not line:
                        continue
                    job = ScanJob.query.get(scan_job_id)
                    if not job:
                        break
                    if job.status == 'stopped':
                        process.terminate()
                        update_job(scan_job_id, status='stopped', progress=100,
                                  error_message='Остановлено пользователем', completed_at=datetime.now(MOSCOW_TZ))
                        return
                    if job.status == 'paused':
                        if os.name != 'nt':
                            try:
                                os.kill(process.pid, 19)
                                while True:
                                    cur_job = ScanJob.query.get(scan_job_id)
                                    if not cur_job or cur_job.status != 'paused':
                                        break
                                    time.sleep(0.5)
                                os.kill(process.pid, 18)
                            except ProcessLookupError:
                                break
                        else:
                            while True:
                                cur_job = ScanJob.query.get(scan_job_id)
                                if not cur_job or cur_job.status != 'paused':
                                    break
                                time.sleep(0.5)
                        continue

                    hm = re.search(r'Nmap scan report for (.+)', line)
                    if hm:
                        update_job(scan_job_id, current_target=hm.group(1))
                    sm = re.search(r'(\d+(?:\.\d+)?)%.*?(\d+)\s+hosts scanned', line)
                    pm = re.search(r'(\d+(?:\.\d+)?)%', line)
                    if sm:
                        update_job(scan_job_id, progress=int(float(sm.group(1))), hosts_processed=int(sm.group(2)))
                    elif pm:
                        update_job(scan_job_id, progress=int(float(pm.group(1))))
                    else:
                        if time.time() - start_time > 2:
                            update_job(scan_job_id, progress=min(90, 10 + ((time.time()-start_time)/120)*80), current_target='Сканирование...')

                process.wait()
                _, stderr_data = process.communicate()
                
                job = ScanJob.query.get(scan_job_id)
                if not job:
                    return

                if process.returncode != 0:
                    err_msg = stderr_data.strip() or f"Код возврата: {process.returncode}"
                    full_error = f"Ошибка выполнения:\n{err_msg}\n\nКоманда: {cmd_str}"
                    update_job(scan_job_id, status='failed', progress=100, error_message=full_error,
                              completed_at=datetime.now(MOSCOW_TZ))
                    print(f"❌ Ошибка nmap job {scan_job_id}: {err_msg}")
                    return

                update_job(scan_job_id, progress=98, current_target='Парсинг XML...')
                job.nmap_xml_path = f'{base}.xml'
                job.nmap_grep_path = f'{base}.gnmap'
                job.nmap_normal_path = f'{base}.nmap'
                
                if os.path.exists(job.nmap_xml_path):
                    with open(job.nmap_xml_path, 'r', encoding='utf-8') as f:
                        job.nmap_xml_content = f.read()
                    self._parse_nmap_results(scan_job_id, job.nmap_xml_path)
                
                if os.path.exists(job.nmap_grep_path):
                    with open(job.nmap_grep_path, 'r', encoding='utf-8') as f:
                        job.nmap_grep_content = f.read()
                
                if os.path.exists(job.nmap_normal_path):
                    with open(job.nmap_normal_path, 'r', encoding='utf-8') as f:
                        job.nmap_normal_content = f.read()
                
                update_job(scan_job_id, progress=100, status='completed', current_target='Готово',
                          completed_at=datetime.now(MOSCOW_TZ))
                print(f"✅ Job {scan_job_id} завершён успешно")

            except FileNotFoundError:
                update_job(scan_job_id, status='failed', progress=100,
                          error_message="Утилита nmap не найдена в PATH.", completed_at=datetime.now(MOSCOW_TZ))
                print("❌ nmap не установлен или не в PATH")
            except PermissionError:
                update_job(scan_job_id, status='failed', progress=100,
                          error_message="Нет прав на выполнение nmap.", completed_at=datetime.now(MOSCOW_TZ))
                print("❌ Нет прав на nmap")
            except Exception as e:
                update_job(scan_job_id, status='failed', progress=100,
                          error_message=f"Критическая ошибка: {str(e)}", completed_at=datetime.now(MOSCOW_TZ))
                print(f"❌ Критическая ошибка nmap job {scan_job_id}: {e}")
                import traceback
                traceback.print_exc()
            finally:
                db.session.remove()
    
    def _parse_targets(self, target_str):
        """Разбивает строку целей на список IP/CIDR"""
        return [t.strip() for t in re.split(r'[,\s]+', target_str) if t.strip()]
    
    def _validate_custom_args(self, custom_args):
        """
        Проверка корректности кастомных аргументов перед запуском
        Возвращает: (is_valid, error_message, parsed_args)
        """
        if not custom_args or not custom_args.strip():
            return True, None, {'rustscan': [], 'nmap': []}
        
        args_list = custom_args.split()
        errors = []
        parsed_rustscan = []
        parsed_nmap = []
        
        i = 0
        while i < len(args_list):
            arg = args_list[i]
            if arg == '--':
                i += 1
                continue
            value_args = ['-p', '--ports', '--batch-size', '--timeout', '--top', '-u', '--ulimit']
            if arg in value_args:
                if i + 1 >= len(args_list):
                    errors.append(f"❌ Аргументу '{arg}' требуется значение")
                elif args_list[i+1].startswith('-') and not args_list[i+1][1:].isdigit():
                    errors.append(f"❌ Аргументу '{arg}' требуется значение")
                else:
                    i += 1
            i += 1
        
        i = 0
        while i < len(args_list):
            if args_list[i] in ['-p', '--ports'] and i + 1 < len(args_list):
                port_val = args_list[i+1]
                if not re.match(r'^[\d,\-\s]+$', port_val):
                    errors.append(f"❌ Неверный формат портов: '{port_val}'")
            i += 1
        
        in_nmap_section = False
        for arg in args_list:
            if arg == '--':
                in_nmap_section = True
                continue
            if in_nmap_section:
                parsed_nmap.append(arg)
            else:
                parsed_rustscan.append(arg)
        
        if errors:
            return False, '\n'.join(errors), {'rustscan': parsed_rustscan, 'nmap': parsed_nmap}
        return True, None, {'rustscan': parsed_rustscan, 'nmap': parsed_nmap}
    
    def _get_targets_with_known_ports(self, group_ids):
        """
        Получает список активов с известными портами из указанных групп
        Возвращает список кортежей (ip_address, ports_string)
        """
        from models import Group, AssetGroup
        
        targets_with_ports = []
        
        # Получаем все активы из указанных групп
        for group_id in group_ids:
            group_assets = db.session.query(Asset).join(AssetGroup).filter(
                AssetGroup.group_id == group_id,
                Asset.open_ports.isnot(None),
                Asset.open_ports != ''
            ).all()
            
            for asset in group_assets:
                targets_with_ports.append((asset.ip_address, asset.open_ports))
        
        return targets_with_ports
    
    def _scan_known_ports(self, scan_job_id, targets_with_ports, custom_args):
        """
        Выполняет сканирование Nmap для каждого актива с его известными портами
        targets_with_ports: список кортежей (ip, ports)
        """
        total = len(targets_with_ports)
        if total == 0:
            return
        
        for idx, (ip, ports) in enumerate(targets_with_ports):
            update_job(scan_job_id, 
                      current_target=f"{ip} ({idx+1}/{total})",
                      progress=int((idx / total) * 95))
            
            ts = datetime.now(MOSCOW_TZ).strftime('%Y%m%d_%H%M%S')
            res_dir = os.path.join('scan_results', f'nmap_{ts}_{ip.replace(".", "_")}')
            os.makedirs(res_dir, exist_ok=True)
            base = os.path.join(res_dir, 'scan')
            
            cmd = ['nmap', ip, '-p', ports]
            cmd.extend(['-sV', '-sC', '-v'])
            cmd.extend(['-oA', base])
            
            # Добавляем кастомные аргументы если есть
            if custom_args:
                cmd.extend(custom_args.split())
            
            cmd_str = ' '.join(cmd)
            print(f"🚀 Сканирование {ip} на портах {ports}")
            print(f"   📜 Команда: {cmd_str}")
            
            try:
                process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                process.wait()
                
                if process.returncode == 0:
                    # Сохраняем пути к файлам
                    job = ScanJob.query.get(scan_job_id)
                    if job:
                        # Объединяем результаты в один файл
                        existing_output = job.nmap_normal_content or ''
                        if os.path.exists(f'{base}.nmap'):
                            with open(f'{base}.nmap', 'r', encoding='utf-8') as f:
                                existing_output += f"\n\n=== {ip} ===\n" + f.read()
                            job.nmap_normal_content = existing_output
                        
                        if os.path.exists(f'{base}.xml'):
                            with open(f'{base}.xml', 'r', encoding='utf-8') as f:
                                self._parse_nmap_xml_content(scan_job_id, f.read(), ip)
                        
                        db.session.commit()
                        
            except Exception as e:
                print(f"❌ Ошибка сканирования {ip}: {e}")
        
        update_job(scan_job_id, progress=100, status='completed', current_target='Готово',
                  completed_at=datetime.now(MOSCOW_TZ))
    
    def _parse_nmap_results(self, scan_job_id, xml_path):
        """Парсинг Nmap XML с разделением полей"""
        try:
            tree = ET.parse(xml_path)
            root = tree.getroot()
            for host in root.findall('host'):
                st = host.find('status')
                if st is None or st.get('state') != 'up':
                    continue
                addr = host.find('address')
                ip = addr.get('addr') if addr is not None else None
                if not ip:
                    continue
                
                hostname, os_info = 'Unknown', 'Unknown'
                hn = host.find('hostnames')
                if hn is not None:
                    ne = hn.find('hostname')
                    if ne is not None:
                        hostname = ne.get('name')
                oe = host.find('os')
                if oe is not None:
                    om = oe.find('osmatch')
                    if om is not None:
                        os_info = om.get('name')
                
                ports, services = [], []
                pe = host.find('ports')
                if pe is not None:
                    for port in pe.findall('port'):
                        state = port.find('state')
                        if state is not None and state.get('state') == 'open':
                            pid, proto = port.get('portid'), port.get('protocol')
                            svc = port.find('service')
                            s = {'name': svc.get('name') if svc is not None else '',
                                 'product': svc.get('product') if svc is not None else '',
                                 'version': svc.get('version') if svc is not None else '',
                                 'extrainfo': svc.get('extrainfo') if svc is not None else ''}
                            pstr = f"{pid}/{proto}"
                            ports.append(pstr)
                            services.append(s)
                            asset = Asset.query.filter_by(ip_address=ip).first()
                            if asset:
                                ex = ServiceInventory.query.filter_by(asset_id=asset.id, port=pstr).first()
                                if ex:
                                    ex.service_name = s['name']
                                    ex.product = s['product']
                                    ex.version = s['version']
                                    ex.extrainfo = s['extrainfo']
                                    ex.last_seen = datetime.now(MOSCOW_TZ)
                                    ex.is_active = True
                                else:
                                    db.session.add(ServiceInventory(asset_id=asset.id, port=pstr, protocol=proto,
                                                                   service_name=s['name'], product=s['product'],
                                                                   version=s['version'], extrainfo=s['extrainfo']))
                                    log_asset_change(asset.id, 'service_detected', 'service_inventory', None, s['name'], scan_job_id, f'Порт {pstr}')
                
                asset = Asset.query.filter_by(ip_address=ip).first()
                if not asset:
                    asset = Asset(ip_address=ip, status='up')
                    db.session.add(asset)
                    db.session.flush()
                
                if asset.os_info != os_info and os_info != 'Unknown':
                    log_asset_change(asset.id, 'os_changed', 'os_info', asset.os_info, os_info, scan_job_id)
                asset.hostname = hostname if hostname != 'Unknown' else asset.hostname
                asset.os_info = os_info if os_info != 'Unknown' else asset.os_info
                
                if ports:
                    ports_string = ', '.join(sorted(ports, key=lambda x: int(x.split('/')[0])))
                    old_nmap = asset.nmap_ports or ''
                    if old_nmap != ports_string:
                        log_asset_change(asset.id, 'nmap_ports_changed', 'nmap_ports', old_nmap, ports_string, scan_job_id)
                    asset.nmap_ports = ports_string
                    all_ports = set()
                    if asset.rustscan_ports:
                        all_ports.update(asset.rustscan_ports.split(', '))
                    if asset.nmap_ports:
                        all_ports.update(asset.nmap_ports.split(', '))
                    asset.open_ports = ', '.join(sorted(all_ports, key=lambda x: int(x.split('/')[0]) if '/' in x else int(x)))
                    asset.device_role, asset.device_tags = detect_device_role_and_tags(asset.open_ports, services)
                
                asset.last_scanned = datetime.now(MOSCOW_TZ)
                asset.last_nmap = datetime.now(MOSCOW_TZ)
                asset.data_source = 'scanning'
                scanners = json.loads(asset.scanners_used) if asset.scanners_used else []
                if 'nmap' not in scanners:
                    scanners.append('nmap')
                    asset.scanners_used = json.dumps(scanners)
                
                db.session.add(ScanResult(asset_id=asset.id, ip_address=ip, scan_job_id=scan_job_id,
                                         scan_type='nmap', ports=json.dumps(ports), services=json.dumps(services),
                                         os_detection=os_info, scanned_at=datetime.now(MOSCOW_TZ)))
            
            db.session.commit()
            print(f"🎉 Закоммичены результаты nmap job {scan_job_id}")
        except Exception as e:
            print(f"❌ Ошибка парсинга nmap XML: {e}")
            import traceback
            traceback.print_exc()
    
    def _parse_nmap_xml_content(self, scan_job_id, xml_content, target_ip=None):
        """Парсинг XML контента напрямую (без файла)"""
        try:
            root = ET.fromstring(xml_content)
            # Логика аналогична _parse_nmap_results
        except Exception as e:
            print(f"❌ Ошибка парсинга nmap XML content: {e}")
