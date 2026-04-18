# scanner.py
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

def parse_targets(target_str):
    """Разбивает строку целей на список IP/CIDR"""
    return [t.strip() for t in re.split(r'[,\s]+', target_str) if t.strip()]

def get_known_ports_for_group(group_id):
    """
    Получает список уникальных портов из всех активов указанной группы.
    Возвращает строку с портами через запятую (например, "22,80,443") или '-' если портов нет.
    """
    if not group_id or group_id == 'ungrouped':
        return '-'
    
    assets = Asset.query.filter_by(group_id=group_id).all()
    all_ports = set()
    
    for asset in assets:
        # Собираем порты из разных полей
        port_sources = [asset.open_ports, asset.rustscan_ports, asset.nmap_ports]
        
        for port_str in port_sources:
            if not port_str:
                continue
            # Пробуем распарсить как JSON список
            try:
                ports_list = json.loads(port_str)
                if isinstance(ports_list, list):
                    for p in ports_list:
                        # Извлекаем номер порта (например, "22/tcp" -> "22")
                        port_num = str(p).split('/')[0]
                        if port_num.isdigit():
                            all_ports.add(port_num)
                    continue
            except (json.JSONDecodeError, TypeError):
                pass
            
            # Если не JSON, пробуем как строку "22/tcp, 80/tcp"
            for item in port_str.split(','):
                item = item.strip()
                if not item:
                    continue
                port_num = item.split('/')[0]
                if port_num.isdigit():
                    all_ports.add(port_num)
    
    if not all_ports:
        return '-'
    
    return ','.join(sorted(all_ports, key=int))

def check_scan_conflicts(target, scan_type):
    """
    Проверка на конфликты сканирований
    Возвращает: (is_blocked, error_message)
    """
    active_jobs = ScanJob.query.filter(
        ScanJob.status.in_(['pending', 'running', 'paused']),
        ScanJob.target == target
    ).all()
    
    if active_jobs:
        return True, f"Активное сканирование уже выполняется для {target} (job #{active_jobs[0].id})"
    
    same_type_jobs = ScanJob.query.filter(
        ScanJob.status.in_(['pending', 'running', 'paused']),
        ScanJob.scan_type == scan_type
    ).all()
    
    if same_type_jobs:
        return True, f"Активное сканирование {scan_type.upper()} уже выполняется (job #{same_type_jobs[0].id})"
    
    return False, None

def validate_custom_args(scan_type, custom_args):
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

