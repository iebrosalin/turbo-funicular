import asyncio
import logging
import os
import re
from typing import Dict, Any, List, Optional, Union
from ..base import BaseScanner, ScanResult
from backend.models.target import Target
import ipaddress

logger = logging.getLogger(__name__)

class FpingScanner(BaseScanner):
    """
    Сканер на основе утилиты fping для быстрого ICMP-сканирования.
    Хост считается живым, если получен хотя бы один ответ на ping.
    Поддерживает все флаги fping.
    """
    
    SCANNER_NAME = "fping"
    SUPPORTS_MULTIPLE_TARGETS = True  # Поддерживает списки через -f
    DEFAULT_TIMEOUT = 30
    
    def __init__(
        self, 
        job_id: int, 
        target: Union[str, Target],
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
        output_dir: Optional[str] = None,
        use_cidr_expand: bool = True  # Новый параметр для автоматического расширения CIDR
    ):
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
            use_cidr_expand: Автоматически расширять CIDR в список IP с флагом -g (по умолчанию True)
        """
        super().__init__(job_id, target, output_dir)
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
        self.use_cidr_expand = use_cidr_expand
        
        # Проверяем, является ли цель CIDR-нотацией
        self._is_cidr = self._check_if_cidr(self.target)

    def _check_if_cidr(self, target: str) -> bool:
        """
        Проверяет, является ли строка CIDR-нотацией (например, 192.168.1.0/24).
        
        Args:
            target: Строка для проверки
            
        Returns:
            bool: True если это CIDR-нотация
        """
        if '/' not in target:
            return False
        
        try:
            ipaddress.ip_network(target, strict=False)
            return True
        except ValueError:
            return False

    def _expand_cidr_to_ips(self, cidr: str) -> List[str]:
        """
        Расширяет CIDR-нотацию в список IP-адресов.
        
        Args:
            cidr: CIDR-нотация (например, "192.168.1.0/24")
            
        Returns:
            List[str]: Список IP-адресов
        """
        try:
            network = ipaddress.ip_network(cidr, strict=False)
            # Исключаем сетевой и широковещательный адреса для IPv4
            ips = [str(ip) for ip in network.hosts()]
            logger.info(f"[FpingScanner] CIDR {cidr} расширен в {len(ips)} IP-адресов")
            return ips
        except Exception as e:
            logger.warning(f"[FpingScanner] Ошибка расширения CIDR {cidr}: {e}")
            return [cidr]  # Возвращаем как есть при ошибке

    async def scan(self) -> ScanResult:
        """
        Выполняет ICMP-сканирование через fping.
        
        Returns:
            ScanResult: Результаты с живыми/недоступными хостами и статистикой
        """
        # Создаем временную директорию через базовый класс
        self._create_temp_dir(prefix=f"fping_job_{self.job_id}_")
        
        # Пути к временным файлам
        stdout_file = os.path.join(self.temp_dir, "stdout.txt")
        stderr_file = os.path.join(self.temp_dir, "stderr.txt")
        
        # Формируем команду
        cmd = ["fping"]
        
        # Для CIDR всегда используем режим без -q, чтобы получить список живых хостов
        # Флаг -q подавляет вывод "is alive", который нам нужен для парсинга
        is_cidr_scan = self._is_cidr and self.use_cidr_expand
        
        # Добавляем флаги
        if self.alive_only and not is_cidr_scan:
            # Для CIDR не используем -a, так как fping сам фильтрует с -g
            cmd.append("-a")
        if self.unreachable:
            cmd.append("-u")
        # Не используем -q при сканировании CIDR, чтобы получить список живых хостов
        if self.quiet and not is_cidr_scan:
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
        
        # Обработка CIDR-нотации: используем флаг -g для передачи диапазона
        if is_cidr_scan:
            # fping поддерживает CIDR напрямую с флагом -g
            cmd.append("-g")
            cmd.append(self.target)
            logger.info(f"[{self.__class__.__name__}] CIDR-цель {self.target} будет обработана с флагом -g")
        else:
            # Добавляем цель как есть (одиночный хост или уже расширенный список)
            cmd.append(self.target)
        
        logger.info(f"[{self.__class__.__name__}] Запуск команды: {' '.join(cmd)}")
        
        # Открываем файлы для записи stdout и stderr
        with open(stdout_file, 'w', encoding='utf-8') as stdout_f, \
             open(stderr_file, 'w', encoding='utf-8') as stderr_f:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=stdout_f,
                stderr=stderr_f
            )
        
        logger.info(f"[{self.__class__.__name__}] Запущен процесс fping для задачи {self.job_id}, PID: {process.pid}")
        
        # Ждем завершения процесса с таймаутом
        try:
            await asyncio.wait_for(process.wait(), timeout=300)  # 5 минут максимум
        except asyncio.TimeoutError:
            logger.error(f"[{self.__class__.__name__}] Процесс fping превысил таймаут, принудительно завершаем")
            process.kill()
            await process.wait()
        
        logger.info(f"[{self.__class__.__name__}] Процесс fping завершен с кодом {process.returncode}")
        
        # Читаем результаты из временных файлов через базовый класс
        stdout_str = self._read_file_content(stdout_file, "stdout")
        stderr_str = self._read_file_content(stderr_file, "stderr")
        
        # Логируем вывод для отладки
        logger.info(f"[{self.__class__.__name__}] STDOUT ({len(stdout_str)} bytes): {stdout_str[:500] if stdout_str else 'ПУСТО'}")
        logger.info(f"[{self.__class__.__name__}] STDERR ({len(stderr_str)} bytes): {stderr_str[:500] if stderr_str else 'ПУСТО'}")
        
        # Парсим вывод для извлечения данных
        result = self._parse_output(stdout_str, stderr_str)
        
        # Очищаем временную директорию
        self._cleanup_temp_dir()
        
        # Формируем результат
        return {
            "hostname": result.get("hostname", ""),
            "ip": result.get("ip", self.target),
            "alive_hosts": result.get("alive_hosts", []),
            "unreachable_hosts": result.get("unreachable_hosts", []),
            "stats": result.get("stats", {}),
            "raw_output": stdout_str + "\n" + stderr_str,
            "output_xml": ""  # fping не генерирует XML
        }

    def _parse_output(self, stdout: str, stderr: str) -> ScanResult:
        """
        Парсинг вывода fping.
        
        fping выводит информацию о живых хостах в stderr в формате:
        <IP> is alive
        
        При сканировании CIDR с флагом -g вывод может быть в формате:
        <IP> is alive
        <IP> is alive
        ...
        
        При использовании -q выводится статистика в конце.
        
        Args:
            stdout: Вывод stdout утилиты
            stderr: Вывод stderr утилиты
            
        Returns:
            ScanResult: Распарсенные данные (alive_hosts, unreachable_hosts, stats)
        """
        result: ScanResult = {
            "hostname": "",
            "ip": "",
            "alive_hosts": [],
            "unreachable_hosts": [],
            "stats": {}
        }
        
        # Объединяем stdout и stderr для парсинга
        # fping обычно пишет "is alive" в stderr, но при CIDR-сканировании может быть и в stdout
        combined_output = stderr + "\n" + stdout
        
        logger.debug(f"[FpingScanner] Комбинированный вывод для парсинга:\n{combined_output[:500]}...")
        
        # Паттерн для поиска живых хостов: "<IP> is alive" или "<hostname> is alive"
        # Поддерживаем различные форматы вывода fping
        alive_pattern = r"^([^\s]+)\s+is\s+alive\s*$"
        matches = re.findall(alive_pattern, combined_output, re.IGNORECASE | re.MULTILINE)
        
        logger.info(f"[FpingScanner] Найдено живых хостов по основному паттерну: {len(matches)}")
        
        for match in matches:
            ip_or_host = match.strip()
            if not ip_or_host:
                continue
                
            host_data = {
                "ip": "",
                "hostname": ""
            }
            
            # Проверяем, является ли строка IP-адресом
            if re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$', ip_or_host):
                host_data["ip"] = ip_or_host
                host_data["hostname"] = ""
            else:
                host_data["hostname"] = ip_or_host
                host_data["ip"] = ip_or_host  # Если не IP, используем как есть
            
            result["alive_hosts"].append(host_data)
            
            # Устанавливаем первый найденный хост как основной
            if not result["ip"] and host_data["ip"]:
                result["ip"] = host_data["ip"]
                result["hostname"] = host_data["hostname"]
        
        # Дополнительный паттерн для случаев с обратным DNS: "<IP> (<hostname>) is alive"
        alive_pattern_dns = r"([\d\.]+|[a-zA-Z0-9\.\-_]+)\s*\(([^)]+)\)\s*is\s+alive"
        matches_dns = re.findall(alive_pattern_dns, combined_output, re.IGNORECASE)
        
        logger.info(f"[FpingScanner] Найдено живых хостов с DNS: {len(matches_dns)}")
        
        for match in matches_dns:
            ip_or_host = match[0].strip()
            hostname = match[1].strip() if len(match) > 1 else ""
            
            # Пропускаем уже добавленные хосты
            existing_ips = [h["ip"] for h in result["alive_hosts"]]
            existing_hostnames = [h["hostname"] for h in result["alive_hosts"]]
            
            if ip_or_host in existing_ips or hostname in existing_hostnames:
                continue
            
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
            
            result["alive_hosts"].append(host_data)
            
            if not result["ip"] and host_data["ip"]:
                result["ip"] = host_data["ip"]
                result["hostname"] = host_data["hostname"]
        
        # ============================================
        # ПАТТЕРН 3: Режим -c (count) со статистикой
        # Формат: "<IP> : xmt/rcv/%loss = X/Y/Z%"
        # Хост жив, если received > 0
        # ============================================
        # Упрощенный паттерн - не требуем min/avg/max в той же строке
        stats_pattern = r"^([\d\.]+|[a-zA-Z0-9\.\-_]+)\s*:\s*xmt/rcv/%loss\s*=\s*(\d+)/(\d+)/([\d\.]+)%"
        stats_matches = re.findall(stats_pattern, combined_output, re.IGNORECASE | re.MULTILINE)
        
        logger.info(f"[FpingScanner] Найдено хостов по паттерну статистики: {len(stats_matches)}")
        
        for match in stats_matches:
            ip_or_host = match[0].strip()
            transmitted = int(match[1])
            received = int(match[2])
            loss_percent = float(match[3])
            
            # Хост жив, если получен хотя бы один ответ
            if received == 0:
                continue
            
            # Пропускаем уже добавленные хосты
            existing_ips = [h["ip"] for h in result["alive_hosts"]]
            existing_hostnames = [h["hostname"] for h in result["alive_hosts"]]
            
            if ip_or_host in existing_ips or ip_or_host in existing_hostnames:
                continue
            
            host_data = {
                "ip": "",
                "hostname": "",
                "stats": {
                    "transmitted": transmitted,
                    "received": received,
                    "loss_percent": loss_percent
                }
            }
            
            if re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$', ip_or_host):
                host_data["ip"] = ip_or_host
                host_data["hostname"] = ""
            else:
                host_data["hostname"] = ip_or_host
                host_data["ip"] = ip_or_host
            
            result["alive_hosts"].append(host_data)
            
            if not result["ip"] and host_data["ip"]:
                result["ip"] = host_data["ip"]
                result["hostname"] = host_data["hostname"]
        
        # ============================================
        # ПАТТЕРН 4: Режим с обратным DNS (-D флаг)
        # Формат: "<timestamp> <IP> (<hostname>) is alive" или "<timestamp> <IP> is alive"
        # Извлекаем DNS-имя из скобок если оно есть
        # ============================================
        dns_pattern = r"^\[\d+\]\s+([\d\.]+)\s+(?:\(([^)]+)\)\s+)?is\s+alive"
        dns_matches = re.findall(dns_pattern, combined_output, re.IGNORECASE | re.MULTILINE)
        
        logger.info(f"[FpingScanner] Найдено хостов с timestamp и DNS: {len(dns_matches)}")
        
        for match in dns_matches:
            ip = match[0].strip()
            hostname = match[1].strip() if len(match) > 1 and match[1] else ""
            
            # Пропускаем уже добавленные хосты
            existing_ips = [h["ip"] for h in result["alive_hosts"]]
            existing_hostnames = [h["hostname"] for h in result["alive_hosts"]]
            
            if ip in existing_ips:
                # Если IP уже есть, но есть новое DNS-имя, обновляем hostname
                if hostname and hostname not in existing_hostnames:
                    for h in result["alive_hosts"]:
                        if h["ip"] == ip:
                            h["hostname"] = hostname
                            break
                continue
            
            host_data = {
                "ip": ip,
                "hostname": hostname,
                "stats": {}
            }
            
            result["alive_hosts"].append(host_data)
            
            if not result["ip"]:
                result["ip"] = ip
                result["hostname"] = hostname
        
        # Паттерн для поиска недоступных хостов: "<IP> is unreachable" или таймауты
        unreachable_pattern = r"^([^\s]+)\s+(?:is\s+unreachable|timed\s*out)\s*$"
        unreachable_matches = re.findall(unreachable_pattern, combined_output, re.IGNORECASE | re.MULTILINE)
        
        logger.info(f"[FpingScanner] Найдено недоступных хостов: {len(unreachable_matches)}")
        
        for match in unreachable_matches:
            ip_or_host = match.strip()
            if not ip_or_host:
                continue
                
            host_data = {
                "ip": "",
                "hostname": ""
            }
            
            if re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$', ip_or_host):
                host_data["ip"] = ip_or_host
                host_data["hostname"] = ""
            else:
                host_data["hostname"] = ip_or_host
                host_data["ip"] = ip_or_host
            
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
        
        logger.info(f"[FpingScanner] Итого живых хостов: {len(result['alive_hosts'])}, статистика: {result['stats']}")
        
        return result
