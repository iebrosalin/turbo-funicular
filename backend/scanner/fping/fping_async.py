import asyncio
import logging
import os
import tempfile
import shutil
import re
from typing import Dict, Any, List, Optional
from ..base import BaseScanner

logger = logging.getLogger(__name__)

class FpingScanner(BaseScanner):
    """
    Сканер на основе утилиты fping для быстрого ICMP-сканирования.
    Хост считается живым, если получен хотя бы один ответ на ping.
    Поддерживает все флаги fping.
    """
    
    def __init__(self, job_id: int, target: str, 
                 count: int = 1,
                 timeout: int = 500,
                 retries: int = 2,
                 interval: int = 10,
                 alive_only: bool = True,
                 unreachable: bool = False,
                 quiet: bool = True,
                 verbose: bool = False,
                 resolve: bool = True,
                 reverse: bool = False,
                 show_stats: bool = False,
                 extra_args: Optional[List[str]] = None,
                 output_dir: Optional[str] = None):
        """
        Инициализация сканера fping.
        
        Args:
            job_id: ID задачи сканирования
            target: Целевой хост или сеть (например, "192.168.1.0/24" или "192.168.1.1")
            count: Количество ICMP-запросов на хост (по умолчанию 1)
            timeout: Таймаут ожидания ответа в мс (по умолчанию 500)
            retries: Количество повторных попыток (по умолчанию 2)
            interval: Интервал между запросами в мс (по умолчанию 10)
            alive_only: Показывать только живые хосты (-a флаг)
            unreachable: Показывать недоступные хосты (-u флаг)
            quiet: Тихий режим, только статистика (-q флаг)
            verbose: Подробный вывод (-v флаг)
            resolve: Разрешать имена в IP (-n флаг, по умолчанию True)
            reverse: Обратное DNS-резолвинг (-r флаг)
            show_stats: Показать статистику (-s флаг)
            extra_args: Дополнительные аргументы командной строки
            output_dir: Директория для вывода (не используется, но требуется для совместимости)
        """
        if output_dir is None:
            output_dir = os.getenv('SCANNER_OUTPUT_DIR', '/app/scanner_output')
        super().__init__(job_id, output_dir)
        self.target = target
        self.count = count
        self.timeout = timeout
        self.retries = retries
        self.interval = interval
        self.alive_only = alive_only
        self.unreachable = unreachable
        self.quiet = quiet
        self.verbose = verbose
        self.resolve = resolve
        self.reverse = reverse
        self.show_stats = show_stats
        self.extra_args = extra_args or []
        self.temp_dir = None

    async def scan(self) -> Dict[str, Any]:
        # Создаем временную директорию для хранения файлов результатов
        self.temp_dir = tempfile.mkdtemp(prefix=f"fping_job_{self.job_id}_")
        logger.info(f"[FpingScanner] Создана временная директория: {self.temp_dir}")
        
        # Пути к временным файлам
        stdout_file = os.path.join(self.temp_dir, "stdout.txt")
        stderr_file = os.path.join(self.temp_dir, "stderr.txt")
        
        # Формируем команду
        cmd = ["fping"]
        
        # Добавляем флаги
        if self.alive_only:
            cmd.append("-a")
        if self.unreachable:
            cmd.append("-u")
        if self.quiet:
            cmd.append("-q")
        if self.verbose:
            cmd.append("-v")
        if self.resolve:
            cmd.append("-n")
        else:
            cmd.append("-r")  # Не резолвить имена
        if self.reverse:
            cmd.append("-D")  # Выводить timestamp и DNS
        
        # Основные параметры
        cmd.extend(["-c", str(self.count)])  # Количество пингов
        cmd.extend(["-t", str(self.timeout)])  # Таймаут
        cmd.extend(["-r", str(self.retries)])  # Повторы
        cmd.extend(["-i", str(self.interval)])  # Интервал
        
        if self.show_stats:
            cmd.append("-s")
        
        # Дополнительные аргументы
        cmd.extend(self.extra_args)
        
        # Добавляем цель
        cmd.append(self.target)
        
        logger.info(f"[FpingScanner] Запуск команды: {' '.join(cmd)}")
        
        # Открываем файлы для записи stdout и stderr
        with open(stdout_file, 'w', encoding='utf-8') as stdout_f, \
             open(stderr_file, 'w', encoding='utf-8') as stderr_f:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=stdout_f,
                stderr=stderr_f
            )
        
        logger.info(f"[FpingScanner] Запущен процесс fping для задачи {self.job_id}, PID: {process.pid}")
        
        # Ждем завершения процесса
        await process.wait()
        
        logger.info(f"[FpingScanner] Процесс fping завершен с кодом {process.returncode}")
        
        # Читаем результаты из временных файлов
        stdout_str = ""
        stderr_str = ""
        
        try:
            if os.path.exists(stdout_file):
                with open(stdout_file, 'r', encoding='utf-8', errors='ignore') as f:
                    stdout_str = f.read()
                logger.info(f"[FpingScanner] Прочитан stdout файл, размер: {len(stdout_str)} байт")
            
            if os.path.exists(stderr_file):
                with open(stderr_file, 'r', encoding='utf-8', errors='ignore') as f:
                    stderr_str = f.read()
                logger.info(f"[FpingScanner] Прочитан stderr файл, размер: {len(stderr_str)} байт")
        except Exception as e:
            logger.error(f"[FpingScanner] Ошибка чтения файлов результатов: {e}", exc_info=True)
        
        # Парсим вывод для извлечения данных
        result = self._parse_output(stdout_str, stderr_str)
        
        # Очищаем временную директорию
        try:
            shutil.rmtree(self.temp_dir)
            logger.info(f"[FpingScanner] Временная директория удалена: {self.temp_dir}")
        except Exception as e:
            logger.warning(f"[FpingScanner] Не удалось удалить временную директорию: {e}")
        
        # Формируем результат
        return {
            "hostname": result.get("hostname", ""),
            "ip": result.get("ip", self.target),
            "alive_hosts": result.get("alive_hosts", []),
            "unreachable_hosts": result.get("unreachable_hosts", []),
            "stats": result.get("stats", {}),
            "raw_output": stdout_str + "\n" + stderr_str
        }

    def _parse_output(self, stdout: str, stderr: str) -> Dict[str, Any]:
        """
        Парсинг вывода fping.
        
        fping выводит информацию о живых хостах в stderr в формате:
        <IP> is alive
        
        При использовании -q выводится статистика в конце.
        """
        result = {
            "hostname": "",
            "ip": "",
            "alive_hosts": [],
            "unreachable_hosts": [],
            "stats": {}
        }
        
        # Объединяем stdout и stderr для парсинга
        # fping обычно пишет "is alive" в stderr
        combined_output = stderr + "\n" + stdout
        
        # Паттерн для поиска живых хостов: "<IP> is alive" или "<IP> (<hostname>) is alive"
        alive_pattern = r"([\d\.]+|[a-zA-Z0-9\.\-_]+)\s*(?:\(([^)]+)\))?\s*is alive"
        matches = re.findall(alive_pattern, combined_output, re.IGNORECASE)
        
        logger.info(f"[FpingScanner] Найдено живых хостов: {len(matches)}")
        
        for match in matches:
            ip_or_host = match[0]
            hostname = match[1] if len(match) > 1 and match[1] else ""
            
            host_data = {
                "ip": "",
                "hostname": ""
            }
            
            # Проверяем, является ли строка IP-адресом
            if re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$', ip_or_host):
                host_data["ip"] = ip_or_host
                host_data["hostname"] = hostname
            else:
                host_data["hostname"] = ip_or_host
                host_data["ip"] = hostname if hostname else ip_or_host
            
            result["alive_hosts"].append(host_data)
            
            # Устанавливаем первый найденный хост как основной
            if not result["ip"]:
                result["ip"] = host_data["ip"]
                result["hostname"] = host_data["hostname"]
        
        # Паттерн для поиска недоступных хостов: "<IP> is unreachable" или таймауты
        unreachable_pattern = r"([\d\.]+|[a-zA-Z0-9\.\-_]+)\s*(?:\(([^)]+)\))?\s*(?:is unreachable|timed out)"
        unreachable_matches = re.findall(unreachable_pattern, combined_output, re.IGNORECASE)
        
        for match in unreachable_matches:
            ip_or_host = match[0]
            hostname = match[1] if len(match) > 1 and match[1] else ""
            
            host_data = {
                "ip": "",
                "hostname": ""
            }
            
            if re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$', ip_or_host):
                host_data["ip"] = ip_or_host
                host_data["hostname"] = hostname
            else:
                host_data["hostname"] = ip_or_host
                host_data["ip"] = hostname if hostname else ip_or_host
            
            result["unreachable_hosts"].append(host_data)
        
        # Парсинг статистики при использовании флага -s или -q
        # Пример: "31 targets\n31 alive\n0 unreachable\n..."
        stats_patterns = [
            (r"(\d+)\s+targets?", "targets"),
            (r"(\d+)\s+alive", "alive"),
            (r"(\d+)\s+unreachable", "unreachable"),
            (r"(\d+)\s+unknown addresses", "unknown"),
            (r"(\d+)\s+timeouts", "timeouts"),
            (r"(\d+)\s+invalid addresses", "invalid"),
        ]
        
        for pattern, key in stats_patterns:
            match = re.search(pattern, combined_output, re.IGNORECASE)
            if match:
                result["stats"][key] = int(match.group(1))
        
        # Парсинг времени выполнения и пакетов
        time_pattern = r"\(([\d\.]+)\s*ms min/avg/max(?:\s*\+\s*([\d\.]+)\s*stdev)?\)"
        time_match = re.search(time_pattern, combined_output)
        if time_match:
            result["stats"]["min_ms"] = float(time_match.group(1))
            if time_match.group(2):
                result["stats"]["avg_ms"] = float(time_match.group(2))
                if time_match.group(3):
                    result["stats"]["max_ms"] = float(time_match.group(3))
                if time_match.group(4):
                    result["stats"]["stdev_ms"] = float(time_match.group(4))
        
        # Парсинг потери пакетов
        loss_pattern = r"(\d+(?:\.\d+)?)\s*%\s*packet loss"
        loss_match = re.search(loss_pattern, combined_output, re.IGNORECASE)
        if loss_match:
            result["stats"]["packet_loss_percent"] = float(loss_match.group(1))
        
        logger.info(f"[FpingScanner] Статистика: {result['stats']}")
        
        return result