def run_rustscan_scan(app, scan_job_id, target, ports, custom_args='', use_known_ports=False):
    """Фоновое выполнение Rustscan с отладкой вывода"""
    with app.app_context():
        try:
            db.session.remove()
            
            # Если выбраны известные порты и цель - группа, получаем порты из активов
            actual_ports = ports
            if use_known_ports and target.startswith('group:'):
                group_id = target.replace('group:', '')
                actual_ports = get_known_ports_for_group(group_id)
                print(f"📦 Использование известных портов для группы {group_id}: {actual_ports}")
            
            targets = parse_targets(target)
            
            is_valid, error_msg, parsed_args = validate_custom_args('rustscan', custom_args)
            if not is_valid:
                update_job(scan_job_id, status='failed', progress=100,
                          error_message=f"Ошибка валидации аргументов:\n{error_msg}", 
                          completed_at=datetime.now(MOSCOW_TZ))
                print(f"❌ Ошибка валидации: {error_msg}")
                return
            
            update_job(scan_job_id, status='running', progress=5, total_hosts=len(targets), 
                      hosts_processed=0, current_target='Инициализация...')
            
            cmd = ['rustscan', '-a', target, '--greppable']
            cmd.extend(parsed_args['rustscan'])
            # Добавляем порты в команду
            if actual_ports and actual_ports != '-':
                cmd.extend(['-p', actual_ports])
            if parsed_args['nmap']:
                cmd.append('--')
                cmd.extend(parsed_args['nmap'])
            
            cmd_str = ' '.join(cmd)
            print(f"🚀 Запуск rustscan job {scan_job_id}")
            print(f"   📜 Команда: {cmd_str}")
            print(f"   🎯 Цель: {target}")
            
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1)
            start_time = time.time()
            processed = 0
            output_lines = []

            for line in iter(process.stdout.readline, ''):
                line = line.strip()
                if line:
                    output_lines.append(line)
                
                job = ScanJob.query.get(scan_job_id)
                if not job: break
                if job.status == 'stopped':
                    process.terminate()
                    update_job(scan_job_id, status='stopped', progress=100, 
                              error_message='Остановлено пользователем', completed_at=datetime.now(MOSCOW_TZ))
                    return
                if job.status == 'paused':
                    time.sleep(0.5)
                    continue

                match = re.match(r'^(\S+)\s+->\s+(.+)$', line)
                if match:
                    processed += 1
                    prog = min(95, 10 + (processed / max(1, len(targets))) * 85)
                    update_job(scan_job_id, progress=int(prog), current_target=match.group(1), hosts_processed=processed)
                else:
                    elapsed = time.time() - start_time
                    if elapsed > 2:
                        update_job(scan_job_id, progress=min(90, 10 + (elapsed / 60) * 80), current_target='Сканирование...')

            process.wait()
            stdout_data, stderr_data = process.communicate()
            
            job = ScanJob.query.get(scan_job_id)
            if not job: 
                print("❌ Job не найден после завершения процесса")
                return

            if process.returncode != 0:
                err_msg = stderr_data.strip() or f"Код возврата: {process.returncode}"
                full_error = f"Ошибка выполнения:\n{err_msg}\n\nКоманда: {cmd_str}"
                update_job(scan_job_id, status='failed', progress=100, error_message=full_error, 
                          completed_at=datetime.now(MOSCOW_TZ))
                print(f"❌ Ошибка rustscan: {err_msg}")
                return

            job.rustscan_output = '\n'.join(output_lines) if output_lines else stdout_data
            
            ts = datetime.now(MOSCOW_TZ).strftime('%Y%m%d_%H%M%S')
            res_dir = os.path.join('scan_results', f'rustscan_{ts}')
            os.makedirs(res_dir, exist_ok=True)
            text_path = os.path.join(res_dir, 'scan.txt')
            with open(text_path, 'w', encoding='utf-8') as f:
                f.write(job.rustscan_output)
            job.rustscan_text_path = text_path
            
            update_job(scan_job_id, progress=98, current_target='Парсинг результатов...')
            
            parse_rustscan_results(scan_job_id, job.rustscan_output, target)
            
            update_job(scan_job_id, progress=100, status='completed', current_target='Готово', 
                      completed_at=datetime.now(MOSCOW_TZ))
            print(f"✅ Job {scan_job_id} завершён успешно")

        except FileNotFoundError:
            update_job(scan_job_id, status='failed', progress=100, 
                      error_message="Утилита rustscan не найдена в PATH.", completed_at=datetime.now(MOSCOW_TZ))
            print("❌ rustscan не установлен или не в PATH")
        except Exception as e:
            update_job(scan_job_id, status='failed', progress=100, 
                      error_message=f"Критическая ошибка: {str(e)}", completed_at=datetime.now(MOSCOW_TZ))
            print(f"❌ Критическая ошибка: {e}")
            import traceback
            traceback.print_exc()
        finally:
            db.session.remove()

