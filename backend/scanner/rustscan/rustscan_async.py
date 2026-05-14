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
        
        # Пути к временным файлам
        stdout_file = os.path.join(self.temp_dir, "stdout.txt")
        
        cmd = ["rustscan", "-a", self.target]
        
        if self.ports:
            cmd.extend(["-p", self.ports])
            
        # Add Nmap arguments if scripts are specified
        if self.nmap_scripts and self.nmap_scripts.strip() and self.nmap_scripts.lower() != "none":
            cmd.extend(["--", "nmap", "-sV", "-O", f"--script={self.nmap_scripts}"])
        else:
            # Run without nmap if no scripts specified to avoid auto-triggering
            cmd.extend(["--", "--no-nmap"])
            
        logger.info(f"[RustscanScanner] Запуск команды: {' '.join(cmd)}")
        
        # Открываем файл для записи stdout
        with open(stdout_file, 'w', encoding='utf-8') as stdout_f:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=stdout_f,
                stderr=asyncio.subprocess.PIPE
            )
        
        logger.info(f"[RustscanScanner] Запущен процесс Rustscan для задачи {self.job_id}, PID: {process.pid}")
        
        stderr = await process.stderr.read()
        stderr_str = stderr.decode('utf-8', errors='ignore') if stderr else ""
        
        if stderr_str:
            for line in stderr_str.splitlines():
                logger.debug(f"[Rustscan] {line}")
                
        logger.info(f"[RustscanScanner] Процесс Rustscan завершен с кодом {process.returncode}")
        
        if process.returncode != 0:
            logger.error(f"[RustscanScanner] Rustscan вернул код ошибки {process.returncode}. stderr: {stderr_str}")
        
        # Читаем stdout из временного файла
        stdout_str = ""
        try:
            if os.path.exists(stdout_file):
                with open(stdout_file, 'r', encoding='utf-8', errors='ignore') as f:
                    stdout_str = f.read()
                logger.info(f"[RustscanScanner] Прочитан stdout файл, размер: {len(stdout_str)} байт")
        except Exception as e:
            logger.error(f"[RustscanScanner] Ошибка чтения stdout файла: {e}", exc_info=True)
        
        # Парсим вывод для извлечения данных
        result = self._parse_output(stdout_str, stderr_str)
        
        # Очищаем временную директорию
        try:
            shutil.rmtree(self.temp_dir)
            logger.info(f"[RustscanScanner] Временная директория удалена: {self.temp_dir}")
        except Exception as e:
            logger.warning(f"[RustscanScanner] Не удалось удалить временную директорию: {e}")
        
        # Формируем результат
        return {
            "hostname": result.get("hostname", self.target),
            "ip": result.get("ip", self.target),
            "ports": result.get("ports", []),
            "raw_output": stdout_str + "\n" + stderr_str  # raw из временного файла
        }

    def _parse_output(self, stdout: str, stderr: str) -> Dict[str, Any]:
        result = {
            "hostname": "",
            "ip": "",
            "ports": []
        }
        
        # Очищаем ANSI-коды из вывода
        ansi_escape = re.compile(r'\x1b\[[0-9;]*m')
        clean_stdout = ansi_escape.sub('', stdout)
        
        logger.info(f"[RustscanScanner] Очистка ANSI-кодов: длина до={len(stdout)}, после={len(clean_stdout)}")
        logger.debug(f"[RustscanScanner] Очищенный вывод (первые 500 симв): {clean_stdout[:500]}")
        
        # Parse stdout for "Open IP:PORT" lines
        # Example: Open 1.1.1.1:53
        pattern = r"Open\s+([\d\.]+|[\w\.-]+):(\d+)"
        matches = re.findall(pattern, clean_stdout)
        
        logger.info(f"[RustscanScanner] Найдено совпадений портов: {len(matches)}")
        if matches:
            logger.debug(f"[RustscanScanner] Совпадения: {matches}")
        
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
