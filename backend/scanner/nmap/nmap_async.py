import asyncio
import logging
import os
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

    async def scan(self) -> Dict[str, Any]:
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
            
        # Output to stdout in multiple formats
        cmd.extend(["-oX", "-", "-oG", "-", "-oN", "-"])  # XML, Grepable, Normal to stdout
        
        cmd.append(self.target)
        
        logger.info(f"[NmapScanner] Запуск команды: {' '.join(cmd)}")
        
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        logger.info(f"[NmapScanner] Запущен процесс Nmap для задачи {self.job_id}, PID: {process.pid}")
        
        stdout, stderr = await process.communicate()
        
        stdout_str = stdout.decode('utf-8', errors='ignore')
        stderr_str = stderr.decode('utf-8', errors='ignore')
        
        if stdout_str:
            for line in stdout_str.splitlines():
                logger.debug(f"[Nmap] {line}")
        if stderr_str:
            for line in stderr_str.splitlines():
                logger.debug(f"[Nmap] {line}")
                
        logger.info(f"[NmapScanner] Процесс Nmap завершен с кодом {process.returncode}")
                
        result = self._parse_output(stdout_str)
        
        # Разделяем вывод на форматы (XML, GNMAP, Normal)
        # Nmap выводит последовательно: сначала XML, потом Grepable, потом Normal
        # Нужно разделить их
        xml_output, gnmap_output, normal_output = self._split_nmap_output(stdout_str)
        
        return {
            "hostname": result.get("hostname", self.target),
            "ip": result.get("ip", self.target),
            "ports": result.get("ports", []),
            "os": result.get("os", ""),
            "raw_output": normal_output,  # raw = normal format
            "output_xml": xml_output,
            "output_gnmap": gnmap_output,
            "output_normal": normal_output
        }
    
    def _split_nmap_output(self, output: str) -> tuple:
        """Разделяет комбинированный вывод nmap на отдельные форматы."""
        # Nmap выводит форматы последовательно: XML, затем Grepable, затем Normal
        # Проблема: внутри XML тегов могут быть вставлены текстовые строки из normal вывода
        
        xml_lines = []
        gnmap_lines = []
        normal_lines = []
        
        current_format = None
        in_xml = False
        
        for line in output.split('\n'):
            stripped = line.strip()
            
            # Начало XML блока
            if line.startswith('<?xml') or line.startswith('<!DOCTYPE'):
                current_format = 'xml'
                in_xml = True
                xml_lines.append(line)
            elif in_xml:
                # Пропускаем текстовые строки внутри XML (не начинающиеся с < или # или <!--)
                # Это строки вида "Nmap scan report for...", "Host is up...", "PORT STATE..." и т.д.
                if stripped and not stripped.startswith('<') and not stripped.startswith('#') and not stripped.startswith('<!--'):
                    # Это текстовая строка, вставленная в XML - пропускаем её
                    continue
                xml_lines.append(line)
                # Конец XML блока
                if stripped == '</nmaprun>':
                    in_xml = False
                    current_format = None
            # Начало Grepable блока
            elif line.startswith('# Nmap') and 'grepable' in line.lower():
                current_format = 'gnmap'
                gnmap_lines.append(line)
            elif current_format == 'gnmap':
                # Конец Grepable, начало Normal
                if line.startswith('# Nmap') and 'normal' in line.lower():
                    current_format = 'normal'
                    normal_lines.append(line)
                else:
                    gnmap_lines.append(line)
            # Начало Normal блока
            elif line.startswith('# Nmap') and 'normal' in line.lower():
                current_format = 'normal'
                normal_lines.append(line)
            elif current_format == 'normal':
                normal_lines.append(line)
            # Игнорируем всё остальное
        
        return '\n'.join(xml_lines), '\n'.join(gnmap_lines), '\n'.join(normal_lines)

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