def run_nmap_scan(app, scan_job_id, target, ports, scripts, custom_args='', use_known_ports=False):
    """Фоновое выполнение Nmap"""
    with app.app_context():
        try:
            db.session.remove()
            
            # Если выбраны известные порты и цель - группа, получаем порты из активов
            actual_ports = ports
            if use_known_ports and target.startswith('group:'):
                group_id = target.replace('group:', '')
                actual_ports = get_known_ports_for_group(group_id)
                print(f"📦 Использование известных портов для группы {group_id}: {actual_ports}")
            
            targets = parse_targets(target)
            
            is_valid, error_msg, parsed_args = validate_custom_args('nmap', custom_args)
            if not is_valid:
                update_job(scan_job_id, status='failed', progress=100,
                          error_message=f"Ошибка валидации аргументов:\n{error_msg}", 
                          completed_at=datetime.now(MOSCOW_TZ))
                print(f"❌ Ошибка валидации аргументов nmap job {scan_job_id}: {error_msg}")
                return
            
            update_job(scan_job_id, status='running', progress=5, total_hosts=len(targets), 
                      hosts_processed=0, current_target='Инициализация...')
            
            ts = datetime.now(MOSCOW_TZ).strftime('%Y%m%d_%H%M%S')
            res_dir = os.path.join('scan_results', f'nmap_{ts}')
            os.makedirs(res_dir, exist_ok=True)
            base = os.path.join(res_dir, 'scan')
            
            cmd = ['nmap', target]
            cmd.extend(parsed_args['rustscan'] + parsed_args['nmap'])
            if '-p' not in custom_args and actual_ports and actual_ports != '-': 
                cmd.extend(['-p', actual_ports])
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
                if not line: continue
                job = ScanJob.query.get(scan_job_id)
                if not job: break
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
                if hm: update_job(scan_job_id, current_target=hm.group(1))
                sm = re.search(r'(\d+(?:\.\d+)?)%.*?(\d+)\s+hosts scanned', line)
                pm = re.search(r'(\d+(?:\.\d+)?)%', line)
                if sm: update_job(scan_job_id, progress=int(float(sm.group(1))), hosts_processed=int(sm.group(2)))
                elif pm: update_job(scan_job_id, progress=int(float(pm.group(1))))
                else:
                    if time.time() - start_time > 2:
                        update_job(scan_job_id, progress=min(90, 10 + ((time.time()-start_time)/120)*80), current_target='Сканирование...')

            process.wait()
            _, stderr_data = process.communicate()
            
            job = ScanJob.query.get(scan_job_id)
            if not job: return

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
                parse_nmap_results(scan_job_id, job.nmap_xml_path)
            
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

def run_nslookup_scan(app, job_id, targets_text, dns_server='77.88.8.8', cli_args=''):
    """
    Выполняет nslookup для списка доменов.
    ВАЖНО: Первый аргумент - app (объект Flask), чтобы работать в контексте.
    """
    with app.app_context():
        try:
            db.session.remove()
            job = ScanJob.query.get(job_id)
            if not job:
                return

            job.status = 'running'
            job.started_at = datetime.now(MOSCOW_TZ)
            db.session.commit()

            domains = [d.strip() for d in targets_text.split('\n') if d.strip()]
            total = len(domains)
            output_lines = []

            for i, domain in enumerate(domains):
                job.current_target = domain
                job.progress = int((i / total) * 100)
                db.session.commit()

                # Формирование команды: nslookup [опции] домен [сервер]
                cmd = ['nslookup']
                if cli_args:
                    cmd.extend(cli_args.split())
                cmd.append(domain)
                if dns_server:
                    cmd.append(dns_server)

                result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
                output_lines.append(f">>> {domain}\n{result.stdout}")
                if result.stderr:
                    output_lines.append(f"ERROR: {result.stderr}")
                
                # Парсинг результатов сразу
                parse_nslookup_output(result.stdout, domain)

            job.status = 'completed'
            job.nslookup_output = "\n".join(output_lines)
            job.progress = 100
            job.completed_at = datetime.now(MOSCOW_TZ)
            db.session.commit()
            
        except Exception as e:
            if job:
                job.status = 'failed'
                job.error_message = str(e)
                job.nslookup_output = "\n".join(output_lines) if 'output_lines' in locals() else ""
                db.session.commit()
            print(f"❌ Ошибка nslookup: {e}")
            import traceback
            traceback.print_exc()
        finally:
            db.session.remove()

def parse_nslookup_output(output, domain_query):
    """Парсинг вывода nslookup и создание активов"""
    lines = output.split('\n')
    current_ip = None
    current_name = None
    
    for line in lines:
        line = line.strip()
        if line.startswith('Name:'):
            current_name = line.split(':', 1)[1].strip()
        elif line.startswith('Address:') and '#' not in line:
            current_ip = line.split(':', 1)[1].strip()
            
            if current_ip and current_name:
                try:
                    asset = Asset.query.filter_by(ip_address=current_ip).first()
                    if not asset:
                        asset = Asset(
                            ip_address=current_ip,
                            hostname=current_name,
                            status='up',
                            data_source='nslookup'
                        )
                        db.session.add(asset)
                        db.session.flush()
                        log_asset_change(asset.id, 'asset_created', 'ip_address', None, current_ip, None, 'Создан через nslookup')
                    
                    # Обновляем DNS имена
                    if asset.dns_names:
                        try:
                            names = json.loads(asset.dns_names)
                        except:
                            names = []
                    else:
                        names = []
                    
                    if current_name not in names:
                        names.append(current_name)
                        asset.dns_names = json.dumps(names)
                    
                    asset.last_scanned = datetime.now(MOSCOW_TZ)
                    db.session.commit()
                    print(f"✅ NSLookup: Добавлен/обновлен актив {current_ip} ({current_name})")
                    
                except Exception as e:
                    print(f"❌ Ошибка сохранения актива из nslookup: {e}")
                    db.session.rollback()
                
                current_name = None # Сброс для следующей записи

