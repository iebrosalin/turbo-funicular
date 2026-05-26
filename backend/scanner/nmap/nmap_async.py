import asyncio
import logging
import os
import xml.etree.ElementTree as ET
from typing import Dict, Any, List, Optional, Union
from ..base import BaseScanner, ScanResult
from backend.models.target import Target

logger = logging.getLogger(__name__)

class NmapScanner(BaseScanner):
    """Сканер на основе nmap для детального сканирования портов и сервисов"""
    
    SCANNER_NAME = "nmap"
    SUPPORTS_MULTIPLE_TARGETS = True  # Поддерживает списки через -iL
    DEFAULT_TIMEOUT = 600
    
    def __init__(
        self, 
        job_id: int, 
        target: Union[str, Target], 
        ports: Optional[str] = None,
        scripts: Optional[str] = None, 
        version_detect: bool = True,
        os_detect: bool = True,
        custom_args: Optional[str] = None,
        output_dir: Optional[str] = None
    ):
        """
        Инициализация сканера Nmap.
        
        Args:
            job_id: ID задачи сканирования
            target: Цель сканирования (IP, домен или сеть)
            ports: Порты для сканирования (например, "80,443" или "1-1000")
            scripts: NSE скрипты для выполнения
            version_detect: Определять версии сервисов (-sV)
            os_detect: Определять ОС (-O)
            custom_args: Дополнительные аргументы командной строки
            output_dir: Директория для временных файлов
        """
        super().__init__(job_id, target, output_dir)
        self.ports = ports
        self.scripts = scripts
        self.version_detect = version_detect
        self.os_detect = os_detect
        self.custom_args = custom_args

    async def scan(self) -> ScanResult:
        """
        Выполняет сканирование Nmap.
        
        Returns:
            ScanResult: Результаты сканирования с портами, сервисами и ОС
        """
        # Создаем временную директорию через базовый класс
        self._create_temp_dir(prefix=f"nmap_job_{self.job_id}_")
        
        # Пути к временным файлам
        xml_file = os.path.join(self.temp_dir, "output.xml")
        gnmap_file = os.path.join(self.temp_dir, "output.gnmap")
        normal_file = os.path.join(self.temp_dir, "output.txt")
        stdout_file = os.path.join(self.temp_dir, "stdout.txt")
        
        cmd = ["nmap"]
        
        if self.ports:
            cmd.extend(["-p", self.ports])
        else:
            cmd.extend(["-p-", "--top-ports", "1000"]) # Default top 1000 if not specified
            
        # Scripts logic
        if self.scripts and self.scripts.strip() and self.scripts.lower() != "none":
            cmd.extend(["--script", self.scripts])
            
        if self.version_detect:
            cmd.append("-sV")
        if self.os_detect:
            cmd.append("-O")
        
        # Добавляем кастомные аргументы если указаны
        if self.custom_args and self.custom_args.strip():
            # Разбиваем аргументы по пробелам и добавляем каждый отдельно
            custom_args_list = self.custom_args.strip().split()
            cmd.extend(custom_args_list)
            logger.info(f"[{self.__class__.__name__}] Добавлены кастомные аргументы: {self.custom_args}")
            
        # Output to separate files in different formats
        cmd.extend(["-oX", xml_file, "-oG", gnmap_file, "-oN", normal_file])
        
        # Добавляем цели: если target содержит запятые, разделяем их на отдельные аргументы
        # Это позволяет nmap корректно обрабатывать список хостов/IP/CIDR
        if ',' in self.target:
            # Разделяем по запятой и добавляем каждый как отдельный аргумент
            targets = [t.strip() for t in self.target.split(',') if t.strip()]
            cmd.extend(targets)
        else:
            cmd.append(self.target)
        
        logger.info(f"[{self.__class__.__name__}] Запуск команды: {' '.join(cmd)}")
        
        # Открываем файл для записи stdout
        with open(stdout_file, 'w', encoding='utf-8') as stdout_f:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=stdout_f,
                stderr=asyncio.subprocess.PIPE
            )
        
        logger.info(f"[{self.__class__.__name__}] Запущен процесс Nmap для задачи {self.job_id}, PID: {process.pid}")
        
        stderr = await process.stderr.read()
        stderr_str = stderr.decode('utf-8', errors='ignore') if stderr else ""
        
        if stderr_str:
            for line in stderr_str.splitlines():
                logger.debug(f"[Nmap] {line}")
                
        logger.info(f"[{self.__class__.__name__}] Процесс Nmap завершен с кодом {process.returncode}")
        
        if process.returncode != 0:
            logger.error(f"[{self.__class__.__name__}] Nmap вернул код ошибки {process.returncode}. stderr: {stderr_str}")
        
        # Читаем результаты из временных файлов через базовый класс
        xml_output = self._read_file_content(xml_file, "XML")
        gnmap_output = self._read_file_content(gnmap_file, "Grepable")
        normal_output = self._read_file_content(normal_file, "Normal")
        
        # Парсим XML для извлечения данных - теперь получаем список результатов для всех хостов
        all_results = self._parse_output(xml_output)
        
        # Очищаем временную директорию
        self._cleanup_temp_dir()
        
        # Возвращаем первый результат как основной (для обратной совместимости)
        # Но также добавляем список всех результатов для обработки в scan_queue_manager
        if all_results:
            first_result = all_results[0]
            return {
                "hostname": first_result.get("hostname", self.target),
                "ip": first_result.get("ip", self.target),
                "ports": first_result.get("ports", []),
                "os": first_result.get("os", ""),
                "raw_output": normal_output,
                "output_xml": xml_output,
                "output_gnmap": gnmap_output,
                "output_normal": normal_output,
                "all_hosts": all_results  # Добавляем все хосты для последующей обработки
            }
        else:
            return {
                "hostname": self.target,
                "ip": self.target,
                "ports": [],
                "os": "",
                "raw_output": normal_output,
                "output_xml": xml_output,
                "output_gnmap": gnmap_output,
                "output_normal": normal_output,
                "all_hosts": []
            }

    def _parse_output(self, xml_str: str) -> List[ScanResult]:
        """
        Парсит XML вывод Nmap для всех хостов.
        
        Args:
            xml_str: XML строка с результатами сканирования
            
        Returns:
            Список ScanResult: Распарсенные данные для каждого хоста (hostname, ip, ports, os)
        """
        results: List[ScanResult] = []
        
        # Parse XML from string
        try:
            root = ET.fromstring(xml_str)
            
            # Находим все элементы host
            hosts = root.findall('host')
            for host in hosts:
                result: ScanResult = {
                    "hostname": "",
                    "ip": "",
                    "ports": [],
                    "os": ""
                }
                
                # Get IP and Hostname
                addr = host.find('address')
                if addr is not None:
                    result["ip"] = addr.get('addr', '')
                
                hostname_elem = host.find('hostnames/host')
                if hostname_elem is not None:
                    result["hostname"] = hostname_elem.get('name', '')
                
                # Get Ports
                ports_elem = host.find('ports')
                if ports_elem is not None:
                    for port in ports_elem.findall('port'):
                        state = port.find('state')
                        if state is not None and state.get('state') == 'open':
                            port_id = port.get('portid')
                            protocol = port.get('protocol')
                            service = port.find('service')
                            service_name = service.get('name', '') if service is not None else ''
                            product = service.get('product', '') if service is not None else ''
                            version = service.get('version', '') if service is not None else ''
                            extra_info = service.get('extrainfo', '') if service is not None else ''
                            
                            # Извлечение script output
                            scripts_output = []
                            for script_elem in port.findall('script'):
                                script_id = script_elem.get('id', '')
                                script_output = script_elem.get('output', '')
                                scripts_output.append({
                                    'id': script_id,
                                    'output': script_output
                                })
                            
                            # Извлечение SSL информации
                            ssl_subject = None
                            ssl_issuer = None
                            if service is not None:
                                tunnel = service.get('tunnel', '')
                                if tunnel == 'ssl':
                                    # Пытаемся получить SSL cert из service elem
                                    cert_elem = service.find('cert')
                                    if cert_elem is not None:
                                        subject_elem = cert_elem.find('subject')
                                        issuer_elem = cert_elem.find('issuer')
                                        if subject_elem is not None:
                                            ssl_subject = subject_elem.text or ''
                                        if issuer_elem is not None:
                                            ssl_issuer = issuer_elem.text or ''
                            
                            port_data = {
                                "port": int(port_id),
                                "protocol": protocol,
                                "service": service_name,
                                "product": product,
                                "version": version,
                                "extra_info": extra_info,
                                "script_output": scripts_output,
                                "ssl_subject": ssl_subject,
                                "ssl_issuer": ssl_issuer
                            }
                            result["ports"].append(port_data)
                
                # Get OS
                osmatch = host.find('os/osmatch')
                if osmatch is not None:
                    result["os"] = osmatch.get('name', '')
                
                # Добавляем результат только если найден IP
                if result["ip"]:
                    results.append(result)
                        
        except Exception as e:
            logger.error(f"[NmapScanner] Ошибка парсинга XML: {e}")
        
        return results
