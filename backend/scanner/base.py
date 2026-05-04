import asyncio
import logging
import os
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class BaseScanner:
    """Базовый класс для всех сканеров"""
    
    def __init__(self, job_id: int, output_dir: str = "/app/scanner_output"):
        self.job_id = job_id
        self.output_dir = output_dir
        self.job_output_dir = os.path.join(output_dir, str(job_id))
        
        # Создаем директорию для вывода если она не существует
        os.makedirs(self.job_output_dir, exist_ok=True)
    
    async def scan(self) -> Dict[str, Any]:
        """
        Метод сканирования, должен быть переопределен в наследниках
        """
        raise NotImplementedError("Метод scan должен быть реализован в наследнике")
    
    def _parse_output(self, stdout: str, stderr: str) -> Dict[str, Any]:
        """
        Парсинг вывода сканера, должен быть переопределен в наследниках
        """
        raise NotImplementedError("Метод _parse_output должен быть реализован в наследнике")
