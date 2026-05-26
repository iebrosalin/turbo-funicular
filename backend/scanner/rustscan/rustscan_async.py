import asyncio
import logging
import os
import re
from typing import Dict, Any, List, Optional, Union
from ..base import BaseScanner, ScanResult
from backend.models.target import Target

logger = logging.getLogger(__name__)

class RustscanScanner(BaseScanner):
    """Сканер на основе rustscan для быстрого сканирования портов"""
    
    SCANNER_NAME = "rustscan"
    SUPPORTS_MULTIPLE_TARGETS = False  # Только один target за раз
    DEFAULT_TIMEOUT = 300
    
    def __init__(
        self, 
        job_id: int, 
        target: Union[str, Target], 
        ports: Optional[str] = None,
        nmap_scripts: Optional[str] = None,
        custom_args: Optional[str] = None, 
        output_dir: Optional[str] = None
    ):
        """
        Инициализация сканера Rustscan.
        
        Args:
            job_id: ID задачи сканирования
            target: Цель сканирования (IP или домен)
            ports: Порты для сканирования
            nmap_scripts: NSE скрипты для выполнения после сканирования
            custom_args: Дополнительные аргументы командной строки
            output_dir: Директория для временных файлов
        """
        super().__init__(job_id, target, output_dir)
        self.ports = ports
        self.nmap_scripts = nmap_scripts
        self.custom_args = custom_args

    async def scan(self) -> ScanResult:
        """
        Выполняет сканирование Rustscan.
        
        Returns:
            ScanResult: Результаты сканирования с открытыми портами
        """
        # Создаем временную директорию через базовый класс
        self._create_temp_dir(prefix=f"rustscan_job_{self.job_id}_")
        
        # Пути к временным файлам
        stdout_file = os.path.join(self.temp_dir, "stdout.txt")
        
        cmd = ["rustscan", "-a", self.target]
        
        if self.ports:
            cmd.extend(["-p", self.ports])
        
        # Добавляем кастомные аргументы если указаны
        if self.custom_args and self.custom_args.strip():
            custom_args_list = self.custom_args.strip().split()
            cmd.extend(custom_args_list)
            logger.info(f"[{self.__class__.__name__}] Добавлены кастомные аргументы: {self.custom_args}")
            
        # Add Nmap arguments if scripts are specified
        if self.nmap_scripts and self.nmap_scripts.strip() and self.nmap_scripts.lower() != "none":
            cmd.extend(["--", "nmap", "-sV", "-O", f"--script={self.nmap_scripts}"])
        else:
            # Run without nmap if no scripts specified to avoid auto-triggering
            cmd.extend(["--", "--no-nmap"])
            
        logger.info(f"[{self.__class__.__name__}] Запуск команды: {' '.join(cmd)}")
        
        # Открываем файл для записи stdout
        with open(stdout_file, 'w', encoding='utf-8') as stdout_f:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=stdout_f,
                stderr=asyncio.subprocess.PIPE
            )
        
        logger.info(f"[{self.__class__.__name__}] Запущен процесс Rustscan для задачи {self.job_id}, PID: {process.pid}")
        
        stderr = await process.stderr.read()
        stderr_str = stderr.decode('utf-8', errors='ignore') if stderr else ""
        
        if stderr_str:
            for line in stderr_str.splitlines():
                logger.debug(f"[Rustscan] {line}")
                
        logger.info(f"[{self.__class__.__name__}] Процесс Rustscan завершен с кодом {process.returncode}")
        
        if process.returncode != 0:
            logger.error(f"[{self.__class__.__name__}] Rustscan вернул код ошибки {process.returncode}. stderr: {stderr_str}")
        
        # Читаем stdout из временного файла через базовый класс
        stdout_str = self._read_file_content(stdout_file, "stdout")
        
        # Парсим вывод для извлечения данных
        result = self._parse_output(stdout_str, stderr_str)
        
        # Очищаем временную директорию
        self._cleanup_temp_dir()
        
        # Формируем результат
        return {
            "hostname": result.get("hostname", self.target),
            "ip": result.get("ip", self.target),
            "ports": result.get("ports", []),
            "raw_output": stdout_str + "\n" + stderr_str
        }

    def _parse_output(self, stdout: str, stderr: str) -> ScanResult:
        """
        Парсит вывод Rustscan.
        
        Args:
            stdout: Вывод stdout утилиты
            stderr: Вывод stderr утилиты
            
        Returns:
            ScanResult: Распарсенные данные (hostname, ip, ports)
        """
        result: ScanResult = {
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
