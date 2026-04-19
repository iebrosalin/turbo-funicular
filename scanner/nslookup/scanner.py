"""
Модуль для сканирования с помощью Nslookup.
"""
import subprocess
import json
from datetime import datetime
from extensions import db
from models import ScanJob, Asset
from utils import log_asset_change, MOSCOW_TZ


class NslookupScanner:
    """Класс для выполнения сканирования Nslookup"""
    
    def __init__(self, app):
        self.app = app
    
    def scan(self, job_id, targets_text, dns_server='77.88.8.8', cli_args=''):
        """
        Выполняет nslookup для списка доменов.
        
        Args:
            job_id: ID задачи сканирования
            targets_text: Список доменов (каждый с новой строки)
            dns_server: DNS сервер для запросов
            cli_args: Дополнительные аргументы командной строки
        """
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
                    self._parse_nslookup_output(result.stdout, domain)

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
    
    def _parse_nslookup_output(self, output, domain_query):
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
                    
                    current_name = None  # Сброс для следующей записи
