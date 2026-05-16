"""
Парсеры результатов сканирования.
"""

from .base_parser import BaseParser, TextParser, FileParser

__all__ = [
    'BaseParser',
    'TextParser',
    'FileParser',
]
