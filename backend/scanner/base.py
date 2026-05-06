import asyncio
import logging
import os
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class BaseScanner:
    """Базовый класс для всех сканеров"""
    
    def __init__(self, job_id: int, output_dir: str = "/app/scanner_output"):
        self.job_id = job_id
        # Директория больше не создается - результаты сохраняются только в БД
        self.output_dir = output_dir
        self.job_output_dir = None  # Больше не используется
    
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
    
    def _log_file_content(self, file_path: str, label: str = "Файл результата"):
        """Выводит первые 100 строк файла для отладки (больше не используется)"""
        logger.warning(f"[SCAN_DEBUG] Логирование файлов больше не поддерживается: {label}")
