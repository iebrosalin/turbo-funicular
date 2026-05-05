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
        logger.info(f"[SCAN_DEBUG] Директория для задачи {job_id}: {self.job_output_dir}")
        logger.info(f"[SCAN_DEBUG] Директория существует: {os.path.exists(self.job_output_dir)}")
        logger.info(f"[SCAN_DEBUG] Права доступа к директории: {oct(os.stat(self.job_output_dir).st_mode)[-3:]}")
    
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
        """Выводит первые 100 строк файла для отладки"""
        if os.path.exists(file_path):
            try:
                size = os.path.getsize(file_path)
                logger.info(f"[SCAN_DEBUG] {label} создан: {file_path} (Размер: {size} байт)")
                with open(file_path, 'r', errors='ignore') as f:
                    lines = f.readlines()
                    logger.info(f"[SCAN_DEBUG] Всего строк в файле: {len(lines)}")
                    logger.info(f"[SCAN_DEBUG] --- Первые 100 строк {label} ---")
                    for i, line in enumerate(lines[:100]):
                        logger.debug(f"[SCAN_DEBUG] [{i+1}] {line.rstrip()}")
                    if len(lines) > 100:
                        logger.debug(f"[SCAN_DEBUG] ... и еще {len(lines) - 100} строк")
                    logger.info(f"[SCAN_DEBUG] --- Конец превью {label} ---")
            except Exception as e:
                logger.error(f"[SCAN_DEBUG] Ошибка чтения файла {file_path}: {e}")
        else:
            logger.warning(f"[SCAN_DEBUG] {label} не найден: {file_path}")
