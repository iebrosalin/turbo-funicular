import asyncio
import logging
import os
from typing import Dict, Any, List, Optional, Union
from ..base import BaseScanner, ScanResult
from backend.models.target import Target

logger = logging.getLogger(__name__)

class DigScanner(BaseScanner):
    """Сканер на основе dig для DNS-запросов"""
    
    SCANNER_NAME = "dig"
    SUPPORTS_MULTIPLE_TARGETS = False  # Только один домен за раз
    DEFAULT_TIMEOUT = 60
    
    def __init__(
        self, 
        job_id: int, 
        target: Union[str, Target], 
        record_types: Optional[List[str]] = None,
        output_dir: Optional[str] = None
    ):
        """
        Инициализация сканера Dig.
        
        Args:
            job_id: ID задачи сканирования
            target: Доменное имя для запроса
            record_types: Типы DNS записей для запроса
            output_dir: Директория для временных файлов
        """
        super().__init__(job_id, target, output_dir)
        # Default types if not specified
        self.record_types = record_types or ["A", "AAAA", "MX", "NS", "TXT", "CNAME", "SOA"]

    async def scan(self) -> ScanResult:
        """
        Выполняет DNS-запросы через dig.
        
        Returns:
            ScanResult: Результаты с DNS записями
        """
        # Создаем временную директорию через базовый класс
        self._create_temp_dir(prefix=f"dig_job_{self.job_id}_")
        
        # Пути к временным файлам
        stdout_file = os.path.join(self.temp_dir, "stdout.txt")
        
        cmd = ["dig"]
        
        # Add record types
        for rtype in self.record_types:
            cmd.append(rtype)
            
        cmd.append(self.target)
        cmd.append("+noall")
        cmd.append("+answer")
        cmd.append("+authority")
        cmd.append("+additional")
        
        logger.info(f"[{self.__class__.__name__}] Запуск команды: {' '.join(cmd)}")
        
        # Открываем файл для записи stdout
        with open(stdout_file, 'w', encoding='utf-8') as stdout_f:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=stdout_f,
                stderr=asyncio.subprocess.PIPE
            )
        
        logger.info(f"[{self.__class__.__name__}] Запущен процесс Dig для задачи {self.job_id}, PID: {process.pid}")
        
        stderr = await process.stderr.read()
        stderr_str = stderr.decode('utf-8', errors='ignore') if stderr else ""
        
        if stderr_str:
            for line in stderr_str.splitlines():
                logger.debug(f"[Dig] {line}")
                
        logger.info(f"[{self.__class__.__name__}] Процесс Dig завершен с кодом {process.returncode}")
        
        # Читаем stdout из временного файла через базовый класс
        stdout_str = self._read_file_content(stdout_file, "stdout")
        
        result = self._parse_output(stdout_str)
        
        # Очищаем временную директорию
        self._cleanup_temp_dir()
        
        return {
            "hostname": self.target,
            "ip": "",  # Dig doesn't necessarily resolve the IP of the target itself in the same way
            "ports": [],
            "dns_records": result.get("records", []),
            "raw_output": stdout_str + "\n" + stderr_str
        }

    def _parse_output(self, output: str) -> ScanResult:
        """
        Парсит вывод dig.
        
        Args:
            output: Вывод утилиты dig
            
        Returns:
            ScanResult: Распарсенные DNS записи
        """
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
