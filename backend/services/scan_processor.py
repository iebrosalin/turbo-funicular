import logging
import json
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import select

from backend.models.asset import Asset
from backend.models.group import AssetGroup
from backend.models.scan_job import ScanJob, ScanStatus

logger = logging.getLogger(__name__)

class ScanProcessor:
    def __init__(self, db: Session):
        self.db = db

    def process(self, job_id: int):
        """Основной метод обработки результатов сканирования."""
        job = self.db.get(ScanJob, job_id)
        if not job:
            logger.error(f"Задача {job_id} не найдена.")
            return

        logger.info(f"Начало обработки результатов для задачи {job_id} (тип: {job.scan_type})")

        try:
            if job.scan_type == 'nmap':
                self._process_nmap(job)
            elif job.scan_type == 'rustscan':
                self._process_rustscan(job)
            elif job.scan_type == 'dig':
                self._process_dig(job)
            
            job.status = ScanStatus.COMPLETED
            job.completed_at = datetime.utcnow()
            self.db.commit()
            logger.info(f"Задача {job_id} успешно обработана и помечена как завершенная.")
        except Exception as e:
            logger.error(f"Ошибка при обработке задачи {job_id}: {e}", exc_info=True)
            job.status = ScanStatus.FAILED
            job.error_message = str(e)
            self.db.commit()

    def _process_nmap(self, job: ScanJob):
        """Обработка результатов Nmap из XML файла."""
        import os
        xml_path = os.path.join(job.output_dir, 'result.xml')
        
        if not os.path.exists(xml_path):
            # Пробуем альтернативное имя, если nmap сохранил иначе
            for f in os.listdir(job.output_dir):
                if f.endswith('.xml'):
                    xml_path = os.path.join(job.output_dir, f)
                    break
        
        if not os.path.exists(xml_path):
            raise FileNotFoundError(f"XML файл результатов не найден в {job.output_dir}")

        tree = ET.parse(xml_path)
        root = tree.getroot()
        
        hosts_count = 0
        for host in root.findall('host'):
            status_elem = host.find('status')
            if status_elem is None or status_elem.get('state') != 'up':
                continue

            # Извлечение IP
            addr_elem = host.find('address')
            if addr_elem is None:
                continue
            ip_addr = addr_elem.get('addr')
            
            # Извлечение hostname
            hostname = ""
            hostnames_elem = host.find('hostnames')
            if hostnames_elem is not None:
                hn_elem = hostnames_elem.find('hostname')
                if hn_elem is not None:
                    hostname = hn_elem.get('name', "")

            # Извлечение портов и сервисов
            open_ports = []
            services = []
            ports_elem = host.find('ports')
            if ports_elem is not None:
                for port in ports_elem.findall('port'):
                    port_id = port.get('portid')
                    protocol = port.get('protocol')
                    state_elem = port.find('state')
                    
                    if state_elem is not None and state_elem.get('state') == 'open':
                        open_ports.append(int(port_id))
                        
                        service_elem = port.find('service')
                        if service_elem is not None:
                            svc_data = {
                                "port": int(port_id),
                                "protocol": protocol,
                                "name": service_elem.get('name', ''),
                                "product": service_elem.get('product', ''),
                                "version": service_elem.get('version', ''),
                                "extrainfo": service_elem.get('extrainfo', ''),
                                "tunnel": service_elem.get('tunnel', '') # ssl
                            }
                            services.append(svc_data)

            # Извлечение OS
            os_family = None
            os_match = host.find('os/osmatch')
            if os_match is not None:
                os_family = os_match.get('name', '').split()[0] # Берем первое слово (например, Linux)

            # Обновление или создание актива
            self._upsert_asset(ip_addr, {
                "hostname": hostname,
                "open_ports": open_ports,
                "services": services,
                "os_family": os_family,
                "group_id": job.group_id
            })
            hosts_count += 1

        job.result_summary = {"hosts_found": hosts_count}
        logger.info(f"Nmap: Обработано {hosts_count} хостов.")

    def _process_rustscan(self, job: ScanJob):
        """Обработка результатов Rustscan из JSON файла."""
        import os
        json_path = os.path.join(job.output_dir, 'rustscan.json')
        
        if not os.path.exists(json_path):
             for f in os.listdir(job.output_dir):
                if f.endswith('.json') and 'rustscan' in f.lower():
                    json_path = os.path.join(job.output_dir, f)
                    break

        if not os.path.exists(json_path):
            raise FileNotFoundError(f"JSON файл результатов Rustscan не найден в {job.output_dir}")

        with open(json_path, 'r') as f:
            data = json.load(f)

        # Ожидаем список или объект с полями ip/ports
        items = data if isinstance(data, list) else [data]
        
        hosts_count = 0
        for item in items:
            ip = item.get('ip') or item.get('address')
            if not ip:
                continue
            
            ports = item.get('ports', [])
            # Преобразуем в int, если были строки
            open_ports = [int(p) for p in ports]

            self._upsert_asset(ip, {
                "open_ports": open_ports,
                "group_id": job.group_id
            })
            hosts_count += 1
            
        job.result_summary = {"hosts_found": hosts_count}
        logger.info(f"Rustscan: Обработано {hosts_count} хостов.")

    def _process_dig(self, job: ScanJob):
        """Обработка результатов Dig из JSON файла."""
        import os
        json_path = os.path.join(job.output_dir, 'dig.json') # Или result.json
        
        if not os.path.exists(json_path):
             for f in os.listdir(job.output_dir):
                if f.endswith('.json') and ('dig' in f.lower() or 'result' in f.lower()):
                    json_path = os.path.join(job.output_dir, f)
                    break

        if not os.path.exists(json_path):
            raise FileNotFoundError(f"JSON файл результатов Dig не найден в {job.output_dir}")

        with open(json_path, 'r') as f:
            records = json.load(f)

        if not isinstance(records, list):
            records = [records]

        dns_by_ip = {} # Группируем записи по IP для пакетного обновления
        
        for rec in records:
            rec_type = rec.get('type', '')
            rec_data = rec.get('data', '')
            rec_name = rec.get('name', '')
            
            # Если это A или AAAA запись, создаем/обновляем актив
            if rec_type in ['A', 'AAAA']:
                ip = rec_data
                # Сохраняем запись для добавления в актив
                if ip not in dns_by_ip:
                    dns_by_ip[ip] = []
                dns_by_ip[ip].append(rec)
                
                # Создаем актив если нет
                self._upsert_asset(ip, {
                    "hostname": rec_name, # Имя из запроса
                    "group_id": job.group_id
                })
            
            # Если это CNAME, MX и т.д., но мы знаем IP из контекста (упрощено)
            # В полной версии нужно резолвить имена, здесь просто сохраняем если есть IP в data
            
        # Обновляем DNS записи у активов
        for ip, recs in dns_by_ip.items():
            asset = self.db.execute(select(Asset).where(Asset.ip_address == ip)).scalar_one_or_none()
            if asset:
                current_dns = asset.dns_records or []
                # Объединяем, избегая дублей (простая логика)
                existing_types = {(r.get('type'), r.get('data')) for r in current_dns}
                new_recs = [r for r in recs if (r.get('type'), r.get('data')) not in existing_types]
                
                if new_recs:
                    asset.dns_records = (current_dns + new_recs)
                    logger.debug(f"Добавлено {len(new_recs)} DNS записей для {ip}")
        
        self.db.commit()
        job.result_summary = {"records_processed": len(records)}
        logger.info(f"Dig: Обработано {len(records)} записей.")

    def _upsert_asset(self, ip: str, updates: Dict[str, Any]):
        """Создает или обновляет актив."""
        asset = self.db.execute(select(Asset).where(Asset.ip_address == ip)).scalar_one_or_none()
        
        if not asset:
            asset = Asset(ip_address=ip, status='active')
            self.db.add(asset)
            logger.debug(f"Создан новый актив: {ip}")
        else:
            logger.debug(f"Обновление существующего актива: {ip}")

        # Применяем обновления
        for key, value in updates.items():
            if value is not None:
                # Для списков (порты, сервисы) можно решать: заменять или дополнять.
                # Здесь заменяем данными последнего сканирования для простоты, 
                # либо можно реализовать мерж.
                if key == 'open_ports':
                    # Объединяем порты, чтобы не терять старые, если сканирование частичное?
                    # Для простоты заменим на уникальные из нового + старые
                    old_ports = asset.open_ports or []
                    asset.open_ports = list(set(old_ports + value))
                elif key == 'services':
                     # Заменяем полностью услуги для этого хоста (упрощенно)
                     # В идеале нужно мерджить по порту
                     asset.services = value
                elif key == 'dns_records':
                    old_dns = asset.dns_records or []
                    # Простой аппенд без глубокой проверки дублей
                    asset.dns_records = old_dns + value
                else:
                    setattr(asset, key, value)
        
        # Группа
        if updates.get('group_id'):
            asset.group_id = updates['group_id']
            
        asset.updated_at = datetime.utcnow()
