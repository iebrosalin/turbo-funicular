"""
Модуль для сканирования с помощью dig.
Заменяет nslookup для более гибкого DNS-сканирования.
"""
import subprocess
import json
import re
from datetime import datetime
from extensions import db
from models import ScanJob, Asset
from utils import log_asset_change, MOSCOW_TZ


class DigScanner:
    """Класс для выполнения сканирования dig"""
    
    def __init__(self, app):
        self.app = app
    
    def scan(self, job_id, targets_text, dns_server='77.88.8.8', cli_args='', record_types=None):
        """
        Выполняет dig для списка доменов.
        
        Args:
            job_id: ID задачи сканирования
            targets_text: Список доменов (каждый с новой строки)
            dns_server: DNS сервер для запросов
            cli_args: Дополнительные аргументы командной строки
            record_types: Список типов DNS записей для сканирования (A, AAAA, MX, TXT и т.д.)
        """
        if record_types is None:
            record_types = ['A', 'AAAA', 'MX', 'TXT', 'NS', 'CNAME', 'SOA', 'PTR', 'SRV']
        
        with self.app.app_context():
            try:
                db.session.remove()
                job = ScanJob.query.get(job_id)
                if not job:
                    return

                job.status = 'running'
                job.started_at = datetime.now(MOSCOW_TZ)
                db.session.commit()

                domains = [d.strip() for d in targets_text.split('\n') if d.strip()]
                total = len(domains) * len(record_types)
                output_lines = []
                processed = 0

                for domain in domains:
                    for record_type in record_types:
                        job.current_target = f"{domain} ({record_type})"
                        job.progress = int((processed / total) * 100)
                        db.session.commit()

                        # Формирование команды: dig [@сервер] домен тип [опции]
                        cmd = ['dig']
                        if dns_server:
                            cmd.append(f'@{dns_server}')
                        cmd.append(domain)
                        cmd.append(record_type)
                        
                        # Добавляем короткие опции для чистого вывода
                        cmd.extend(['+short', '+noall', '+answer'])
                        
                        if cli_args:
                            # Разбиваем аргументы, но не добавляем +short если уже есть
                            args_list = cli_args.split()
                            cmd.extend([arg for arg in args_list if not arg.startswith('+')])

                        try:
                            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
                            output_section = f">>> dig {record_type} {domain}\n"
                            if result.stdout:
                                output_section += result.stdout
                            if result.stderr:
                                output_section += f"ERROR: {result.stderr}\n"
                            output_lines.append(output_section)
                            
                            # Парсинг результатов сразу
                            self._parse_dig_output(result.stdout, domain, record_type)
                            
                        except subprocess.TimeoutExpired:
                            output_lines.append(f">>> dig {record_type} {domain}\nTIMEOUT\n")
                        except Exception as e:
                            output_lines.append(f">>> dig {record_type} {domain}\nERROR: {str(e)}\n")
                        
                        processed += 1

                job.status = 'completed'
                job.nslookup_output = "\n".join(output_lines)  # Используем поле nslookup_output для совместимости
                job.progress = 100
                job.completed_at = datetime.now(MOSCOW_TZ)
                db.session.commit()
                
            except Exception as e:
                if job:
                    job.status = 'failed'
                    job.error_message = str(e)
                    job.nslookup_output = "\n".join(output_lines) if 'output_lines' in locals() else ""
                    db.session.commit()
                print(f"❌ Ошибка dig: {e}")
                import traceback
                traceback.print_exc()
            finally:
                db.session.remove()
    
    def _parse_dig_output(self, output, domain, record_type):
        """Парсинг вывода dig и создание активов"""
        lines = output.strip().split('\n')
        
        for line in lines:
            line = line.strip()
            if not line or line.startswith(';'):
                continue
            
            # Разные форматы вывода для разных типов записей
            if record_type == 'A':
                # IP адрес
                ip_match = re.match(r'^(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})$', line)
                if ip_match:
                    ip_address = ip_match.group(1)
                    self._create_or_update_asset(ip_address, domain, record_type)
            
            elif record_type == 'AAAA':
                # IPv6 адрес
                ipv6_pattern = r'^([0-9a-fA-F:]+)$'
                ipv6_match = re.match(ipv6_pattern, line)
                if ipv6_match:
                    # Для IPv6 пока просто логируем, можно добавить поддержку
                    print(f"🔍 Найден IPv6 для {domain}: {line}")
            
            elif record_type in ['MX', 'NS', 'CNAME']:
                # Формат: priority target. или canonical name.
                parts = line.split()
                if parts:
                    target = parts[-1].rstrip('.')
                    if record_type == 'MX' and len(parts) > 1:
                        priority = parts[0]
                        print(f"📧 MX запись для {domain}: {priority} -> {target}")
                    else:
                        # Пробуем разрешить имя в IP
                        self._resolve_and_create_asset(target, domain, record_type)
            
            elif record_type == 'TXT':
                # TXT записи
                txt_match = re.match(r'^"?([^"]+)"?$', line)
                if txt_match:
                    print(f"📝 TXT запись для {domain}: {txt_match.group(1)}")
            
            elif record_type == 'SOA':
                # SOA записи
                print(f"🏛️ SOA запись для {domain}: {line}")
            
            elif record_type == 'PTR':
                # PTR записи (reverse DNS)
                ptr_match = re.match(r'^(.+)\.$', line)
                if ptr_match:
                    print(f"🔄 PTR запись: {domain} -> {ptr_match.group(1)}")
    
    def _resolve_and_create_asset(self, hostname, original_domain, record_type):
        """Разрешение имени хоста и создание актива"""
        try:
            cmd = ['dig', '+short', 'A', hostname]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            if result.stdout:
                ips = [ip.strip() for ip in result.stdout.strip().split('\n') if ip.strip()]
                for ip in ips:
                    self._create_or_update_asset(ip, hostname, record_type, original_domain)
        except Exception as e:
            print(f"⚠️ Не удалось разрешить {hostname}: {e}")
    
    def _create_or_update_asset(self, ip_address, hostname, record_type, original_domain=None):
        """Создание или обновление актива"""
        try:
            asset = Asset.query.filter_by(ip_address=ip_address).first()
            if not asset:
                asset = Asset(
                    ip_address=ip_address,
                    hostname=hostname,
                    status='up',
                    data_source='dig'
                )
                db.session.add(asset)
                db.session.flush()
                log_asset_change(asset.id, 'asset_created', 'ip_address', None, ip_address, None, 'Создан через dig')
                print(f"✅ DIG: Создан актив {ip_address} ({hostname})")
            else:
                # Обновляем DNS имена
                if asset.dns_names:
                    try:
                        names = json.loads(asset.dns_names)
                    except:
                        names = []
                else:
                    names = []
                
                # Добавляем все связанные имена
                names_to_add = [hostname]
                if original_domain and original_domain != hostname:
                    names_to_add.append(original_domain)
                
                for name in names_to_add:
                    if name not in names:
                        names.append(name)
                
                if names:
                    asset.dns_names = json.dumps(names)
                
                asset.last_scanned = datetime.now(MOSCOW_TZ)
                print(f"✅ DIG: Обновлен актив {ip_address} ({hostname})")
            
            db.session.commit()
            
        except Exception as e:
            print(f"❌ Ошибка сохранения актива из dig: {e}")
            db.session.rollback()
