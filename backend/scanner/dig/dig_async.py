import asyncio
import logging
import os
import re
from typing import Dict, Any, List, Optional
from ..base import BaseScanner

logger = logging.getLogger(__name__)

class DigScanner(BaseScanner):
    def __init__(self, job_id: int, target: str, record_types: Optional[List[str]] = None, 
                 output_dir: str = "/app/scanner_output"):
        super().__init__(job_id, output_dir)
        self.target = target
        # Default types if not specified
        self.record_types = record_types or ["A", "AAAA", "MX", "NS", "TXT", "CNAME", "SOA"]
        self.raw_file = os.path.join(self.job_output_dir, "dig.txt")
        self.json_file = os.path.join(self.job_output_dir, "dig.json")

    async def scan(self) -> Dict[str, Any]:
        cmd = ["dig"]
        
        # Add record types
        for rtype in self.record_types:
            cmd.append(rtype)
            
        cmd.append(self.target)
        cmd.append("+noall")
        cmd.append("+answer")
        cmd.append("+authority")
        cmd.append("+additional")
        
        logger.info(f"[DigScanner] Запуск команды: {' '.join(cmd)}")
        
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        logger.info(f"[DigScanner] Запущен процесс Dig для задачи {self.job_id}, PID: {process.pid}")
        
        stdout, stderr = await process.communicate()
        
        stdout_str = stdout.decode('utf-8', errors='ignore')
        stderr_str = stderr.decode('utf-8', errors='ignore')
        
        if stdout_str:
            for line in stdout_str.splitlines():
                logger.debug(f"[Dig] {line}")
        if stderr_str:
            for line in stderr_str.splitlines():
                logger.debug(f"[Dig] {line}")
                
        logger.info(f"[DigScanner] Процесс Dig завершен с кодом {process.returncode}")
        
        # Save raw output
        with open(self.raw_file, 'w') as f:
            f.write(stdout_str)
            if stderr_str:
                f.write("\nSTDERR:\n")
                f.write(stderr_str)
        
        result = self._parse_output(stdout_str)
        
        # Save JSON result
        import json
        with open(self.json_file, 'w') as f:
            json.dump(result.get("records", []), f, indent=2)
            
        return {
            "hostname": self.target,
            "ip": "", # Dig doesn't necessarily resolve the IP of the target itself in the same way
            "ports": [],
            "dns_records": result.get("records", []),
            "raw_output": stdout_str + "\n" + stderr_str
        }

    def _parse_output(self, output: str) -> Dict[str, Any]:
        records = []
        lines = output.strip().split('\n')
        
        for line in lines:
            line = line.strip()
            if not line or line.startswith(';'):
                continue
            
            parts = line.split()
            if len(parts) >= 5:
                # Format: name ttl class type data
                name = parts[0]
                # ttl = parts[1] # Often not needed for basic storage
                # rclass = parts[2] # Usually IN
                rtype = parts[3]
                data = " ".join(parts[4:])
                
                records.append({
                    "name": name.rstrip('.'),
                    "type": rtype,
                    "data": data.rstrip('.')
                })
        
        return {"records": records}
