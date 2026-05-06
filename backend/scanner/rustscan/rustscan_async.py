import asyncio
import logging
import os
import tempfile
import shutil
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
        # Создаем временную директорию для файлов результатов
        self.temp_dir = None

    async def scan(self) -> Dict[str, Any]:
        # Создаем временную директорию для хранения файлов результатов
        self.temp_dir = tempfile.mkdtemp(prefix=f"rustscan_job_{self.job_id}_")
        logger.info(f"[RustscanScanner] Создана временная директория: {self.temp_dir}")
        
        cmd = ["rustscan", "-a", self.target]
        
        if self.ports:
            cmd.extend(["-p", self.ports])
        
        # Rustscan не поддерживает вывод в файл через -g, он только включает greppable формат в stdout
        # Поэтому мы просто включаем greppable вывод и будем парсить stdout
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
        
        if process.returncode != 0:
            logger.error(f"[RustscanScanner] Rustscan вернул код ошибки {process.returncode}. stderr: {stderr_str}")
        
        # Сохраняем greppable вывод во временный файл для последующего чтения
        greppable_file = os.path.join(self.temp_dir, "output.gnmap")
        greppable_output = ""
        try:
            # Парсим stdout для извлечения greppable строк (формат: IP PORT1,PORT2,PORT3)
            # Rustscan с флагом -g выводит строки вида: "127.0.0.1 80,443,8080"
            greppable_lines = []
            for line in stdout_str.splitlines():
                line = line.strip()
                # Проверяем формат greppable: IP адрес followed by пробел и порты через запятую
                if re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\s+\d+(,\d+)*$', line):
                    greppable_lines.append(line)
                elif re.match(r'^[a-zA-Z0-9.-]+\s+\d+(,\d+)*$', line) and not line.startswith('Open'):
                    # Также проверяем hostname формат
                    parts = line.split()
                    if len(parts) == 2 and ',' in parts[1]:
                        greppable_lines.append(line)
            
            greppable_output = '\n'.join(greppable_lines)
            
            # Сохраняем в файл
            with open(greppable_file, 'w', encoding='utf-8') as f:
                f.write(greppable_output)
            
            logger.info(f"[RustscanScanner] Greppable данные извлечены из stdout, размер: {len(greppable_output)} байт")
            if greppable_lines:
                logger.info(f"[RustscanScanner] Найдено {len(greppable_lines)} строк в greppable формате")
        except Exception as e:
            logger.error(f"[RustscanScanner] Ошибка обработки greppable вывода: {e}", exc_info=True)
        
        # Парсим вывод для извлечения данных
        result = self._parse_output(stdout_str, stderr_str, greppable_output)
        
        # Очищаем временную директорию
        try:
            shutil.rmtree(self.temp_dir)
            logger.info(f"[RustscanScanner] Временная директория удалена: {self.temp_dir}")
        except Exception as e:
            logger.warning(f"[RustscanScanner] Не удалось удалить временную директорию: {e}")
        
        # Формируем JSON формат для rustscan
        json_output = {
            "target": self.target,
            "ip": result.get("ip", self.target),
            "hostname": result.get("hostname", ""),
            "ports": result.get("ports", []),
            "raw_output": stdout_str + "\n" + stderr_str,
            "greppable_output": greppable_output
        }
            
        return {
            "hostname": result.get("hostname", self.target),
            "ip": result.get("ip", self.target),
            "ports": result.get("ports", []),
            "raw_output": stdout_str + "\n" + stderr_str,
            "output_json": json_output,
            "output_gnmap": greppable_output
        }

    def _parse_output(self, stdout: str, stderr: str, greppable: str) -> Dict[str, Any]:
        result = {
            "hostname": "",
            "ip": "",
            "ports": []
        }
        
        # Сначала пробуем парсить greppable формат (более надежный)
        # Пример: "127.0.0.1 80,443,8080"
        if greppable:
            for line in greppable.splitlines():
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                # Формат: IP PORT1,PORT2,PORT3
                parts = line.split()
                if len(parts) >= 2:
                    ip = parts[0]
                    if not result["ip"]:
                        result["ip"] = ip
                    # Парсим порты
                    port_str = parts[1]
                    for port in port_str.split(','):
                        try:
                            result["ports"].append(int(port))
                        except ValueError:
                            pass
        
        # Если greppable пустой, парсим stdout
        if not result["ports"]:
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
