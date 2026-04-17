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

# 🔥 Функция check_scan_conflicts остаётся в scanner.py для импорта в routes
def check_scan_conflicts(target, scan_type):
    """
    🔥 Проверка на конфликты сканирований
    Возвращает: (is_blocked, error_message)
    """
    # Проверка активных сканирований той же цели
    active_jobs = ScanJob.query.filter(
        ScanJob.status.in_(['pending', 'running', 'paused']),
        ScanJob.target == target
    ).all()
    
    if active_jobs:
        return True, f"Активное сканирование уже выполняется для {target} (job #{active_jobs[0].id})"
    
    # Проверка активных сканирований того же типа
    same_type_jobs = ScanJob.query.filter(
        ScanJob.status.in_(['pending', 'running', 'paused']),
        ScanJob.scan_type == scan_type
    ).all()
    
    if same_type_jobs:
        return True, f"Активное сканирование {scan_type.upper()} уже выполняется (job #{same_type_jobs[0].id})"
    
    return False, None

def validate_custom_args(scan_type, custom_args):
    """
    🔥 Проверка корректности кастомных аргументов перед запуском
    Возвращает: (is_valid, error_message, parsed_args)
    """
    if not custom_args or not custom_args.strip():
        return True, None, {'rustscan': [], 'nmap': []}
    
    args_list = custom_args.split()
    errors = []
    parsed_rustscan = []
    parsed_nmap = []
    
    # Проверка баланса флагов и значений
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
    
    # Проверка портов
    i = 0
    while i < len(args_list):
        if args_list[i] in ['-p', '--ports'] and i + 1 < len(args_list):
            port_val = args_list[i+1]
            if not re.match(r'^[\d,\-\s]+$', port_val):
                errors.append(f"❌ Неверный формат портов: '{port_val}'")
        i += 1
    
    # Разделение аргументов Rustscan и Nmap
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

def run_rustscan_scan(app, scan_job_id, target, custom_args=''):
    """Фоновое выполнение Rustscan с отладкой вывода"""
    with app.app_context():
        try:
            db.session.remove()
            targets = parse_targets(target)
            
            # Валидация
            is_valid, error_msg, parsed_args = validate_custom_args('rustscan', custom_args)
            if not is_valid:
                update_job(scan_job_id, status='failed', progress=100,
                          error_message=f"Ошибка валидации аргументов:\n{error_msg}", 
                          completed_at=datetime.now(MOSCOW_TZ))
                print(f"❌ Ошибка валидации: {error_msg}")
                return
            
            update_job(scan_job_id, status='running', progress=5, total_hosts=len(targets), 
                      hosts_processed=0, current_target='Инициализация...')
            
            # Сборка команды
            cmd = ['rustscan', '-a', target, '--greppable']
            cmd.extend(parsed_args['rustscan'])
            if parsed_args['nmap']:
                cmd.append('--')
                cmd.extend(parsed_args['nmap'])
            
            cmd_str = ' '.join(cmd)
            print(f"🚀 Запуск rustscan job {scan_job_id}")
            print(f"   📜 Команда: {cmd_str}")
            print(f"   🎯 Цель: {target}")
            
            # 🔥 Запуск с захватом stdout
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1)
            start_time = time.time()
            processed = 0
            output_lines = []

            # 🔥 Читаем stdout ПОСТРОЧНО
            for line in iter(process.stdout.readline, ''):
                line = line.strip()
                print(f"📝 Rustscan stdout: {line}")  # 🔥 ОТЛАДКА
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
            
            print(f"📊 Process returncode: {process.returncode}")
            print(f"📊 Output lines collected: {len(output_lines)}")
            print(f"📊 Stdout data length: {len(stdout_data) if stdout_data else 0}")
            print(f"📊 Stderr data: {stderr_data[:500] if stderr_data else 'None'}")
            
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

            # 🔥 Сохраняем вывод ДВУМЯ способами: в БД и в файл
            job.rustscan_output = '\n'.join(output_lines) if output_lines else stdout_data
            
            # 🔥 Сохраняем результат в текстовый файл
            ts = datetime.now(MOSCOW_TZ).strftime('%Y%m%d_%H%M%S')
            res_dir = os.path.join('scan_results', f'rustscan_{ts}')
            os.makedirs(res_dir, exist_ok=True)
            text_path = os.path.join(res_dir, 'scan.txt')
            with open(text_path, 'w', encoding='utf-8') as f:
                f.write(job.rustscan_output)
            job.rustscan_text_path = text_path
            
            print(f"📝 Сохранён вывод: {len(job.rustscan_output)} символов")
            print(f"📁 Файл сохранён: {text_path}")
            print(f"📝 Первые 500 символов: {job.rustscan_output[:500]}")
            
            # 🔥 Читаем содержимое файла и сохраняем в БД
            with open(text_path, 'r', encoding='utf-8') as f:
                job.rustscan_output = f.read()
            
            update_job(scan_job_id, progress=98, current_target='Парсинг результатов...')
            
            # 🔥 Вызываем парсер с явной передачей вывода
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

