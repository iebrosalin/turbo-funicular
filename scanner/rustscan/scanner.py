"""
Модуль для сканирования с помощью Rustscan.
"""
import os
import re
import subprocess
import time
import json
from datetime import datetime
from extensions import db
from models import ScanJob, Asset, ScanResult
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


class RustscanScanner:
    """Класс для выполнения сканирования Rustscan"""
    
    def __init__(self, app):
        self.app = app
    
    def scan(self, scan_job_id, target, ports='-', custom_args='', run_nmap_after=False, nmap_args=''):
        """
        Фоновое выполнение Rustscan
        
        Args:
            scan_job_id: ID задачи сканирования
            target: Цель сканирования (IP, CIDR)
            ports: Порты для сканирования
            custom_args: Дополнительные аргументы rustscan
            run_nmap_after: Если True, запустить nmap после rustscan
            nmap_args: Аргументы для nmap
        """
        with self.app.app_context():
            try:
                db.session.remove()
                targets = self._parse_targets(target)
                
                # Валидация аргументов
                is_valid, error_msg, parsed_args = self._validate_custom_args(custom_args)
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
                    if not job:
                        break
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
                
                found_ips = self._parse_rustscan_results(scan_job_id, job.rustscan_output, target)
                
                # Если нужно запустить nmap после rustscan
                if run_nmap_after and found_ips:
                    self._queue_nmap_after_rustscan(scan_job_id, found_ips, nmap_args)
                
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
    
    def _parse_rustscan_results(self, scan_job_id, output, target):
        """
        Парсинг вывода Rustscan с обработкой квадратных скобок
        Возвращает список найденных IP адресов
        """
        if not output:
            print(f"⚠️ ПУСТОЙ вывод rustscan для job {scan_job_id}")
            return []
        
        parsed_count = 0
        found_ips = []
        
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
                
                found_ips.append(ip)
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
                    if asset.rustscan_ports:
                        all_ports.update(asset.rustscan_ports.split(', '))
                    if asset.nmap_ports:
                        all_ports.update(asset.nmap_ports.split(', '))
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
        
        return found_ips
    
    def _queue_nmap_after_rustscan(self, rustscan_job_id, found_ips, nmap_args):
        """
        Создаёт и добавляет в очередь задачу nmap для найденных rustscan IP
        """
        from utils.scan_queue import scan_queue_manager
        
        # Создаём новую задачу nmap
        target_ips = ', '.join(found_ips)
        new_job = ScanJob(
            scan_type='nmap',
            target=target_ips,
            status='pending',
            progress=0,
            scan_parameters=json.dumps({
                'ports': '-',
                'scripts': '',
                'args': nmap_args,
                'from_rustscan': True,
                'parent_job_id': rustscan_job_id
            })
        )
        db.session.add(new_job)
        db.session.commit()
        
        # Добавляем в очередь
        app = self.app
        scan_queue_manager.add_to_queue(
            new_job.id,
            'nmap',
            target_ips,
            ports='-',
            scripts='',
            custom_args=nmap_args
        )
        
        print(f"✅ Добавлена задача nmap #{new_job.id} для {len(found_ips)} IP после rustscan #{rustscan_job_id}")
