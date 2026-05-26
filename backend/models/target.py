"""
Модель целевого объекта для сканирования.
Поддерживает IP-адреса (v4/v6) и доменные имена.
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
import ipaddress


class TargetType(Enum):
    """Типы целевых объектов"""
    IPV4 = "ipv4"
    IPV6 = "ipv6"
    IPV4_NETWORK = "ipv4_network"  # CIDR для IPv4
    IPV6_NETWORK = "ipv6_network"  # CIDR для IPv6
    DOMAIN = "domain"
    UNKNOWN = "unknown"


@dataclass
class Target:
    """
    Представляет цель для сканирования.
    
    Attributes:
        value: Исходное значение (IP или домен)
        type: Автоматически определенный тип цели
        original_input: Оригинальный ввод из CSV/формы (для отслеживания)
        metadata: Дополнительные метаданные (группа, строка CSV и т.д.)
    """
    value: str
    type: TargetType = field(init=False)
    original_input: Optional[str] = None
    metadata: dict = field(default_factory=dict)
    
    def __post_init__(self):
        """Автоматическое определение типа цели после инициализации"""
        self.type = self._detect_type()
        
        # Сохраняем оригинальный ввод, если не указан
        if self.original_input is None:
            self.original_input = self.value
    
    def _detect_type(self) -> TargetType:
        """Определяет тип цели на основе значения"""
        value = self.value.strip()
        
        # Проверка на IPv4 сеть (CIDR)
        try:
            network = ipaddress.IPv4Network(value, strict=False)
            # Если это сеть с маской (не одиночный хост)
            if network.prefixlen < 32:
                return TargetType.IPV4_NETWORK
            # Если /32 - это обычный IP
            return TargetType.IPV4
        except (ipaddress.AddressValueError, ipaddress.NetmaskValueError, ValueError):
            pass
        
        # Проверка на IPv6 сеть (CIDR)
        try:
            network = ipaddress.IPv6Network(value, strict=False)
            # Если это сеть с маской (не одиночный хост)
            if network.prefixlen < 128:
                return TargetType.IPV6_NETWORK
            # Если /128 - это обычный IP
            return TargetType.IPV6
        except (ipaddress.AddressValueError, ipaddress.NetmaskValueError, ValueError):
            pass
        
        # Проверка на домен (базовая валидация)
        if self._is_valid_domain(value):
            return TargetType.DOMAIN
        
        return TargetType.UNKNOWN
    
    def _is_valid_domain(self, domain: str) -> bool:
        """
        Базовая валидация доменного имени.
        
        Правила:
        - Длина 1-253 символа
        - Состоит из меток, разделенных точками
        - Каждая метка 1-63 символа
        - Метки содержат буквы, цифры, дефисы (не начинаются/не заканчиваются на дефис)
        - Не начинается с точки
        """
        if not domain or len(domain) > 253:
            return False
        
        if domain.startswith('.') or domain.endswith('.'):
            domain = domain.strip('.')
        
        if not domain:
            return False
        
        labels = domain.split('.')
        
        # Должна быть хотя бы одна метка
        if len(labels) < 1:
            return False
        
        for label in labels:
            if not label:
                return False
            if len(label) > 63:
                return False
            if label.startswith('-') or label.endswith('-'):
                return False
            # Разрешены буквы, цифры, дефисы
            if not all(c.isalnum() or c == '-' for c in label):
                return False
        
        return True
    
    def is_ip(self) -> bool:
        """Проверяет, является ли цель IP-адресом (включая CIDR сети)"""
        return self.type in (TargetType.IPV4, TargetType.IPV6, TargetType.IPV4_NETWORK, TargetType.IPV6_NETWORK)
    
    def is_cidr(self) -> bool:
        """Проверяет, является ли цель CIDR сетью"""
        return self.type in (TargetType.IPV4_NETWORK, TargetType.IPV6_NETWORK)
    
    def is_domain(self) -> bool:
        """Проверяет, является ли цель доменным именем"""
        return self.type == TargetType.DOMAIN
    
    def is_valid(self) -> bool:
        """Проверяет валидность цели (UNKNOWN считается невалидным)"""
        return self.type != TargetType.UNKNOWN
    
    def __str__(self) -> str:
        return self.value
    
    def __hash__(self) -> int:
        return hash(self.value)
    
    def __eq__(self, other) -> bool:
        if isinstance(other, Target):
            return self.value == other.value
        return False
    
    @classmethod
    def from_string(cls, value: str, original_input: Optional[str] = None, 
                    metadata: Optional[dict] = None) -> 'Target':
        """Создает Target из строки"""
        return cls(
            value=value.strip(),
            original_input=original_input or value,
            metadata=metadata or {}
        )
    
    def to_dict(self) -> dict:
        """Конвертирует Target в словарь"""
        return {
            'value': self.value,
            'type': self.type.value,
            'original_input': self.original_input,
            'metadata': self.metadata,
            'is_valid': self.is_valid()
        }