def run_nmap_scan(app, scan_job_id, target, ports=None, custom_args=''):
    """
    Фоновое выполнение Nmap
    🔥 ПРОВЕРКА КОНФЛИКТОВ УДАЛЕНА — выполняется только в маршруте до создания job
    """
    with app.app_context():
        try:
            db.session.remove()
            targets = parse_targets(target)
            
            # 🔥 ВАЛИДАЦИЯ АРГУМЕНТОВ (остаётся)
            is_valid, error_msg, parsed_args = validate_custom_args('nmap', custom_args)
            if not is_valid:
                update_job(scan_job_id, status='failed', progress=100,
                          error_message=f"Ошибка валидации аргументов:\n{error_msg}", 
                          completed_at=datetime.now(MOSCOW_TZ))
                print(f"❌ Ошибка валидации аргументов nmap job {scan_job_id}: {error_msg}")
                return
            
            # 🔥 ПРОВЕРКА КОНФЛИКТОВ УДАЛЕНА отсюда!
            
            update_job(scan_job_id, status='running', progress=5, total_hosts=len(targets), 
                      hosts_processed=0, current_target='Инициализация...')
            
            ts = datetime.now(MOSCOW_TZ).strftime('%Y%m%d_%H%M%S')
            res_dir = os.path.join('scan_results', f'nmap_{ts}')
            os.makedirs(res_dir, exist_ok=True)
            base = os.path.join(res_dir, 'scan')
            
            cmd = ['nmap', target]
            cmd.extend(parsed_args['rustscan'] + parsed_args['nmap'])
            if '-p' not in custom_args and ports: 
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
                        os.kill(process.pid, 19)
                        while ScanJob.query.get(scan_job_id).status == 'paused': time.sleep(0.5)
                        os.kill(process.pid, 18)
                    else:
                        while ScanJob.query.get(scan_job_id).status == 'paused': time.sleep(0.5)
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
            
            # 🔥 Читаем содержимое файлов и сохраняем в БД
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

        except FileNotFoundError as e:
            update_job(scan_job_id, status='failed', progress=100, 
                      error_message=f"Утилита nmap не найдена в PATH.", completed_at=datetime.now(MOSCOW_TZ))
            print(f"❌ nmap не установлен или не в PATH")
        except PermissionError as e:
            update_job(scan_job_id, status='failed', progress=100, 
                      error_message=f"Нет прав на выполнение nmap.", completed_at=datetime.now(MOSCOW_TZ))
            print(f"❌ Нет прав на nmap")
        except Exception as e:
            update_job(scan_job_id, status='failed', progress=100, 
                      error_message=f"Критическая ошибка: {str(e)}", completed_at=datetime.now(MOSCOW_TZ))
            print(f"❌ Критическая ошибка nmap job {scan_job_id}: {e}")
            import traceback
            traceback.print_exc()
        finally:
            db.session.remove()

