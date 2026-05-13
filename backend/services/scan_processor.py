import logging
import json
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from backend.models.asset import Asset
from backend.models.group import Group
from backend.models.scan import ScanJob
from backend.models.service import ServiceInventory
from backend.schemas.scan import ScanStatus

logger = logging.getLogger(__name__)

class ScanProcessor:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def process(self, job_id: int, parameters: Optional[Dict[str, Any]] = None):
        """Основной метод обработки результатов сканирования.
        
        Args:
            job_id: ID задачи сканирования
            parameters: Опциональные параметры задачи (чтобы избежать проблем с чтением из БД)
        """
        # Явно загружаем задачу вместе со связью scan и group
        stmt = select(ScanJob).options(
            selectinload(ScanJob.scan).selectinload(Scan.group)
        ).where(ScanJob.id == job_id)
        result = await self.db.execute(stmt)
        job = result.scalar_one_or_none()
        
        if not job:
            logger.error(f"Задача {job_id} не найдена.")
            return

        logger.info(f"Начало обработки результатов для задачи {job_id} (тип: {job.job_type})")
        
        # Используем переданные параметры если они есть, иначе читаем из БД
        job_params = parameters if parameters is not None else (job.parameters or {})
        
        # Логируем параметры задачи для отладки
        if job_params:
            logger.info(f"[DEBUG ScanProcessor] job.parameters содержит ключи: {job_params.keys()}")
            raw_output = job_params.get('raw_output', '')
            logger.info(f"[DEBUG ScanProcessor] raw_output длина={len(raw_output)}, первые 100 символов: {raw_output[:100] if raw_output else 'ПУСТО'}")
        else:
            logger.error(f"[DEBUG ScanProcessor] job.parameters пуст или None!")

        try:
            if job.job_type == 'nmap':
                await self._process_nmap(job, job_params)
            elif job.job_type == 'rustscan':
                await self._process_rustscan(job, job_params)
            elif job.job_type == 'dig':
                await self._process_dig(job, job_params)
            
            job.status = ScanStatus.COMPLETED.value
            job.completed_at = datetime.utcnow()
            await self.db.commit()
            logger.info(f"Задача {job_id} успешно обработана и помечена как завершенная.")
        except Exception as e:
            logger.error(f"Ошибка при обработке задачи {job_id}: {e}", exc_info=True)
            job.status = ScanStatus.FAILED.value
            job.error_message = str(e)
            await self.db.commit()

    async def _process_nmap(self, job: ScanJob, job_params: Dict[str, Any]):
        """Обработка результатов Nmap из XML строки."""
        # Сначала пробуем получить XML из output_xml, затем из raw_output для обратной совместимости
        xml_str = job_params.get('output_xml', '') or job_params.get('raw_output', '')
        
        if not xml_str:
            raise FileNotFoundError(f"XML данные результатов не найдены в параметрах задачи {job.id}")

        import xml.etree.ElementTree as ET
        try:
            root = ET.fromstring(xml_str)
        except ET.ParseError as e:
            logger.error(f"[ScanProcessor] Ошибка парсинга XML для задачи {job.id}: {e}")
            logger.error(f"[ScanProcessor] Первые 500 символов XML: {xml_str[:500]}")
            raise ValueError(f"Некорректный формат XML в задаче {job.id}: {e}")
        
        hosts_count = 0
        for host in root.findall('host'):
            status_elem = host.find('status')
            # Если status отсутствует, считаем хост активным (для обратной совместимости)
            if status_elem is not None and status_elem.get('state') != 'up':
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
                            # Извлечение script output
                            scripts_output = []
                            for script_elem in port.findall('script'):
                                script_id = script_elem.get('id', '')
                                script_out = script_elem.get('output', '')
                                scripts_output.append({
                                    'id': script_id,
                                    'output': script_out
                                })
                            
                            # Извлечение SSL информации
                            ssl_subject = None
                            ssl_issuer = None
                            tunnel = service_elem.get('tunnel', '')
                            if tunnel == 'ssl':
                                cert_elem = service_elem.find('cert')
                                if cert_elem is not None:
                                    subject_elem = cert_elem.find('subject')
                                    issuer_elem = cert_elem.find('issuer')
                                    if subject_elem is not None:
                                        ssl_subject = subject_elem.text or ''
                                    if issuer_elem is not None:
                                        ssl_issuer = issuer_elem.text or ''
                            
                            svc_data = {
                                "port": int(port_id),
                                "protocol": protocol,
                                "service": service_elem.get('name', ''),
                                "product": service_elem.get('product', ''),
                                "version": service_elem.get('version', ''),
                                "extrainfo": service_elem.get('extrainfo', ''),
                                "tunnel": tunnel,
                                "scripts": scripts_output,
                                "ssl_subject": ssl_subject,
                                "ssl_issuer": ssl_issuer
                            }
                            services.append(svc_data)

            # Извлечение OS
            os_family = None
            os_match = host.find('os/osmatch')
            if os_match is not None:
                os_family = os_match.get('name', '').split()[0] # Берем первое слово (например, Linux)

            # Обновление или создание актива (без services)
            await self._upsert_asset(ip_addr, {
                "hostname": hostname,
                "open_ports": open_ports,
                "os_family": os_family,
                "group_id": job.scan.group_id,
                "scan_type": "nmap"  # Передаем тип сканирования для обновления временных меток
            })
            
            # Обработка сервисов - создаем/обновляем записи ServiceInventory
            # Нужно получить asset после _upsert_asset
            result = await self.db.execute(select(Asset).where(Asset.ip_address == ip_addr))
            asset = result.scalar_one_or_none()
            if asset and services:
                await self._upsert_services(asset, services)
                logger.debug(f"  - Обновлено сервисов: {len(services)}")
            
            hosts_count += 1

        logger.info(f"Nmap: Обработано {hosts_count} хостов.")

    async def _process_rustscan(self, job: ScanJob, job_params: Dict[str, Any]):
        """Обработка результатов Rustscan из raw_output."""
        raw_output = job_params.get('raw_output', '')
        
        if not raw_output:
            raise ValueError(f"Нет данных raw_output для задачи Rustscan {job.id}")

        # Парсим вывод напрямую из stdout
        import re
        
        hosts_data = {}  # ip -> set of ports
        
        # Парсим raw_output (stdout) - формат: "Open IP:PORT"
        pattern = r"Open\s+([\d\.]+|[\w\.-]+):(\d+)"
        matches = re.findall(pattern, raw_output)
        
        for ip, port in matches:
            if ip not in hosts_data:
                hosts_data[ip] = set()
            try:
                hosts_data[ip].add(int(port))
            except ValueError:
                pass
        
        hosts_count = 0
        for ip, ports in hosts_data.items():
            # Создаем/обновляем актив
            await self._upsert_asset(ip, {
                "open_ports": list(ports),
                "group_id": job.scan.group_id,
                "scan_type": "rustscan"  # Передаем тип сканирования для обновления временных меток
            })
            hosts_count += 1
        
        logger.info(f"Rustscan: Обработано {hosts_count} хостов.")

    async def _process_dig(self, job: ScanJob, job_params: Dict[str, Any]):
        """Обработка результатов Dig из данных задачи."""
        # Получаем DNS записи из параметров задачи
        dns_records = job_params.get('dns_records', [])
        
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
                await self._upsert_asset(ip, {
                    "hostname": rec_name, # Имя из запроса
                    "group_id": job.scan.group_id,
                    "scan_type": "dig"  # Передаем тип сканирования для обновления временных меток
                })
        
        # Обновляем DNS записи у активов
        for ip, recs in dns_by_ip.items():
            result = await self.db.execute(select(Asset).where(Asset.ip_address == ip))
            asset = result.scalar_one_or_none()
            if asset:
                current_dns = asset.dns_records or []
                # Объединяем, избегая дублей (простая логика)
                existing_types = {(r.get('type'), r.get('data')) for r in current_dns}
                new_recs = [r for r in recs if (r.get('type'), r.get('data')) not in existing_types]
                
                if new_recs:
                    asset.dns_records = (current_dns + new_recs)
                    logger.debug(f"Добавлено {len(new_recs)} DNS записей для {ip}")
        
        await self.db.commit()
        logger.info(f"Dig: Обработано {len(dns_records)} записей.")

    async def _upsert_asset(self, ip: str, updates: Dict[str, Any]):
        """Создает или обновляет актив."""
        # Явно загружаем актив со всеми связями чтобы избежать ленивой загрузки
        result = await self.db.execute(
            select(Asset).options(
                selectinload(Asset.groups),
                selectinload(Asset.services)
            ).where(Asset.ip_address == ip)
        )
        asset = result.scalar_one_or_none()
        
        # Определяем активность по наличию открытых портов
        new_open_ports = updates.get('open_ports', [])
        has_open_ports = len(new_open_ports) > 0
        
        # Получаем group_id и scan_type из обновлений
        group_id = updates.get('group_id')
        scan_type = updates.get('scan_type')  # rustscan, nmap, dig
        
        if not asset:
            # Новый актив: статус зависит от наличия открытых портов
            status = 'active' if has_open_ports else 'inactive'
            asset = Asset(ip_address=ip, status=status)
            self.db.add(asset)
            logger.info(f"[SCAN_PROCESS] СОЗДАН НОВЫЙ АКТИВ: IP={ip}, Группа={group_id}, Статус={status}")
            
            # Если указана группа, добавляем связь для нового актива
            if group_id:
                group_result = await self.db.execute(select(Group).where(Group.id == group_id))
                group = group_result.scalar_one_or_none()
                if group:
                    asset.groups.append(group)
                    logger.debug(f"  - Добавлена группа {group.name} для нового актива {ip}")
                else:
                    logger.warning(f"  - Группа с ID {group_id} не найдена для актива {ip}")
        else:
            logger.info(f"[SCAN_PROCESS] ОБНОВЛЕНИЕ АКТИВА: IP={ip}")

        # Применяем обновления
        for key, value in updates.items():
            if value is not None and key != 'group_id' and key != 'scan_type':  # group_id и scan_type обрабатываются отдельно
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
        
        # Обновляем временные метки сканирований в зависимости от типа
        now = datetime.utcnow()
        if scan_type == 'rustscan':
            asset.last_rustscan = now
            # Обновляем rustscan_ports
            if new_open_ports:
                asset.rustscan_ports = new_open_ports
        elif scan_type == 'nmap':
            asset.last_nmap = now
            # Обновляем nmap_ports
            if new_open_ports:
                asset.nmap_ports = new_open_ports
        elif scan_type == 'dig':
            asset.last_dns_scan = now
        
        # Обновляем last_seen для любого типа сканирования
        asset.last_seen = now
        
        # Обновляем статус актива на основе наличия открытых портов
        current_open_ports = asset.open_ports or []
        if len(current_open_ports) > 0:
            asset.status = 'active'
        else:
            asset.status = 'inactive'
        
        # Обновляем группу для существующего актива
        if group_id and asset.id:  # Только для существующих активов (у новых уже добавлено выше)
            # Получаем текущие группы
            current_group_ids = [g.id for g in asset.groups]
            
            # Если группа изменилась, обновляем связь
            if current_group_ids != [group_id]:
                # Очищаем текущие группы
                asset.groups.clear()
                
                # Добавляем новую группу
                group_result = await self.db.execute(select(Group).where(Group.id == group_id))
                group = group_result.scalar_one_or_none()
                if group:
                    asset.groups.append(group)
                    logger.debug(f"  - Обновлена группа на {group.name} для актива {ip}")
                else:
                    logger.warning(f"  - Группа с ID {group_id} не найдена для актива {ip}")
            
        asset.updated_at = now
        
        await self.db.commit()
        logger.info(f"[SCAN_PROCESS] Изменения закоммичены для актива {ip}")

    async def _upsert_services(self, asset: Asset, services_data: List[Dict[str, Any]]):
        """Создает или обновляет сервисы для актива."""
        # Удаляем старые сервисы для этого актива (полная замена)
        asset.services.clear()
        await self.db.flush()  # Применяем удаление перед добавлением новых
        
        for svc in services_data:
            service = ServiceInventory(
                asset_id=asset.id,
                port=svc.get('port'),
                protocol=svc.get('protocol', 'tcp'),
                state=svc.get('state', 'open'),
                service_name=svc.get('service', ''),
                product=svc.get('product', ''),
                version=svc.get('version', ''),
                extra_info=svc.get('extrainfo', ''),
                ostype=svc.get('ostype', ''),
                devicetype=svc.get('devicetype', ''),
                scripts=svc.get('scripts', [])
            )
            # Обработка SSL
            ssl_subject = svc.get('ssl_subject')
            ssl_issuer = svc.get('ssl_issuer')
            if ssl_subject:
                service.ssl_cert_subject = ssl_subject
            if ssl_issuer:
                service.ssl_cert_issuer = ssl_issuer
            
            self.db.add(service)
        
        await self.db.flush()  # Флешим чтобы получить ID и применить изменения
        logger.debug(f"  - Создано/обновлено {len(services_data)} сервисов для {asset.ip_address}")
