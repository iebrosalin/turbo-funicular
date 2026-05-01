import re
from typing import List, Any, Dict, Optional, Tuple
from sqlalchemy import and_, or_, not_
from sqlalchemy.sql.elements import BinaryExpression

class QueryParserError(Exception):
    """Ошибка парсинга запроса."""
    pass

class SQLQueryParser:
    """
    Парсер SQL-like строк для фильтрации активов.
    Поддерживает:
    - Поля: ip, hostname, os, ports, source, mac, vendor, status, notes
    - Операторы: =, !=, LIKE, IN, REG_MATCH
    - Логические операторы: AND, OR
    - Группировка: ()
    
    Пример: (ip = "192.168.1.1" OR hostname LIKE "%srv%") AND ports IN [80, 443]
    """

    OPERATORS = {
        '=': 'eq',
        '!=': 'ne',
        'LIKE': 'like',
        'IN': 'in',
        'REG_MATCH': 'regexp'
    }

    def __init__(self, model_class):
        self.model_class = model_class
        self.tokens = []
        self.pos = 0

    def tokenize(self, query: str) -> List[str]:
        """Разбивает строку запроса на токены."""
        # Регулярное выражение для токенизации
        token_spec = r"""
            (?P<STRING>"[^"]*"|'[^']*') |  # Строки в кавычках
            (?P<NUMBER>\d+) |              # Числа
            (?P<LIST>\[[^\]]*\]) |         # Списки [...]
            (?P<OP>!=|=|LIKE|IN|REG_MATCH|AND|OR|NOT|\(|\)) | # Операторы и скобки
            (?P<FIELD>[a-zA-Z_][a-zA-Z0-9_]*) | # Имена полей
            (?P<SKIP>\s+) |                # Пробелы
            (?P<OTHER>.)                   # Остальное (ошибка)
        """
        tokens = []
        for mo in re.finditer(token_spec, query, re.VERBOSE | re.IGNORECASE):
            kind = mo.lastgroup
            value = mo.group()
            if kind == 'SKIP':
                continue
            elif kind == 'OTHER':
                raise QueryParserError(f"Недопустимый символ: {value}")
            tokens.append((kind, value))
        return tokens

    def parse(self, query: str):
        """Парсит строку запроса и возвращает условие SQLAlchemy."""
        self.tokens = self.tokenize(query)
        self.pos = 0
        if not self.tokens:
            return None
        result = self.parse_or_expression()
        if self.pos < len(self.tokens):
            raise QueryParserError(f"Неожиданный токен после конца выражения: {self.tokens[self.pos]}")
        return result

    def current_token(self):
        if self.pos < len(self.tokens):
            return self.tokens[self.pos]
        return None

    def consume(self, expected_kind=None, expected_value=None):
        token = self.current_token()
        if token is None:
            raise QueryParserError("Ожидался токен, но достигнут конец выражения")
        
        kind, value = token
        
        if expected_kind and kind != expected_kind:
            raise QueryParserError(f"Ожидался тип токена {expected_kind}, получен {kind}")
        
        if expected_value and value.upper() != expected_value.upper():
            raise QueryParserError(f"Ожидался токен {expected_value}, получен {value}")
        
        self.pos += 1
        return token

    def parse_or_expression(self):
        """Парсит выражение OR."""
        left = self.parse_and_expression()
        
        while self.current_token() and self.current_token()[1].upper() == 'OR':
            self.consume(expected_value='OR')
            right = self.parse_and_expression()
            left = or_(left, right)
            
        return left

    def parse_and_expression(self):
        """Парсит выражение AND."""
        left = self.parse_primary()
        
        while self.current_token() and self.current_token()[1].upper() == 'AND':
            self.consume(expected_value='AND')
            right = self.parse_primary()
            left = and_(left, right)
            
        return left

    def parse_primary(self):
        """Парсит первичное выражение (скобки, NOT или условие)."""
        token = self.current_token()
        if not token:
            raise QueryParserError("Неожиданный конец выражения")
            
        kind, value = token
        
        if value == '(':
            self.consume(expected_value='(')
            expr = self.parse_or_expression()
            self.consume(expected_value=')')
            return expr
            
        if value.upper() == 'NOT':
            self.consume(expected_value='NOT')
            expr = self.parse_primary()
            return not_(expr)
            
        return self.parse_condition()

    def parse_condition(self):
        """Парсит простое условие: field op value."""
        field_token = self.consume(expected_kind='FIELD')
        field_name = field_token[1].lower()
        
        # Проверка существования поля в модели
        if not hasattr(self.model_class, field_name):
            raise QueryParserError(f"Неизвестное поле: {field_name}")
        
        col = getattr(self.model_class, field_name)
        
        op_token = self.current_token()
        if not op_token or op_token[0] not in ['OP', 'FIELD']: # FIELD может быть LIKE, IN и т.д.
            raise QueryParserError("Ожидался оператор после имени поля")
        
        # Если оператор это слово (LIKE, IN, etc), оно может быть распознано как FIELD или OP в зависимости от регистра/контекста
        # Нормализуем
        op_value = op_token[1].upper()
        if op_value in ['LIKE', 'IN', 'REG_MATCH', 'AND', 'OR', 'NOT']:
             self.consume() # Потребляем как оператор
        elif op_token[1] in ['=', '!=']:
             self.consume()
        else:
             # Попытка обработать как оператор, если он был распознан как FIELD из-за регистра
             if op_value in self.OPERATORS:
                 self.consume()
             else:
                 raise QueryParserError(f"Неизвестный оператор: {op_token[1]}")

        op_map = {
            '=': lambda c, v: c == v,
            '!=': lambda c, v: c != v,
            'LIKE': lambda c, v: c.ilike(v.replace('*', '%')),
            'REG_MATCH': lambda c, v: c.op('~')(v),
            'IN': lambda c, v: c.in_(v) if isinstance(v, list) else c.in_([v])
        }

        if op_value not in op_map:
            raise QueryParserError(f"Неподдерживаемый оператор: {op_value}")

        # Парсинг значения
        val_token = self.current_token()
        if not val_token:
            raise QueryParserError("Ожидалось значение после оператора")
        
        value = None
        kind, val_str = val_token
        
        if kind == 'STRING':
            value = val_str[1:-1] # Убираем кавычки
            self.consume()
        elif kind == 'NUMBER':
            value = int(val_str)
            self.consume()
        elif kind == 'LIST':
            # Парсинг списка [1, 2, 3] или ["a", "b"]
            inner = val_str[1:-1].strip()
            if not inner:
                value = []
            else:
                # Простой парсинг элементов списка
                items = []
                for item in re.findall(r'"([^"]*)"|\'([^\']*)\'|(\d+)', inner):
                    val = item[0] or item[1] or item[2]
                    if val.isdigit():
                        items.append(int(val))
                    else:
                        items.append(val)
                value = items
            self.consume()
        else:
            raise QueryParserError(f"Недопустимый формат значения: {val_str}")

        return op_map[op_value](col, value)

def parse_query(query_str: str, model_class):
    """Вспомогательная функция для парсинга запроса."""
    if not query_str or not query_str.strip():
        return None
    parser = SQLQueryParser(model_class)
    try:
        return parser.parse(query_str)
    except QueryParserError as e:
        raise ValueError(str(e))