def run_nslookup_scan(app, scan_job_id, target_list):
    """Фоновое выполнение nslookup для списка доменных имён"""
    with app.app_context():
        try:
            db.session.remove()
            
            # Парсим список доменов (разделённые переносом строки)
            if isinstance(target_list, str):
                domains = [d.strip() for d in target_list.split('\n') if d.strip()]
            else:
                domains = target_list
            
            if not domains:
                update_job(scan_job_id, status='failed', progress=100,
                          error_message="Список доменов пуст", 
                          completed_at=datetime.now(MOSCOW_TZ))
                return
            
            update_job(scan_job_id, status='running', progress=5, total_hosts=len(domains), 
                      hosts_processed=0, current_target='Инициализация...')
            
            # Сохраняем результаты
            ts = datetime.now(MOSCOW_TZ).strftime('%Y%m%d_%H%M%S')
            res_dir = os.path.join('scan_results', f'nslookup_{ts}')
            os.makedirs(res_dir, exist_ok=True)
            output_file = os.path.join(res_dir, 'results.txt')
            
            results = []
            processed = 0
            
            for domain in domains:
                job = ScanJob.query.get(scan_job_id)
                if not job:
                    break
                if job.status == 'stopped':
                    update_job(scan_job_id, status='stopped', progress=100, 
                              error_message='Остановлено пользователем', completed_at=datetime.now(MOSCOW_TZ))
                    return
                if job.status == 'paused':
                    time.sleep(0.5)
                    continue
                
                update_job(scan_job_id, current_target=domain, hosts_processed=processed)
                
                try:
                    # Выполняем nslookup
                    process = subprocess.Popen(['nslookup', domain], 
                                             stdout=subprocess.PIPE, 
                                             stderr=subprocess.PIPE, 
                                             text=True)
                    stdout, stderr = process.communicate(timeout=30)
                    
                    result_entry = f"\n{'='*60}\nДомен: {domain}\n{'='*60}\n"
                    if process.returncode == 0:
                        result_entry += stdout
                        results.append({'domain': domain, 'status': 'success', 'output': stdout})
                    else:
                        result_entry += f"Ошибка: {stderr}\n"
                        results.append({'domain': domain, 'status': 'failed', 'error': stderr})
                    
                    # Записываем в файл
                    with open(output_file, 'a', encoding='utf-8') as f:
                        f.write(result_entry)
                    
                    processed += 1
                    prog = min(95, 10 + (processed / len(domains)) * 85)
                    update_job(scan_job_id, progress=int(prog))
                    
                except subprocess.TimeoutExpired:
                    error_msg = f"Превышено время ожидания для {domain}"
                    results.append({'domain': domain, 'status': 'timeout', 'error': error_msg})
                    with open(output_file, 'a', encoding='utf-8') as f:
                        f.write(f"\n{'='*60}\nДомен: {domain}\n{'='*60}\nОшибка: {error_msg}\n")
                except FileNotFoundError:
                    update_job(scan_job_id, status='failed', progress=100,
                              error_message="Утилита nslookup не найдена в PATH.", 
                              completed_at=datetime.now(MOSCOW_TZ))
                    return
                except Exception as e:
                    results.append({'domain': domain, 'status': 'error', 'error': str(e)})
                    with open(output_file, 'a', encoding='utf-8') as f:
                        f.write(f"\n{'='*60}\nДомен: {domain}\n{'='*60}\nОшибка: {str(e)}\n")
            
            # Читаем содержимое файла и сохраняем в БД
            with open(output_file, 'r', encoding='utf-8') as f:
                nslookup_output = f.read()
            
            job = ScanJob.query.get(scan_job_id)
            if job:
                job.nslookup_output = nslookup_output
                job.nslookup_file_path = output_file
                update_job(scan_job_id, progress=100, status='completed', current_target='Готово', 
                          completed_at=datetime.now(MOSCOW_TZ))
                print(f"✅ Job {scan_job_id} nslookup завершён успешно")
                print(f"📁 Файл сохранён: {output_file}")
                print(f"📊 Обработано доменов: {processed}/{len(domains)}")
            
        except Exception as e:
            update_job(scan_job_id, status='failed', progress=100, 
                      error_message=f"Критическая ошибка: {str(e)}", completed_at=datetime.now(MOSCOW_TZ))
            print(f"❌ Критическая ошибка nslookup job {scan_job_id}: {e}")
            import traceback
            traceback.print_exc()
        finally:
            db.session.remove()

def parse_rustscan_results(scan_job_id, output, target):
    """Парсинг вывода Rustscan с обработкой квадратных скобок"""
    print(f"🔍 Парсинг rustscan job {scan_job_id}...")
    print(f"🔍 Вывод получен: {bool(output)}")
    print(f"🔍 Длина вывода: {len(output) if output else 0}")
    
    if not output:
        print(f"⚠️ ПУСТОЙ вывод rustscan для job {scan_job_id}")
        return
    
    parsed_count = 0
    
    for line in output.strip().split('\n'):
        line = line.strip()
        print(f"🔍 Строка: '{line}'")
        
        if not line or '->' not in line:
            print(f"⚠️ Пропущено (нет '->'): {line}")
            continue
            
        try:
            parts = line.split('->')
            ip = parts[0].strip()
            ports_str = parts[1].strip() if len(parts) > 1 else ''
            
            # 🔥 УДАЛЯЕМ КВАДРАТНЫЕ СКОБКИ
            ports_str = ports_str.replace('[', '').replace(']', '')
            
            print(f"🔍 IP: {ip}, Порты (после очистки): {ports_str}")
            
            # Теперь разбиваем по запятым и проверяем isdigit()
            new_ports = [p.strip() for p in ports_str.split(',') if p.strip() and p.strip().isdigit()]
            
            if not new_ports:
                print(f"⚠️ Не найдено портов для {ip}")
                continue
            
            formatted_ports = [f"{p}/tcp" for p in new_ports]
            ports_string = ', '.join(sorted(formatted_ports, key=lambda x: int(x.split('/')[0])))
            
            asset = Asset.query.filter_by(ip_address=ip).first()
            if not asset:
                print(f"🆕 Создаю новый актив для {ip}")
                asset = Asset(ip_address=ip, status='up', data_source='scanning',
                             rustscan_ports=ports_string, last_rustscan=datetime.now(MOSCOW_TZ))
                db.session.add(asset)
                db.session.flush()
                log_asset_change(asset.id, 'asset_created', 'ip_address', None, ip, scan_job_id, 'Создан через rustscan')
            else:
                print(f"✏️ Обновляю существующий актив {ip}")
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
            print(f"✅ Обработан {ip}: порты {', '.join(new_ports)}")
            
        except Exception as e:
            print(f"❌ Ошибка парсинга строки: {line}")
            print(f"❌ Ошибка: {e}")
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
                                ex.service_name, ex.product, ex.version, ex.extrainfo, ex.last_seen, ex.is_active = \
                                    s['name'], s['product'], s['version'], s['extrainfo'], datetime.now(MOSCOW_TZ), True
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