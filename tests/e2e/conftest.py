"""
Конфигурация pytest для headless E2E тестов БЕЗ Playwright.
Использует только requests + SQLAlchemy.
"""

import pytest


def pytest_configure(config):
    """Настройка pytest перед запуском."""
    # Добавляем маркеры если нужно
    config.addinivalue_line(
        "markers", "e2e: mark test as end-to-end test"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow running"
    )
