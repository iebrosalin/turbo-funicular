"""
Nmap XML Importer - Импорт результатов сканирования Nmap из XML.
"""
import xml.etree.ElementTree as ET
from typing import List, Dict, Any, Optional
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
import logging

logger = logging.getLogger(__name__)


class NmapXmlImporter:
    """Класс для импорта результатов Nmap из XML файлов."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def parse_file(self, file_path: str) -> List[Dict[str, Any]]:
        """
        Распарсить XML файл Nmap и вернуть список хостов.
        
        Args:
            file_path: Путь к XML файлу
        
        Returns:
            Список словарей с данными о хостах
        """
        try:
            tree = ET.parse(file_path)
            root = tree.getroot()
            
            hosts = []
            for host in root.findall('host'):
                host_data = self._parse_host(host)
                if host_data:
                    hosts.append(host_data)
            
            logger.info(f"Распарсено {len(hosts)} хостов из {file_path}")
            return hosts
            
        except ET.ParseError as e:
            logger.error(f"Ошибка парсинга XML: {e}")
            raise
        except Exception as e:
            logger.error(f"Ошибка при чтении файла: {e}")
            raise
    
    def _parse_host(self, host_elem: ET.Element) -> Optional[Dict[str, Any]]:
        """Распарсить элемент хоста."""
        # IP адрес
        addr_elem = host_elem.find('address')
        if addr_elem is None or addr_elem.get('addrtype') != 'ipv4':
            return None
        
        ip_address = addr_elem.get('addr')
        
        # Имя хоста
        hostname_elem = host_elem.find('hostnames/hostname')
        hostname = hostname_elem.get('name') if hostname_elem is not None else None
        
        # Статус
        status_elem = host_elem.find('status')
        status = status_elem.get('state', 'unknown') if status_elem is not None else 'unknown'
        
        # OS информация
        os_match = None
        os_accuracy = 0
        os_elem = host_elem.find('os/osmatch')
        if os_elem is not None:
            os_match = os_elem.get('name')
            os_accuracy = int(os_elem.get('accuracy', 0))
        
        # Порты
        ports = []
        services = []
        ports_elem = host_elem.find('ports')
        if ports_elem is not None:
            for port in ports_elem.findall('port'):
                port_id = port.get('portid')
                protocol = port.get('protocol')
                
                state_elem = port.find('state')
                state = state_elem.get('state', 'unknown') if state_elem is not None else 'unknown'
                
                if state == 'open':
                    ports.append(int(port_id))
                    
                    # Информация о сервисе
                    service_elem = port.find('service')
                    if service_elem is not None:
                        service_info = {
                            'port': int(port_id),
                            'protocol': protocol,
                            'product': service_elem.get('product', ''),
                            'version': service_elem.get('version', ''),
                            'extrainfo': service_elem.get('extrainfo', ''),
                            'method': service_elem.get('method', ''),
                            'conf': service_elem.get('conf', '0'),
                            'tunnel': service_elem.get('tunnel', ''),
                        }
                        
                        # SSL информация
                        ssl_elem = service_elem.find('script[@id="ssl-cert"]')
                        if ssl_elem is not None:
                            output = ssl_elem.get('output', '')
                            service_info['ssl_cert'] = output
                        
                        services.append(service_info)
        
        # Скрипты NSE
        scripts = []
        hostscripts_elem = host_elem.find('hostscript')
        if hostscripts_elem is not None:
            for script in hostscripts_elem.findall('script'):
                scripts.append({
                    'id': script.get('id'),
                    'output': script.get('output', '')
                })
        
        return {
            'ip_address': ip_address,
            'hostname': hostname,
            'status': status,
            'os_match': os_match,
            'os_accuracy': os_accuracy,
            'ports': ports,
            'services': services,
            'scripts': scripts,
            'raw_xml': ET.tostring(host_elem, encoding='unicode')
        }
    
    async def import_to_db(
        self,
        hosts_data: List[Dict[str, Any]],
        group_id: Optional[int] = None,
        scan_id: Optional[int] = None
    ) -> int:
        """
        Импортировать данные хостов в базу данных.
        
        Args:
            hosts_data: Список данных о хостах
            group_id: ID группы для назначения активов
            scan_id: ID сканирования для связи результатов
        
        Returns:
            Количество импортированных хостов
        """
        from backend.models.asset import Asset
        from backend.models.scan import ScanResult
        from utils import create_asset_if_not_exists, get_moscow_time
        
        imported_count = 0
        
        for host_data in hosts_data:
            # Создаём или получаем актив
            asset = await create_asset_if_not_exists(
                db=self.db,
                ip_address=host_data['ip_address'],
                hostname=host_data.get('hostname'),
                group_id=group_id
            )
            
            # Обновляем информацию об ОС
            if host_data.get('os_match'):
                asset.os_family = self._extract_os_family(host_data['os_match'])
                asset.os_version = host_data['os_match']
            
            # Обновляем порты
            if host_data.get('ports'):
                asset.update_ports(host_data['ports'], scan_type='nmap')
            
            # Сохраняем результат сканирования
            if scan_id:
                result = ScanResult(
                    scan_id=scan_id,
                    asset_ip=asset.ip_address,
                    hostname=asset.hostname,
                    os_match=host_data.get('os_match'),
                    os_accuracy=host_data.get('os_accuracy'),
                    ports=host_data.get('ports', []),
                    raw_output=host_data.get('raw_xml', ''),
                    scanned_at=get_moscow_time()
                )
                self.db.add(result)
            
            imported_count += 1
        
        await self.db.commit()
        logger.info(f"Импортировано {imported_count} хостов в БД")
        return imported_count
    
    def _extract_os_family(self, os_match: str) -> str:
        """Извлечь семейство ОС из строки os_match."""
        os_lower = os_match.lower()
        
        if 'windows' in os_lower:
            return 'windows'
        elif 'linux' in os_lower:
            return 'linux'
        elif 'freebsd' in os_lower or 'openbsd' in os_lower:
            return 'bsd'
        elif 'mac' in os_lower or 'darwin' in os_lower:
            return 'macos'
        elif 'ios' in os_lower:
            return 'ios'
        elif 'android' in os_lower:
            return 'android'
        else:
            return 'unknown'
    
    async def import_file(
        self,
        file_path: str,
        group_id: Optional[int] = None,
        scan_id: Optional[int] = None
    ) -> int:
        """
        Импортировать XML файл напрямую.
        
        Args:
            file_path: Путь к XML файлу
            group_id: ID группы для назначения активов
            scan_id: ID сканирования для связи результатов
        
        Returns:
            Количество импортированных хостов
        """
        hosts_data = await self.parse_file(file_path)
        return await self.import_to_db(hosts_data, group_id, scan_id)
