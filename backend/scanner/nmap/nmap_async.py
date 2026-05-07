import asyncio
import logging
import os
import tempfile
import shutil
import xml.etree.ElementTree as ET
from typing import Dict, Any, List, Optional
from ..base import BaseScanner

logger = logging.getLogger(__name__)

class NmapScanner(BaseScanner):
    def __init__(self, job_id: int, target: str, ports: Optional[str] = None, 
                 scripts: Optional[str] = None, version_detect: bool = True, 
                 os_detect: bool = True, output_dir: Optional[str] = None):
        # Используем переменную окружения или значение по умолчанию
        if output_dir is None:
            output_dir = os.getenv('SCANNER_OUTPUT_DIR', '/app/scanner_output')
        super().__init__(job_id, output_dir)
        self.target = target
        self.ports = ports
        self.scripts = scripts
        self.version_detect = version_detect
        self.os_detect = os_detect
        # Создаем временную директорию для файлов результатов
        self.temp_dir = None

    async def scan(self) -> Dict[str, Any]:
        # Создаем временную директорию для хранения файлов результатов
        self.temp_dir = tempfile.mkdtemp(prefix=f"nmap_job_{self.job_id}_")
        logger.info(f"[NmapScanner] Создана временная директория: {self.temp_dir}")
        
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
            
        # Output to separate files in different formats
        cmd.extend(["-oX", xml_file, "-oG", gnmap_file, "-oN", normal_file])
        
        cmd.append(self.target)
        
        logger.info(f"[NmapScanner] Запуск команды: {' '.join(cmd)}")
        
        # Открываем файл для записи stdout
        with open(stdout_file, 'w', encoding='utf-8') as stdout_f:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=stdout_f,
                stderr=asyncio.subprocess.PIPE
            )
        
        logger.info(f"[NmapScanner] Запущен процесс Nmap для задачи {self.job_id}, PID: {process.pid}")
        
        stderr = await process.stderr.read()
        stderr_str = stderr.decode('utf-8', errors='ignore') if stderr else ""
        
        if stderr_str:
            for line in stderr_str.splitlines():
                logger.debug(f"[Nmap] {line}")
                
        logger.info(f"[NmapScanner] Процесс Nmap завершен с кодом {process.returncode}")
        
        if process.returncode != 0:
            logger.error(f"[NmapScanner] Nmap вернул код ошибки {process.returncode}. stderr: {stderr_str}")
        
        # Читаем результаты из временных файлов
        xml_output = ""
        gnmap_output = ""
        normal_output = ""
        stdout_output = ""
        
        # Проверяем существование и размер файлов
        for f_path, f_name in [(xml_file, "XML"), (gnmap_file, "Grepable"), (normal_file, "Normal"), (stdout_file, "Stdout")]:
            if os.path.exists(f_path):
                file_size = os.path.getsize(f_path)
                logger.info(f"[NmapScanner] Файл {f_name} существует, размер: {file_size} байт")
                if file_size == 0:
                    logger.warning(f"[NmapScanner] Файл {f_name} пустой!")
            else:
                logger.error(f"[NmapScanner] Файл {f_name} не найден по пути {f_path}")
        
        try:
            if os.path.exists(xml_file):
                with open(xml_file, 'r', encoding='utf-8', errors='ignore') as f:
                    xml_output = f.read()
                logger.info(f"[NmapScanner] Прочитан XML файл, размер: {len(xml_output)} байт")
                if not xml_output.strip():
                    logger.error("[NmapScanner] XML файл прочитан, но содержимое пустое!")
            
            if os.path.exists(gnmap_file):
                with open(gnmap_file, 'r', encoding='utf-8', errors='ignore') as f:
                    gnmap_output = f.read()
                    logger.info(f"[NmapScanner] Прочитан Grepable файл, размер: {len(gnmap_output)} байт")
                    
            if os.path.exists(normal_file):
                with open(normal_file, 'r', encoding='utf-8', errors='ignore') as f:
                    normal_output = f.read()
                    logger.info(f"[NmapScanner] Прочитан Normal файл, размер: {len(normal_output)} байт")
            
            if os.path.exists(stdout_file):
                with open(stdout_file, 'r', encoding='utf-8', errors='ignore') as f:
                    stdout_output = f.read()
                    logger.info(f"[NmapScanner] Прочитан Stdout файл, размер: {len(stdout_output)} байт")
        except Exception as e:
            logger.error(f"[NmapScanner] Ошибка чтения файлов результатов: {e}", exc_info=True)
            raise
        
        # Парсим XML для извлечения данных
        result = self._parse_output(xml_output)
        
        # Очищаем временную директорию
        try:
            shutil.rmtree(self.temp_dir)
            logger.info(f"[NmapScanner] Временная директория удалена: {self.temp_dir}")
        except Exception as e:
            logger.warning(f"[NmapScanner] Не удалось удалить временную директорию: {e}")
        
        return {
            "hostname": result.get("hostname", self.target),
            "ip": result.get("ip", self.target),
            "ports": result.get("ports", []),
            "os": result.get("os", ""),
            "raw_output": normal_output,  # raw = normal format из файла
            "output_xml": xml_output,
            "output_gnmap": gnmap_output,
            "output_normal": normal_output
        }

    def _parse_output(self, xml_str: str) -> Dict[str, Any]:
        result = {
            "hostname": "",
            "ip": "",
            "ports": [],
            "os": ""
        }
        
        # Parse XML from string
        try:
            root = ET.fromstring(xml_str)
            
            host = root.find('host')
            if host is not None:
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
                            
                            result["ports"].append({
                                "port": int(port_id),
                                "protocol": protocol,
                                "service": service_name,
                                "product": product,
                                "version": version
                            })
                
                # Get OS
                osmatch = host.find('os/osmatch')
                if osmatch is not None:
                    result["os"] = osmatch.get('name', '')
                        
        except Exception as e:
            logger.error(f"[NmapScanner] Ошибка парсинга XML: {e}")
        
        return result
