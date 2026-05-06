import asyncio
import logging
import os
import re
import json
from typing import Dict, Any, List, Optional
from ..base import BaseScanner

logger = logging.getLogger(__name__)

class RustscanScanner(BaseScanner):
    def __init__(self, job_id: int, target: str, ports: Optional[str] = None, 
                 nmap_scripts: Optional[str] = None, output_dir: Optional[str] = None):
        # Используем переменную окружения или значение по умолчанию
        if output_dir is None:
            output_dir = os.getenv('SCANNER_OUTPUT_DIR', '/app/scanner_output')
        super().__init__(job_id, output_dir)
        self.target = target
        self.ports = ports
        self.nmap_scripts = nmap_scripts

    async def scan(self) -> Dict[str, Any]:
        cmd = ["rustscan", "-a", self.target]
        
        if self.ports:
            cmd.extend(["-p", self.ports])
        
        # Add greppable flag for parsing
        cmd.append("-g")
            
        # Add Nmap arguments if scripts are specified
        if self.nmap_scripts and self.nmap_scripts.strip() and self.nmap_scripts.lower() != "none":
            cmd.extend(["--", "nmap", "-sV", "-O", f"--script={self.nmap_scripts}"])
        else:
            # Run without nmap if no scripts specified to avoid auto-triggering
            cmd.extend(["--", "--no-nmap"])
            
        logger.info(f"[RustscanScanner] Запуск команды: {' '.join(cmd)}")
        
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        logger.info(f"[RustscanScanner] Запущен процесс Rustscan для задачи {self.job_id}, PID: {process.pid}")
        
        stdout, stderr = await process.communicate()
        
        stdout_str = stdout.decode('utf-8', errors='ignore')
        stderr_str = stderr.decode('utf-8', errors='ignore')
        
        if stdout_str:
            for line in stdout_str.splitlines():
                logger.debug(f"[Rustscan] {line}")
        if stderr_str:
            for line in stderr_str.splitlines():
                logger.debug(f"[Rustscan] {line}")
                
        logger.info(f"[RustscanScanner] Процесс Rustscan завершен с кодом {process.returncode}")
        
        result = self._parse_output(stdout_str, stderr_str)
        
        # Формируем JSON формат для rustscan
        json_output = {
            "target": self.target,
            "ip": result.get("ip", self.target),
            "hostname": result.get("hostname", ""),
            "ports": result.get("ports", []),
            "raw_output": stdout_str + "\n" + stderr_str
        }
            
        return {
            "hostname": result.get("hostname", self.target),
            "ip": result.get("ip", self.target),
            "ports": result.get("ports", []),
            "raw_output": stdout_str + "\n" + stderr_str,
            "output_json": json_output
        }

    def _parse_output(self, stdout: str, stderr: str) -> Dict[str, Any]:
        result = {
            "hostname": "",
            "ip": "",
            "ports": []
        }
        
        # Parse stdout for "Open IP:PORT" lines
        # Example: Open 1.1.1.1:53
        pattern = r"Open\s+([\d\.]+|[\w\.-]+):(\d+)"
        matches = re.findall(pattern, stdout)
        
        seen_ips = set()
        for ip, port in matches:
            if ip not in seen_ips:
                result["ip"] = ip
                seen_ips.add(ip)
            try:
                result["ports"].append(int(port))
            except ValueError:
                pass
        
        if not result["ip"]:
            result["ip"] = self.target
            
        # Remove duplicates and sort
        result["ports"] = sorted(list(set(result["ports"])))
        
        return result
