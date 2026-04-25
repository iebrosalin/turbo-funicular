#!/usr/bin/env python3
"""
Скрипт для обновления эталонного хеша тестов.
Запускает все тесты и только в случае их успешного прохождения обновляет хеш.
"""
import subprocess
import sys
from pathlib import Path

# Добавляем корень проекта в path, чтобы работали импорты app.core...
ROOT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT_DIR))

from app.core.test_integrity import calculate_tests_hash, HASH_FILE

def main():
    print("🛡️  ЗАПУСК ПРОЦЕДУРЫ ОБНОВЛЕНИЯ ЦЕЛОСТНОСТИ ТЕСТОВ")
    print("=" * 60)
    
    # ШАГ 1: Запуск всех тестов
    print("\n[1/3] 🧪 Запуск полного набора тестов (pytest)...")
    # Запускаем pytest от имени модуля, чтобы подхватить конфигурацию
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/", "-v", "--tb=short"],
        cwd=ROOT_DIR
    )
    
    if result.returncode != 0:
        print("\n❌ ОШИБКА: Тесты не прошли! Эталонный хеш НЕ обновлен.")
        print("Исправьте ошибки в тестах и попробуйте снова.")
        sys.exit(1)
    
    print("✅ Все тесты пройдены успешно!")
    
    # ШАГ 2: Вычисление нового хеша
    print("\n[2/3] 🔒 Вычисление SHA256 хеша файлов тестов...")
    try:
        new_hash = calculate_tests_hash()
    except Exception as e:
        print(f"\n❌ ОШИБКА при вычислении хеша: {e}")
        sys.exit(1)
    
    # ШАГ 3: Сохранение эталона
    print("\n[3/3] 💾 Сохранение нового эталонного хеша...")
    try:
        with open(HASH_FILE, "w", encoding='utf-8') as f:
            f.write(new_hash)
        print(f"✨ УСПЕХ! Эталонный хеш обновлен: {new_hash}")
        print(f"Файл сохранен: {HASH_FILE.relative_to(ROOT_DIR)}")
    except Exception as e:
        print(f"\n❌ ОШИБКА при записи файла: {e}")
        sys.exit(1)

    print("\n" + "=" * 60)
    print("Теперь приложение сможет запуститься с новыми тестами.")

if __name__ == "__main__":
    main()