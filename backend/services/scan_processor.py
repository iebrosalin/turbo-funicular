import logging
import json
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import select

from backend.models.asset import Asset
from backend.models.group import AssetGroup
from backend.models.scan import ScanJob
from backend.schemas.scan import ScanStatus

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

        logger.info(f"Начало обработки результатов для задачи {job_id} (тип: {job.job_type})")
        
        # Логируем параметры задачи для отладки
        if job.parameters:
            logger.info(f"[DEBUG ScanProcessor] job.parameters содержит ключи: {job.parameters.keys()}")
            raw_output = job.parameters.get('raw_output', '')
            logger.info(f"[DEBUG ScanProcessor] raw_output длина={len(raw_output)}, первые 100 символов: {raw_output[:100] if raw_output else 'ПУСТО'}")
        else:
            logger.error(f"[DEBUG ScanProcessor] job.parameters пуст или None!")

        try:
            if job.job_type == 'nmap':
                self._process_nmap(job)
            elif job.job_type == 'rustscan':
                self._process_rustscan(job)
            elif job.job_type == 'dig':
                self._process_dig(job)
            
            job.status = ScanStatus.COMPLETED.value
            job.completed_at = datetime.utcnow()
            self.db.commit()
            logger.info(f"Задача {job_id} успешно обработана и помечена как завершенная.")
        except Exception as e:
            logger.error(f"Ошибка при обработке задачи {job_id}: {e}", exc_info=True)
            job.status = ScanStatus.FAILED.value
            job.error_message = str(e)
            self.db.commit()

    def _process_nmap(self, job: ScanJob):
        """Обработка результатов Nmap из XML строки."""
        xml_str = job.parameters.get('raw_output', '') if job.parameters else ''
        
        if not xml_str:
            raise FileNotFoundError(f"XML данные результатов не найдены в параметрах задачи {job.id}")

        import xml.etree.ElementTree as ET
        root = ET.fromstring(xml_str)
        
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
                "group_id": job.scan.group_id
            })
            hosts_count += 1

        logger.info(f"Nmap: Обработано {hosts_count} хостов.")

    def _process_rustscan(self, job: ScanJob):
        """Обработка результатов Rustscan из данных задачи."""
        # Получаем результаты из raw_output в параметрах задачи
        raw_output = job.parameters.get('raw_output', '') if job.parameters else ''
        
        if not raw_output:
            raise ValueError(f"Нет данных raw_output для задачи Rustscan {job.id}")

        # Парсим вывод напрямую
        import re
        pattern = r"Open\s+([\d\.]+|[\w\.-]+):(\d+)"
        matches = re.findall(pattern, raw_output)
        
        seen_ips = set()
        hosts_count = 0
        for ip, port in matches:
            if ip not in seen_ips:
                seen_ips.add(ip)
                # Создаем/обновляем актив
                self._upsert_asset(ip, {
                    "open_ports": [int(port)],
                    "group_id": job.scan.group_id
                })
                hosts_count += 1
            else:
                # Обновляем существующий актив с новым портом
                asset = self.db.execute(select(Asset).where(Asset.ip_address == ip)).scalar_one_or_none()
                if asset:
                    old_ports = asset.open_ports or []
                    try:
                        port_int = int(port)
                        if port_int not in old_ports:
                            asset.open_ports = list(set(old_ports + [port_int]))
                    except ValueError:
                        pass
        
        logger.info(f"Rustscan: Обработано {hosts_count} хостов.")

    def _process_dig(self, job: ScanJob):
        """Обработка результатов Dig из данных задачи."""
        # Получаем DNS записи из параметров задачи
        dns_records = job.parameters.get('dns_records', []) if job.parameters else []
        
        if not dns_records:
            raise ValueError(f"Нет данных dns_records для задачи Dig {job.id}")

        if not isinstance(dns_records, list):
            dns_records = [dns_records]

        dns_by_ip = {} # Группируем записи по IP для пакетного обновления
        
        for rec in dns_records:
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
                    "group_id": job.scan.group_id
                })
        
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
        logger.info(f"Dig: Обработано {len(dns_records)} записей.")

    def _upsert_asset(self, ip: str, updates: Dict[str, Any]):
        """Создает или обновляет актив."""
        asset = self.db.execute(select(Asset).where(Asset.ip_address == ip)).scalar_one_or_none()
        
        if not asset:
            asset = Asset(ip_address=ip, status='active')
            self.db.add(asset)
            logger.info(f"[SCAN_PROCESS] СОЗДАН НОВЫЙ АКТИВ: IP={ip}, Группа={updates.get('group_id')}")
        else:
            logger.info(f"[SCAN_PROCESS] ОБНОВЛЕНИЕ АКТИВА: IP={ip}")

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
                    new_ports = list(set(old_ports + value))
                    if len(new_ports) > len(old_ports):
                        logger.debug(f"  - Добавлено портов: {len(new_ports) - len(old_ports)}")
                    asset.open_ports = new_ports
                elif key == 'services':
                     # Заменяем полностью услуги для этого хоста (упрощенно)
                     # В идеале нужно мерджить по порту
                     asset.services = value
                     logger.debug(f"  - Обновлено сервисов: {len(value)}")
                elif key == 'dns_records':
                    old_dns = asset.dns_records or []
                    # Простой аппенд без глубокой проверки дублей
                    asset.dns_records = old_dns + value
                    logger.debug(f"  - Добавлено DNS записей: {len(value)}")
                elif key == 'hostname' and value:
                    if not asset.hostname:
                        asset.hostname = value
                        logger.debug(f"  - Установлен hostname: {value}")
                else:
                    setattr(asset, key, value)
        
        # Группа
        if updates.get('group_id'):
            asset.group_id = updates['group_id']
            
        asset.updated_at = datetime.utcnow()
