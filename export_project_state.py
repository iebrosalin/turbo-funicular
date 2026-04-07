#!/usr/bin/env python3
# ═══════════════════════════════════════════════════════════════
# ЭКСПОРТ ПРОЕКТА В ЕДИНЫЙ ФАЙЛ ДЛЯ КОНТЕКСТА ИИ
# Nmap Asset Manager - Полная версия
# ═══════════════════════════════════════════════════════════════

import os
import sys
from datetime import datetime

# ═══════════════════════════════════════════════════════════════
# КОНФИГУРАЦИЯ
# ═══════════════════════════════════════════════════════════════

PROJECT_NAME = "Nmap Asset Manager"
VERSION = "2.0"
EXPORT_DIR = "project_export"
OUTPUT_FILE = "PROJECT_CODEBASE.md"

# ═══════════════════════════════════════════════════════════════
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ═══════════════════════════════════════════════════════════════

def get_file_tree(startpath):
    """Генерация дерева файлов для заголовка"""
    tree = []
    skip_dirs = {'.git', '__pycache__', 'venv', EXPORT_DIR, 'scan_results', 'node_modules', '.idea', '.vscode'}
    skip_exts = {'.db', '.pyc', '.log', '.sqlite', '.png', '.jpg', '.gif', '.ico', '.woff', '.ttf', '.eot', '.svg'}
    
    for root, dirs, files in os.walk(startpath):
        dirs[:] = [d for d in dirs if d not in skip_dirs and not d.startswith('.')]
        level = root.replace(startpath, '').count(os.sep)
        indent = '    ' * level
        tree.append(f'{indent}📁 {os.path.basename(root)}/')
        subindent = '    ' * (level + 1)
        for file in sorted(files):
            ext = os.path.splitext(file)[1].lower()
            if ext not in skip_exts:
                tree.append(f'{subindent}📄 {file}')
    return '\n'.join(tree)

def export_concatenated_codebase():
    """Объединение всех файлов проекта в один Markdown-файл"""
    print(f"\n📦 Объединение проекта в {OUTPUT_FILE}...")
    
    output_path = os.path.join(EXPORT_DIR, OUTPUT_FILE)
    os.makedirs(EXPORT_DIR, exist_ok=True)
    
    # Настройки фильтрации
    skip_dirs = {'.git', '__pycache__', 'venv', EXPORT_DIR, 'scan_results', 'node_modules', '.idea', '.vscode', '__history__'}
    skip_exts = {'.db', '.pyc', '.log', '.sqlite', '.png', '.jpg', '.gif', '.ico', '.woff', '.ttf', '.eot', '.svg', '.exe', '.dll', '.so'}
    include_exts = {'.py', '.html', '.css', '.js', '.txt', '.md', '.json', '.yml', '.yaml', '.cfg', '.ini', '.toml', '.sh', '.bat', '.env', '.gitignore', '.dockerignore'}
    
    # Маппинг расширений для подсветки синтаксиса
    lang_map = {
        '.py': 'python', '.js': 'javascript', '.ts': 'typescript', '.css': 'css',
        '.html': 'html', '.htm': 'html', '.json': 'json', '.md': 'markdown',
        '.txt': 'text', '.yml': 'yaml', '.yaml': 'yaml', '.cfg': 'ini',
        '.ini': 'ini', '.toml': 'toml', '.sh': 'bash', '.bat': 'batch',
        '.env': 'text', '.gitignore': 'text', '.dockerignore': 'text'
    }
    
    file_count = 0
    total_size = 0
    files_content = []
    
    # Сбор файлов
    for root, dirs, files in os.walk("."):
        # Фильтрация директорий на месте
        dirs[:] = [d for d in dirs if d not in skip_dirs and not d.startswith('.')]
        
        for file in sorted(files):
            file_path = os.path.join(root, file)
            rel_path = os.path.relpath(file_path).replace("\\", "/")
            ext = os.path.splitext(file)[1].lower()
            
            # Пропускаем системные/бинарные файлы и сам вывод
            if ext in skip_exts or ext not in include_exts:
                continue
            if rel_path == OUTPUT_FILE or rel_path.startswith(f"{EXPORT_DIR}/"):
                continue
                
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
            except UnicodeDecodeError:
                try:
                    with open(file_path, 'r', encoding='latin-1') as f:
                        content = f.read()
                except:
                    content = "[⚠️ Файл не удалось прочитать в текстовом формате]"
            
            files_content.append((rel_path, content, ext))
            file_count += 1
            total_size += len(content.encode('utf-8'))
    
    # Запись в файл
    with open(output_path, 'w', encoding='utf-8') as out:
        # Заголовок
        out.write(f"# 📁 PROJECT CODEBASE: {PROJECT_NAME} v{VERSION}\n\n")
        out.write(f"**Дата экспорта:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        out.write(f"**Файлов включено:** {file_count}\n")
        out.write(f"**Общий размер:** {total_size / 1024:.1f} KB\n")
        out.write(f"**Инструкция для ИИ:** Используй этот файл как полный контекст проекта. Ссылайся на файлы по путям из заголовков.\n")
        out.write("---\n\n")
        
        # Дерево файлов
        out.write("## 🌳 Структура проекта\n\n```text\n")
        out.write(get_file_tree("."))
        out.write("\n```\n\n---\n\n")
        
        # Содержимое файлов
        out.write("## 📂 Исходный код\n\n")
        for rel_path, content, ext in files_content:
            lang = lang_map.get(ext, '')
            out.write(f"### 📄 `{rel_path}`\n\n")
            if lang:
                out.write(f"```{lang}\n{content}\n```\n\n")
            else:
                out.write(f"```\n{content}\n```\n\n")
        
        # Футер
        out.write("---\n\n")
        out.write(f"✅ **Экспорт завершён.** Файл содержит {file_count} файлов общим размером {total_size / 1024:.1f} KB.\n")
        out.write("💡 **Совет:** Скопируйте содержимое этого файла целиком в новое окно чата для сохранения контекста разработки.\n")
        
    print(f"✅ Создан: {output_path}")
    print(f"📊 Файлов: {file_count} | Размер: {total_size / 1024:.1f} KB")

# ═══════════════════════════════════════════════════════════════
# ЗАПУСК
# ═══════════════════════════════════════════════════════════════

def main():
    print("=" * 60)
    print(f"  {PROJECT_NAME} v{VERSION}")
    print(f"  Генерация единого контекста для ИИ")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    try:
        export_concatenated_codebase()
        print("\n" + "=" * 60)
        print("✅ ГОТОВО! Откройте файл и скопируйте его содержимое.")
        print("=" * 60)
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()