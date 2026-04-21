# utils/nmap_xml_importer.py
"""
Утилита для импорта результатов сканирования Nmap из XML-файлов.
Парсит XML-вывод Nmap и обновляет базу данных активами, сервисами и портами.
"""
import xml.etree.ElementTree as ET
import os
from datetime import datetime
from extensions import db
from models import Asset, ServiceInventory, ScanJob, ScanResult, ActivityLog, AssetGroup
from utils import MOSCOW_TZ


class NmapXmlImporter:
    """Класс для импорта и парсинга XML-файлов Nmap"""

    def __init__(self, app):
        self.app = app
        self.imported_count = 0
        self.updated_count = 0
        self.errors = []

    def import_file(self, xml_file_path, job_id=None, group_id=None):
        """
        Импорт XML-файла с результатами сканирования Nmap.

        :param xml_file_path: Путь к XML-файлу
        :param job_id: ID задания сканирования (опционально)
        :param group_id: ID группы для добавления импортированных активов (опционально)
        :return: dict со статистикой импорта
        """
        if not os.path.exists(xml_file_path):
            raise FileNotFoundError(f"XML файл не найден: {xml_file_path}")

        with self.app.app_context():
            try:
                tree = ET.parse(xml_file_path)
                root = tree.getroot()

                # Проверка формата
                if root.tag != 'nmaprun':
                    raise ValueError("Неверный формат XML. Ожидается вывод Nmap.")

                hosts_added = 0
                hosts_updated = 0
                services_added = 0
                services_updated = 0

                for host in root.findall('host'):
                    result = self._process_host(host, job_id)
                    if result:
                        if result['new']:
                            hosts_added += 1
                        else:
                            hosts_updated += 1
                        services_added += result['services_added']
                        services_updated += result['services_updated']

                        # Добавление актива в группу если указано
                        if group_id and result['asset']:
                            self._add_asset_to_group(result['asset'].id, group_id)

                self.imported_count = hosts_added
                self.updated_count = hosts_updated

                # Логирование
                if job_id:
                    self._log_activity(job_id, hosts_added, hosts_updated, services_added, services_updated)

                return {
                    'success': True,
                    'hosts_added': hosts_added,
                    'hosts_updated': hosts_updated,
                    'services_added': services_added,
                    'services_updated': services_updated,
                    'errors': self.errors
                }

            except ET.ParseError as e:
                raise ValueError(f"Ошибка парсинга XML: {e}")

    def _process_host(self, host_elem, job_id=None):
        """Обработка одного хоста из XML"""
        # Статус хоста
        status_elem = host_elem.find('status')
        if status_elem is None or status_elem.get('state') != 'up':
            return None

        # IP адрес
        addr_elem = host_elem.find('address')
        if addr_elem is None:
            self.errors.append("Хост без IP адреса")
            return None

        ip = addr_elem.get('addr')
        addr_type = addr_elem.get('addrtype', 'ipv4')

        # Hostname
        hostname = None
        hostnames = host_elem.find('hostnames')
        if hostnames is not None:
            h_elem = hostnames.find('hostname')
            if h_elem is not None:
                hostname = h_elem.get('name')

        # OS
        os_match = None
        os_accuracy = 0
        os_elem = host_elem.find('os')
        if os_elem is not None:
            os_match_elem = os_elem.find('osmatch')
            if os_match_elem is not None:
                os_match = os_match_elem.get('name')
                try:
                    os_accuracy = int(os_match_elem.get('accuracy', 0))
                except ValueError:
                    pass

        # Создание или обновление актива
        asset = Asset.query.filter_by(ip_address=ip).first()
        is_new = False

        if not asset:
            asset = Asset(
                ip_address=ip,
                hostname=hostname,
                os_family=os_match.split()[0] if os_match else None,
                os_version=' '.join(os_match.split()[1:]) if os_match else None
            )
            db.session.add(asset)
            is_new = True
            db.session.flush()  # Получаем ID
        else:
            # Обновление существующего
            if hostname and not asset.hostname:
                asset.hostname = hostname
            if os_match and (not asset.os_family or os_accuracy > 50):
                asset.os_family = os_match.split()[0]
                asset.os_version = ' '.join(os_match.split()[1:])

        # Порты и сервисы
        ports_elem = host_elem.find('ports')
        services_added = 0
        services_updated = 0

        if ports_elem is not None:
            for port in ports_elem.findall('port'):
                port_result = self._process_port(port, asset, job_id)
                if port_result:
                    if port_result['new']:
                        services_added += 1
                    else:
                        services_updated += 1

        db.session.commit()

        return {
            'new': is_new,
            'asset': asset,
            'services_added': services_added,
            'services_updated': services_updated
        }

    def _process_port(self, port_elem, asset, job_id=None):
        """Обработка одного порта из XML"""
        port_id = port_elem.get('portid')
        protocol = port_elem.get('protocol', 'tcp')

        state_elem = port_elem.find('state')
        state = state_elem.get('state') if state_elem is not None else 'unknown'

        if state != 'open':
            return None

        port_num = int(port_id)

        # Детали сервиса
        service_elem = port_elem.find('service')
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

                    # Парсинг SSL информации из вывода
                    import re
                    subj_match = re.search(r'Subject: (.+?)(?:\n|Issuer:|$)', output)
                    if subj_match:
                        ssl_subject = subj_match.group(1).strip()

                    iss_match = re.search(r'Issuer: (.+?)(?:\n|Validity|$)', output)
                    if iss_match:
                        ssl_issuer = iss_match.group(1).strip()

        # Обновление портов актива
        current_nmap_ports = set(asset.nmap_ports or [])
        current_nmap_ports.add(port_num)
        asset.update_ports('nmap', list(current_nmap_ports))

        # Обновление/Создание сервиса
        service = ServiceInventory.query.filter_by(
            asset_id=asset.id,
            port=port_num,
            protocol=protocol
        ).first()

        is_new = False

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
                discovered_at=datetime.now(MOSCOW_TZ)
            )
            db.session.add(service)
            is_new = True
        else:
            # Обновление существующего
            service.state = 'open'
            if service_name != 'unknown':
                service.service_name = service_name
            if product:
                service.product = product
            if version:
                service.version = version
            if extra_info:
                service.extra_info = extra_info
            if script_output.strip():
                service.script_output = script_output.strip()
            service.last_seen = datetime.now(MOSCOW_TZ)

        return {'new': is_new}

    def _add_asset_to_group(self, asset_id, group_id):
        """Добавление актива в группу"""
        try:
            from models import AssetGroup
            group = AssetGroup.query.get(group_id)
            if group:
                asset = Asset.query.get(asset_id)
                if asset and asset not in group.assets:
                    group.assets.append(asset)
                    db.session.flush()
        except Exception as e:
            self.errors.append(f"Ошибка добавления актива {asset_id} в группу {group_id}: {e}")

    def _log_activity(self, job_id, hosts_added, hosts_updated, services_added, services_updated):
        """Логирование активности импорта"""
        try:
            log = ActivityLog(
                action='nmap_xml_import',
                details={
                    'job_id': job_id,
                    'hosts_added': hosts_added,
                    'hosts_updated': hosts_updated,
                    'services_added': services_added,
                    'services_updated': services_updated
                }
            )
            db.session.add(log)
            db.session.flush()

            # Обновление задания
            job = ScanJob.query.get(job_id)
            if job:
                job.status = 'completed'
                job.progress = 100
                job.completed_at = datetime.now(MOSCOW_TZ)
        except Exception as e:
            self.errors.append(f"Ошибка логирования: {e}")