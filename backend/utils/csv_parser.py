"""
Парсер CSV для обработки списков целей сканирования.
Поддерживает загрузку из текста и файлов.
"""
import csv
import io
from typing import List, Tuple, Optional
from backend.models.target import Target, TargetType


class CSVParser:
    """
    Парсер CSV для извлечения IP-адресов и доменных имен.
    
    Поддерживаемые форматы:
    - Простой список (одна колонка): каждый элемент - отдельная цель
    - CSV с заголовками: колонки 'ip', 'host', 'domain', 'target', 'address'
    - Смешанные данные: автоматическое определение типа каждой записи
    """
    
    # Допустимые названия колонок для целей
    TARGET_COLUMNS = {
        'ip', 'ipv4', 'ipv6', 'host', 'hostname', 
        'domain', 'target', 'address', 'addr'
    }
    
    @classmethod
    def parse_text(cls, csv_text: str, skip_invalid: bool = True) -> Tuple[List[Target], List[str]]:
        """
        Парсит CSV текст в список Target объектов.
        
        Args:
            csv_text: CSV текст для парсинга
            skip_invalid: Если True, пропускает невалидные записи
            
        Returns:
            Кортеж (список валидных Target, список ошибок)
        """
        targets = []
        errors = []
        
        if not csv_text or not csv_text.strip():
            return targets, errors
        
        try:
            # Пробуем разные диалекты CSV
            dialects = ['excel', 'excel-tab', 'unix']
            reader = None
            
            for dialect in dialects:
                try:
                    reader = csv.reader(
                        io.StringIO(csv_text),
                        dialect=dialect
                    )
                    # Пробуем прочитать первую строку для проверки
                    rows = list(reader)
                    if rows:
                        break
                except csv.Error:
                    continue
            
            if not reader or not rows:
                # Если не удалось определить диалект, пробуем простой split
                return cls._parse_simple_list(csv_text, skip_invalid)
            
            # Обработка строк
            targets, errors = cls._process_rows(rows, skip_invalid)
            
        except Exception as e:
            errors.append(f"Ошибка парсинга CSV: {str(e)}")
        
        return targets, errors
    
    @classmethod
    def _parse_simple_list(cls, text: str, skip_invalid: bool = True) -> Tuple[List[Target], List[str]]:
        """Парсит простой список (по одной записи на строку)"""
        targets = []
        errors = []
        
        for line_num, line in enumerate(text.splitlines(), 1):
            line = line.strip()
            
            # Пропускаем пустые строки и комментарии
            if not line or line.startswith('#'):
                continue
            
            # Разделяем по запятым или точкам с запятой если есть
            if ',' in line or ';' in line:
                parts = [p.strip() for p in line.replace(';', ',').split(',')]
                for part in parts:
                    if part and not part.startswith('#'):
                        target = Target.from_string(
                            part,
                            original_input=part,  # Важно: используем часть как original_input
                            metadata={'line': line_num}
                        )
                        if target.is_valid() or not skip_invalid:
                            targets.append(target)
                        elif not target.is_valid():
                            errors.append(f"Строка {line_num}: невалидное значение '{part}'")
            else:
                target = Target.from_string(
                    line,
                    original_input=line,
                    metadata={'line': line_num}
                )
                if target.is_valid() or not skip_invalid:
                    targets.append(target)
                elif not target.is_valid():
                    errors.append(f"Строка {line_num}: невалидное значение '{line}'")
        
        return targets, errors
    
    @classmethod
    def _process_rows(cls, rows: List[List[str]], skip_invalid: bool) -> Tuple[List[Target], List[str]]:
        """Обрабатывает строки CSV"""
        targets = []
        errors = []
        
        if not rows:
            return targets, errors
        
        # Определяем, есть ли заголовок
        header = rows[0] if rows else []
        has_header = cls._detect_header(header)
        
        if has_header:
            # Ищем колонки с целями
            target_columns = cls._find_target_columns(header)
            
            if not target_columns:
                # Если не нашли известные колонки, считаем что это простой список
                return cls._parse_simple_list('\n'.join([','.join(row) for row in rows]), skip_invalid)
            
            # Обрабатываем с заголовком
            for line_num, row in enumerate(rows[1:], 2):  # Начинаем со 2-й строки
                for col_idx in target_columns:
                    if col_idx < len(row):
                        value = row[col_idx].strip()
                        if value and not value.startswith('#'):
                            target = Target.from_string(
                                value,
                                original_input=value,
                                metadata={
                                    'line': line_num,
                                    'column': header[col_idx]
                                }
                            )
                            if target.is_valid() or not skip_invalid:
                                targets.append(target)
                            elif not target.is_valid():
                                errors.append(
                                    f"Строка {line_num}, колонка '{header[col_idx]}': "
                                    f"невалидное значение '{value}'"
                                )
        else:
            # Без заголовка - каждая строка может содержать одну или несколько целей
            for line_num, row in enumerate(rows, 1):
                for cell in row:
                    value = cell.strip()
                    if value and not value.startswith('#'):
                        target = Target.from_string(
                            value,
                            original_input=value,
                            metadata={'line': line_num}
                        )
                        if target.is_valid() or not skip_invalid:
                            targets.append(target)
                        elif not target.is_valid():
                            errors.append(f"Строка {line_num}: невалидное значение '{value}'")
        
        return targets, errors
    
    @classmethod
    def _detect_header(cls, row: List[str]) -> bool:
        """Определяет, является ли строка заголовком"""
        if not row:
            return False
        
        # Проверяем, содержит ли строка известные названия колонок
        for cell in row:
            cell_lower = cell.lower().strip()
            if cell_lower in cls.TARGET_COLUMNS:
                return True
        
        # Если все ячейки выглядят как заголовки (не IP и не домены)
        all_headers = True
        for cell in row:
            cell = cell.strip()
            # Проверяем, похоже ли на IP или домен
            if cls._looks_like_data(cell):
                all_headers = False
                break
        
        return all_headers
    
    @classmethod
    def _find_target_columns(cls, header: List[str]) -> List[int]:
        """Находит индексы колонок с целями"""
        indices = []
        
        for idx, col in enumerate(header):
            if col.lower().strip() in cls.TARGET_COLUMNS:
                indices.append(idx)
        
        # Если не нашли, возвращаем первую колонку только если это не заголовок
        if not indices and header:
            # Проверяем, не является ли первая колонка заголовком типа "ip" или "hostname"
            first_col = header[0].lower().strip()
            if first_col not in cls.TARGET_COLUMNS:
                indices = [0]
        
        return indices
    
    @classmethod
    def _looks_like_data(cls, value: str) -> bool:
        """Проверяет, выглядит ли значение как данные (а не заголовок)"""
        if not value:
            return False
        
        # Проверяем на IP
        try:
            import ipaddress
            ipaddress.ip_address(value)
            return True
        except ValueError:
            pass
        
        # Проверяем на число
        if value.isdigit():
            return True
        
        # Проверяем на домен (содержит точку)
        if '.' in value and len(value) > 3:
            return True
        
        return False
    
    @classmethod
    def parse_file(cls, file_path: str, skip_invalid: bool = True) -> Tuple[List[Target], List[str]]:
        """
        Парсит CSV файл.
        
        Args:
            file_path: Путь к файлу
            skip_invalid: Если True, пропускает невалидные записи
            
        Returns:
            Кортеж (список валидных Target, список ошибок)
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            return cls.parse_text(content, skip_invalid)
        except Exception as e:
            return [], [f"Ошибка чтения файла: {str(e)}"]
    
    @classmethod
    def deduplicate(cls, targets: List[Target]) -> List[Target]:
        """Удаляет дубликаты из списка целей"""
        seen = set()
        unique = []
        
        for target in targets:
            if target.value not in seen:
                seen.add(target.value)
                unique.append(target)
        
        return unique
    
    @classmethod
    def filter_by_type(cls, targets: List[Target], 
                       target_types: List[TargetType]) -> List[Target]:
        """Фильтрует цели по типу"""
        return [t for t in targets if t.type in target_types]
    
    @classmethod
    def get_statistics(cls, targets: List[Target]) -> dict:
        """Возвращает статистику по списку целей"""
        stats = {
            'total': len(targets),
            'ipv4': 0,
            'ipv6': 0,
            'ipv4_network': 0,  # CIDR IPv4
            'ipv6_network': 0,  # CIDR IPv6
            'domain': 0,
            'unknown': 0,
            'valid': 0,
            'invalid': 0
        }
        
        for target in targets:
            if target.type == TargetType.IPV4:
                stats['ipv4'] += 1
            elif target.type == TargetType.IPV6:
                stats['ipv6'] += 1
            elif target.type == TargetType.IPV4_NETWORK:
                stats['ipv4_network'] += 1
            elif target.type == TargetType.IPV6_NETWORK:
                stats['ipv6_network'] += 1
            elif target.type == TargetType.DOMAIN:
                stats['domain'] += 1
            else:
                stats['unknown'] += 1
            
            if target.is_valid():
                stats['valid'] += 1
            else:
                stats['invalid'] += 1
        
        return stats
