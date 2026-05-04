import asyncio
import os
import re
import json
from typing import Dict, Any, List, Optional
from ..base import BaseScanner
from backend.core.logging_config import get_logger

logger = get_logger(__name__)

class RustscanScanner(BaseScanner):
    def __init__(self, job_id: int, target: str, ports: Optional[str] = None, 
                 nmap_scripts: Optional[str] = None, output_dir: str = "/app/scanner_output"):
        super().__init__(job_id, output_dir)
        self.target = target
        self.ports = ports
        self.nmap_scripts = nmap_scripts
        self.raw_file = os.path.join(self.job_output_dir, "rustscan.txt")
        self.grepable_file = os.path.join(self.job_output_dir, "rustscan_grepable.txt")
        self.json_file = os.path.join(self.job_output_dir, "rustscan.json")

    async def scan(self) -> Dict[str, Any]:
        cmd = ["rustscan", "-a", self.target]
        
        if self.ports:
            cmd.extend(["-p", self.ports])
            
        # Add greppable output to file
        cmd.extend(["--greppable", self.grepable_file])
        
        # Add Nmap arguments if scripts are specified
        if self.nmap_scripts and self.nmap_scripts.strip() and self.nmap_scripts.lower() != "none":
            cmd.extend(["--", "nmap", "-sV", "-O", f"--script={self.nmap_scripts}"])
        else:
            # Run without nmap if no scripts specified to avoid auto-triggering
            cmd.append("--no-nmap")
            
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
        
        # Save raw output
        with open(self.raw_file, 'w') as f:
            f.write(stdout_str)
            if stderr_str:
                f.write("\nSTDERR:\n")
                f.write(stderr_str)
        
        result = self._parse_output(stdout_str, stderr_str)
        
        # Save JSON result (parsed structure)
        with open(self.json_file, 'w') as f:
            json.dump(result, f, indent=2)
            
        return {
            "hostname": result.get("hostname", self.target),
            "ip": result.get("ip", self.target),
            "ports": result.get("ports", []),
            "raw_output": stdout_str + "\n" + stderr_str
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
        
        # If no IP found in "Open" lines, try to find it elsewhere or use target
        if not result["ip"]:
            # Try to extract from grepable file if exists
            if os.path.exists(self.grepable_file):
                with open(self.grepable_file, 'r') as f:
                    content = f.read()
                    # Grepable format: Host: IP Ports: Port1,Port2...
                    g_pattern = r"Host:\s*([\d\.]+|[\w\.-]+).*?Ports:\s*([\d,]+)"
                    g_match = re.search(g_pattern, content)
                    if g_match:
                        result["ip"] = g_match.group(1)
                        ports_str = g_match.group(2)
                        for p in ports_str.split(','):
                            if p.strip():
                                try:
                                    result["ports"].append(int(p.strip()))
                                except ValueError:
                                    pass
        
        if not result["ip"]:
            result["ip"] = self.target
            
        # Remove duplicates and sort
        result["ports"] = sorted(list(set(result["ports"])))
        
        return result