def parse_rustscan_results(scan_job_id, output, target):
    """Парсинг вывода Rustscan с обработкой квадратных скобок"""
    if not output:
        print(f"⚠️ ПУСТОЙ вывод rustscan для job {scan_job_id}")
        return
    
    parsed_count = 0
    
    for line in output.strip().split('\n'):
        line = line.strip()
        if not line or '->' not in line:
            continue
            
        try:
            parts = line.split('->')
            ip = parts[0].strip()
            ports_str = parts[1].strip() if len(parts) > 1 else ''
            
            # Удаляем квадратные скобки
            ports_str = ports_str.replace('[', '').replace(']', '')
            
            new_ports = [p.strip() for p in ports_str.split(',') if p.strip() and p.strip().isdigit()]
            
            if not new_ports:
                continue
            
            formatted_ports = [f"{p}/tcp" for p in new_ports]
            ports_string = ', '.join(sorted(formatted_ports, key=lambda x: int(x.split('/')[0])))
            
            asset = Asset.query.filter_by(ip_address=ip).first()
            if not asset:
                asset = Asset(ip_address=ip, status='up', data_source='scanning',
                             rustscan_ports=ports_string, last_rustscan=datetime.now(MOSCOW_TZ))
                db.session.add(asset)
                db.session.flush()
                log_asset_change(asset.id, 'asset_created', 'ip_address', None, ip, scan_job_id, 'Создан через rustscan')
            else:
                asset.rustscan_ports = ports_string
                asset.last_rustscan = datetime.now(MOSCOW_TZ)
                
                all_ports = set()
                if asset.rustscan_ports: all_ports.update(asset.rustscan_ports.split(', '))
                if asset.nmap_ports: all_ports.update(asset.nmap_ports.split(', '))
                asset.open_ports = ', '.join(sorted(all_ports, key=lambda x: int(x.split('/')[0]) if '/' in x else int(x)))
                asset.device_role, asset.device_tags = detect_device_role_and_tags(asset.open_ports)
            
            asset.last_scanned = datetime.now(MOSCOW_TZ)
            asset.status = 'up'
            
            scanners = json.loads(asset.scanners_used) if asset.scanners_used else []
            if 'rustscan' not in scanners:
                scanners.append('rustscan')
                asset.scanners_used = json.dumps(scanners)
            
            db.session.add(ScanResult(asset_id=asset.id, ip_address=ip, scan_job_id=scan_job_id, 
                                     scan_type='rustscan', ports=json.dumps(formatted_ports), 
                                     scanned_at=datetime.now(MOSCOW_TZ)))
            
            parsed_count += 1
            
        except Exception as e:
            print(f"❌ Ошибка парсинга строки rustscan: {line} - {e}")
            import traceback
            traceback.print_exc()
    
    if parsed_count > 0:
        db.session.commit()
        print(f"🎉 Закоммичено {parsed_count} активов из rustscan job {scan_job_id}")
    else:
        print(f"⚠️ Ни один актив не был обновлён")
        db.session.rollback()

def parse_nmap_results(scan_job_id, xml_path):
    """Парсинг Nmap XML с разделением полей"""
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
        for host in root.findall('host'):
            st = host.find('status')
            if st is None or st.get('state') != 'up': continue
            addr = host.find('address')
            ip = addr.get('addr') if addr is not None else None
            if not ip: continue
            
            hostname, os_info = 'Unknown', 'Unknown'
            hn = host.find('hostnames')
            if hn is not None:
                ne = hn.find('hostname')
                if ne is not None: hostname = ne.get('name')
            oe = host.find('os')
            if oe is not None:
                om = oe.find('osmatch')
                if om is not None: os_info = om.get('name')
            
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
                if asset.rustscan_ports: all_ports.update(asset.rustscan_ports.split(', '))
                if asset.nmap_ports: all_ports.update(asset.nmap_ports.split(', '))
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