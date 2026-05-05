import asyncio
import logging
import os
import re
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
        self.xml_file = os.path.join(self.job_output_dir, "nmap.xml")

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
            
        # Output formats
        cmd.extend(["-oX", self.xml_file])
        cmd.extend(["-oN", os.path.join(self.job_output_dir, "nmap.nmap")])
        cmd.extend(["-oG", os.path.join(self.job_output_dir, "nmap.gnmap")])
        
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
        
        # Save raw output
        raw_file = os.path.join(self.job_output_dir, "nmap.txt")
        with open(raw_file, 'w') as f:
            f.write(stdout_str)
            if stderr_str:
                f.write("\nSTDERR:\n")
                f.write(stderr_str)
                
        result = self._parse_output()
        return {
            "hostname": result.get("hostname", self.target),
            "ip": result.get("ip", self.target),
            "ports": result.get("ports", []),
            "os": result.get("os", ""),
            "raw_output": stdout_str + "\n" + stderr_str
        }

    def _parse_output(self) -> Dict[str, Any]:
        result = {
            "hostname": "",
            "ip": "",
            "ports": [],
            "os": ""
        }
        
        # Parse XML for reliable data
        if os.path.exists(self.xml_file):
            try:
                tree = ET.parse(self.xml_file)
                root = tree.getroot()
                
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
