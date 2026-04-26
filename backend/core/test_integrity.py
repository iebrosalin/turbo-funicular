import hashlib
from pathlib import Path

# Путь к папке с тестами (относительно этого файла: backend/app/core -> backend -> tests)
TESTS_DIR = Path(__file__).parent.parent.parent / "tests"
# Файл для хранения эталонного хеша (будет создан в backend/app/)
HASH_FILE = Path(__file__).parent / "test_hash.txt"

class SecurityError(Exception):
    """Исключение при нарушении целостности тестов."""
    pass

def calculate_tests_hash() -> str:
    """
    Вычисляет общий SHA256 хеш всех Python-файлов в папке tests/.
    Учитывает пути файлов и их содержимое для максимальной чувствительности.
    """
    sha256_hash = hashlib.sha256()
    
    if not TESTS_DIR.exists():
        raise FileNotFoundError(f"Tests directory not found: {TESTS_DIR}")

    # Рекурсивно находим все .py файлы и сортируем их для детерминированности
    files = sorted(TESTS_DIR.rglob("*.py"))
    
    if not files:
        raise ValueError("No test files found in tests/ directory")

    for file_path in files:
        # 1. Добавляем относительный путь файла в хеш (чтобы переименование меняло хеш)
        relative_path = file_path.relative_to(TESTS_DIR)
        sha256_hash.update(str(relative_path).encode('utf-8'))
        
        # 2. Добавляем содержимое файла
        with open(file_path, "rb") as f:
            # Читаем блоками по 4KB
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
                
    return sha256_hash.hexdigest()

def verify_test_integrity() -> None:
    """
    Сравнивает текущий хеш тестов с сохраненным эталоном.
    Выбрасывает SecurityError при несовпадении.
    """
    # Если файла эталона нет, проверка пропускается (первый запуск)
    if not HASH_FILE.exists():
        return

    current_hash = calculate_tests_hash()
    
    with open(HASH_FILE, "r", encoding='utf-8') as f:
        expected_hash = f.read().strip()

    if current_hash != expected_hash:
        raise SecurityError(
            "TEST INTEGRITY CHECK FAILED!\n"
            "--------------------------------\n"
            "Обнаружены изменения в файлах тестов без обновления эталона.\n"
            "Запуск приложения заблокирован в целях безопасности.\n\n"
            f"Ожидаемый хеш: {expected_hash}\n"
            f"Текущий хеш:   {current_hash}\n\n"
            "Что делать:\n"
            "1. Если вы намеренно изменили тесты, запустите:\n"
            "   python scripts/update_test_hash.py\n"
            "2. Если изменения случайны, восстановите оригинальные файлы тестов."
        )