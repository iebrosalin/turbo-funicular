# 📁 PROJECT CODEBASE: Nmap Asset Manager v2.0

**Дата экспорта:** 2026-04-18 19:12:18
**Файлов включено:** 44
**Общий размер:** 423.1 KB
**Инструкция для ИИ:** Используй этот файл как полный контекст проекта. Ссылайся на файлы по путям из заголовков.
---

## 🌳 Структура проекта

```text
📁 ./
    📄 .gitignore
    📄 1time.bash
    📄 LICENSE
    📄 app.py
    📄 config.py
    📄 export_project_state.py
    📄 extensions.py
    📄 full_replace_project_files.py
    📄 models.py
    📄 requirements.txt
    📄 scanner.py
    📄 utils.py
    📁 utils/
        📄 __init__.py
        📄 network_utils.py
        📄 osquery_validator.py
        📄 wazuh_api.py
    📁 routes/
        📄 __init__.py
        📄 main.py
        📄 osquery.py
        📄 scans.py
        📄 utilities.py
        📄 wazuh.py
    📁 configs/
        📁 osquery/
            📄 osquery.conf
            📁 packs/
                📄 linux_inventory.conf
                📄 windows_inventory.conf
    📁 uploads/
    📁 static/
        📁 js/
            📄 main.js
            📁 modules/
                📄 assets.js
                📄 groups.js
                📄 scans.js
                📄 theme.js
                📄 tree.js
                📄 utils.js
                📄 wazuh.js
        📁 css/
            📄 style.css
    📁 instance/
        📁 uploads/
    📁 templates/
        📄 asset_detail.html
        📄 asset_history.html
        📄 asset_taxonomy.html
        📄 base.html
        📄 create.html
        📄 edit.html
        📄 index.html
        📄 osquery_config_editor.html
        📄 osquery_dashboard.html
        📄 osquery_deploy.html
        📄 osquery_instructions.html
        📄 scans.html
        📄 utilities.html
        📁 components/
            📄 assets_rows.html
            📄 group_tree.html
            📄 modals.html
```

---

## 📂 Исходный код

### 📄 `app.py`

```python
import os
from flask import Flask
from extensions import db
from routes import register_blueprints
# Убираем прямой импорт scanner здесь, если он не нужен для конфигурации
# import scanner 

def create_app():
    app = Flask(__name__)

    # 1. Конфигурация
    basedir = os.path.abspath(os.path.dirname(__file__))
    instance_dir = os.path.join(basedir, 'instance')
    
    if not os.path.exists(instance_dir):
        os.makedirs(instance_dir)

    db_path = os.path.join(instance_dir, 'app.db')
    
    app.config['SECRET_KEY'] = 'dev-secret-key-change-in-production'
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['UPLOAD_FOLDER'] = os.path.join(basedir, 'uploads')
    app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

    # 2. Инициализация расширений (Привязка app к db)
    db.init_app(app)

    # 3. Регистрация маршрутов
    register_blueprints(app)

    # 4. Создание таблиц и начальных данных ТОЛЬКО внутри контекста
    with app.app_context():
        try:
            # Создаем таблицы
            db.create_all()
            print(f"✅ Таблицы БД созданы/проверены: {db_path}")

            # Проверка данных теперь безопасна, так как мы внутри контекста
            # и db уже инициализирован через init_app выше.
            from models import Group
            if not Group.query.first():
                root = Group(name="Root")
                db.session.add(root)
                db.session.commit()
                print("✅ Создана корневая группа 'Root'")

        except Exception as e:
            print(f"❌ Ошибка создания таблиц БД или начальных данных: {e}")
            # Пробрасываем ошибку дальше, чтобы приложение не запустилось в сломанном состоянии
            raise

    return app

if __name__ == '__main__':
    print(f"📁 Текущая директория: {os.getcwd()}")
    print("🚀 Запуск сервера...")
    
    try:
        app = create_app()
        app.run(host='0.0.0.0', port=5000, debug=True)
    except Exception as e:
        print(f"🛑 Критическая ошибка запуска: {e}")
```

### 📄 `config.py`

```python
import os
from datetime import timezone, timedelta

class Config:
    SECRET_KEY = 'super-secret-key-change-me'
    SQLALCHEMY_DATABASE_URI = 'sqlite:///assets.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
    SCAN_RESULTS_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'scan_results')
    MAX_SCAN_THREADS = 5
    # 🔥 Московское время (UTC+3)
    TIMEZONE = timezone(timedelta(hours=3))
    TIMEZONE_NAME = 'Europe/Moscow'
```

### 📄 `export_project_state.py`

```python
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
```

### 📄 `extensions.py`

```python
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

```

### 📄 `full_replace_project_files.py`

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
full_replace_project_files.py
Полная синхронизация файлов проекта Nmap Asset Manager v2.0.
Автоматически создаёт директории, бэкапит текущие файлы и перезаписывает содержимое.
"""
import os
import sys
import shutil
import argparse
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path(__file__).parent.resolve()
BACKUP_DIR = PROJECT_ROOT / "project_backups" / datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

# 📦 МАНИФЕСТ ФАЙЛОВ
PROJECT_FILES = {
    "extensions.py": """from flask_sqlalchemy import SQLAlchemy
db = SQLAlchemy()
""",
    "models.py": """import json
from datetime import datetime
from extensions import db

class Group(db.Model):
    __tablename__ = 'group'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    parent_id = db.Column(db.Integer, db.ForeignKey('group.id'), nullable=True)
    filter_query = db.Column(db.Text, nullable=True)
    is_dynamic = db.Column(db.Boolean, default=False)
    children = db.relationship('Group', backref=db.backref('parent', remote_side=[id]))
    assets = db.relationship('Asset', backref='group', lazy=True)
    def __repr__(self): return f'<Group {self.name}>'

class Asset(db.Model):
    __tablename__ = 'asset'
    id = db.Column(db.Integer, primary_key=True)
    ip_address = db.Column(db.String(50), nullable=False, index=True)
    hostname = db.Column(db.String(255))
    os_info = db.Column(db.String(255))
    status = db.Column(db.String(20), default='up')
    open_ports = db.Column(db.Text)
    last_scanned = db.Column(db.DateTime, default=datetime.utcnow)
    notes = db.Column(db.Text)
    group_id = db.Column(db.Integer, db.ForeignKey('group.id'), nullable=True)
    device_role = db.Column(db.String(100), nullable=True)
    device_tags = db.Column(db.Text, nullable=True)
    scanners_used = db.Column(db.Text, nullable=True)
    data_source = db.Column(db.String(20), default='manual')
    wazuh_agent_id = db.Column(db.String(50), nullable=True, unique=True)
    osquery_status = db.Column(db.String(20), default='offline')
    osquery_last_seen = db.Column(db.DateTime, nullable=True)
    osquery_cpu = db.Column(db.String(255))
    osquery_ram = db.Column(db.String(50))
    osquery_disk = db.Column(db.String(50))
    osquery_os = db.Column(db.String(255))
    osquery_kernel = db.Column(db.String(255))
    osquery_uptime = db.Column(db.BigInteger)
    osquery_node_key = db.Column(db.String(100), nullable=True, unique=True)
    osquery_version = db.Column(db.String(50), nullable=True)
    def __repr__(self): return f'<Asset {self.ip_address}>'

class ScanJob(db.Model):
    __tablename__ = 'scan_job'
    id = db.Column(db.Integer, primary_key=True)
    scan_type = db.Column(db.String(20), nullable=False)
    target = db.Column(db.String(500), nullable=False)
    status = db.Column(db.String(20), default='pending')
    progress = db.Column(db.Integer, default=0)
    started_at = db.Column(db.DateTime)
    completed_at = db.Column(db.DateTime)
    error_message = db.Column(db.Text)
    rustscan_output = db.Column(db.Text)
    nmap_xml_path = db.Column(db.String(500))
    nmap_grep_path = db.Column(db.String(500))
    nmap_normal_path = db.Column(db.String(500))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    current_target = db.Column(db.String(500), nullable=True)
    hosts_processed = db.Column(db.Integer, default=0)
    total_hosts = db.Column(db.Integer, default=0)
    def to_dict(self):
        return {
            'id': self.id, 'scan_type': self.scan_type, 'target': self.target,
            'status': self.status, 'progress': self.progress,
            'started_at': self.started_at.strftime('%Y-%m-%d %H:%M:%S') if self.started_at else None,
            'completed_at': self.completed_at.strftime('%Y-%m-%d %H:%M:%S') if self.completed_at else None,
            'error_message': self.error_message,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            'current_target': self.current_target,
            'hosts_processed': self.hosts_processed, 'total_hosts': self.total_hosts
        }

class ScanResult(db.Model):
    __tablename__ = 'scan_result'
    id = db.Column(db.Integer, primary_key=True)
    asset_id = db.Column(db.Integer, db.ForeignKey('asset.id'), nullable=True)
    ip_address = db.Column(db.String(50), nullable=False)
    scan_job_id = db.Column(db.Integer, db.ForeignKey('scan_job.id'))
    ports = db.Column(db.Text)
    services = db.Column(db.Text)
    os_detection = db.Column(db.String(255))
    scanned_at = db.Column(db.DateTime, default=datetime.utcnow)
    job = db.relationship('ScanJob', backref='results')
    asset = db.relationship('Asset', backref='scan_results')

class AssetChangeLog(db.Model):
    __tablename__ = 'asset_change_log'
    id = db.Column(db.Integer, primary_key=True)
    asset_id = db.Column(db.Integer, db.ForeignKey('asset.id'), nullable=False)
    changed_at = db.Column(db.DateTime, default=datetime.utcnow)
    change_type = db.Column(db.String(50), nullable=False)
    field_name = db.Column(db.String(100))
    old_value = db.Column(db.Text)
    new_value = db.Column(db.Text)
    scan_job_id = db.Column(db.Integer, db.ForeignKey('scan_job.id'))
    notes = db.Column(db.Text)
    asset = db.relationship('Asset', backref='change_log')
    scan_job = db.relationship('ScanJob', backref='change_logs')
    def to_dict(self):
        return {
            'id': self.id, 'asset_id': self.asset_id,
            'changed_at': self.changed_at.strftime('%Y-%m-%d %H:%M:%S'),
            'change_type': self.change_type, 'field_name': self.field_name,
            'old_value': json.loads(self.old_value) if self.old_value else None,
            'new_value': json.loads(self.new_value) if self.new_value else None,
            'scan_job_id': self.scan_job_id, 'notes': self.notes
        }

class ServiceInventory(db.Model):
    __tablename__ = 'service_inventory'
    id = db.Column(db.Integer, primary_key=True)
    asset_id = db.Column(db.Integer, db.ForeignKey('asset.id'), nullable=False)
    port = db.Column(db.String(20), nullable=False)
    protocol = db.Column(db.String(10))
    service_name = db.Column(db.String(100))
    product = db.Column(db.String(255))
    version = db.Column(db.String(255))
    extrainfo = db.Column(db.String(500))
    cpe = db.Column(db.String(500))
    script_output = db.Column(db.Text)
    first_seen = db.Column(db.DateTime, default=datetime.utcnow)
    last_seen = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)
    asset = db.relationship('Asset', backref='service_inventory')
    def to_dict(self):
        return {
            'id': self.id, 'port': self.port, 'protocol': self.protocol,
            'service_name': self.service_name, 'product': self.product, 'version': self.version,
            'extrainfo': self.extrainfo, 'cpe': self.cpe, 'script_output': self.script_output,
            'first_seen': self.first_seen.strftime('%Y-%m-%d %H:%M:%S'),
            'last_seen': self.last_seen.strftime('%Y-%m-%d %H:%M:%S'), 'is_active': self.is_active
        }

class ScanProfile(db.Model):
    __tablename__ = 'scan_profile'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    scan_type = db.Column(db.String(20), nullable=False)
    target_method = db.Column(db.String(10), default='ip')
    ports = db.Column(db.String(500))
    custom_args = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    def to_dict(self):
        return {
            'id': self.id, 'name': self.name, 'scan_type': self.scan_type,
            'target_method': self.target_method or 'ip', 'ports': self.ports or '',
            'custom_args': self.custom_args or '',
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M')
        }

class WazuhConfig(db.Model):
    __tablename__ = 'wazuh_config'
    id = db.Column(db.Integer, primary_key=True)
    url = db.Column(db.String(255), nullable=False, default='https://localhost:55000')
    username = db.Column(db.String(100), nullable=False, default='wazuh')
    password = db.Column(db.String(255), nullable=False, default='wazuh')
    verify_ssl = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=False)
""",
    "config.py": """import os
class Config:
    SECRET_KEY = 'super-secret-key-change-me'
    SQLALCHEMY_DATABASE_URI = 'sqlite:///assets.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
    SCAN_RESULTS_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'scan_results')
    MAX_SCAN_THREADS = 5
""",
    "app.py": """import os
from flask import Flask
from config import Config
from extensions import db
from routes import register_blueprints

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    os.makedirs(app.config['SCAN_RESULTS_FOLDER'], exist_ok=True)
    db.init_app(app)
    with app.app_context():
        from models import Group
        db.create_all()
        if not Group.query.first():
            db.session.add(Group(name="Сеть"))
            db.session.commit()
    register_blueprints(app)
    return app

if __name__ == '__main__':
    print("📁 Текущая директория:", os.getcwd())
    print("🚀 Запуск сервера...")
    app = create_app()
    app.run(debug=True, host='10.250.95.39', port=5000)
""",
    "utils.py": """import json
import os
from sqlalchemy import or_, and_
from extensions import db
from models import Asset, Group, AssetChangeLog

def detect_device_role_and_tags(ports_str, services_data=None):
    ports_set = {p.strip().split('/')[0] for p in (ports_str or '').split(',') if p.strip()}
    service_str = ' '.join([f"{s.get('name','')} {s.get('product','')} {s.get('version','')} {s.get('extrainfo','')}" for s in (services_data or [])]).lower()
    tags = []
    rules = [
        ("Windows Server", {"ports": {"445", "135", "139", "3389"}, "svc": ["microsoft-ds", "smb", "windows", "rdp"]}, 2),
        ("Linux Server", {"ports": {"22", "80", "443"}, "svc": ["openssh", "linux", "ubuntu", "centos", "apache", "nginx"]}, 2),
        ("Windows АРМ", {"ports": {"445", "3389"}, "svc": ["microsoft-ds", "rdp", "windows"]}, 1),
        ("Linux АРМ", {"ports": {"22"}, "svc": ["openssh", "linux", "ubuntu"]}, 1),
        ("Контроллер домена (AD)", {"ports": {"88", "389", "445", "636"}, "svc": ["ldap", "kpasswd", "microsoft-ds"]}, 2),
        ("База данных", {"ports": {"1433", "3306", "5432", "27017", "6379"}, "svc": ["mysql", "postgresql", "mongodb", "redis", "mssql"]}, 1),
        ("Веб-сервер", {"ports": {"80", "443", "8080", "8443"}, "svc": ["http", "nginx", "apache", "iis", "tomcat"]}, 1),
        ("Почтовый сервер", {"ports": {"25", "110", "143", "465", "587", "993"}, "svc": ["smtp", "pop3", "imap", "exchange"]}, 2),
        ("DNS Сервер", {"ports": {"53"}, "svc": ["dns", "bind", "unbound"]}, 1),
        ("Файловый сервер / NAS", {"ports": {"21", "445", "2049", "139", "873"}, "svc": ["ftp", "smb", "nfs", "rsync", "synology"]}, 1),
        ("Удаленное управление", {"ports": {"22", "23", "3389", "5900", "5901"}, "svc": ["ssh", "telnet", "rdp", "vnc"]}, 1),
        ("Принтер / МФУ", {"ports": {"515", "631", "9100"}, "svc": ["ipp", "http", "jetdirect", "printer"]}, 1),
        ("Прокси / Балансировщик", {"ports": {"3128", "8080", "1080"}, "svc": ["http-proxy", "squid", "haproxy", "nginx"]}, 1),
        ("IoT / Smart Device", {"ports": {"1883", "8883", "5683", "1900"}, "svc": ["mqtt", "coap", "upnp", "http"]}, 1),
        ("DHCP Сервер", {"ports": {"67", "68"}, "svc": ["bootps", "bootpc"]}, 1),
        ("Сетевое оборудование", {"ports": {"161", "162", "23"}, "svc": ["snmp", "telnet", "ssh", "cisco"]}, 1),
        ("Видеонаблюдение", {"ports": {"554", "8000", "37777"}, "svc": ["rtsp", "http", "dvr"]}, 1),
        ("VoIP / Телефония", {"ports": {"5060", "5061", "1720"}, "svc": ["sip", "h323"]}, 1),
        ("Сервер приложений", {"ports": {"8005", "1099", "4444", "9090"}, "svc": ["java", "jboss", "tomcat", "weblogic"]}, 1),
        ("Резервное копирование", {"ports": {"8140", "10080", "445"}, "svc": ["http", "smb", "bacula", "veeam"]}, 1),
    ]
    matched_role = "Не определено"; max_score = 0
    for role, criteria, min_match in rules:
        score = 0; current_tags = []
        port_matches = ports_set.intersection(criteria["ports"])
        if port_matches: score += len(port_matches); current_tags += [f"port:{p}" for p in port_matches]
        svc_matches = [s for s in criteria["svc"] if s in service_str]
        if svc_matches: score += len(svc_matches); current_tags += [f"svc:{s}" for s in svc_matches]
        if score >= min_match and score > max_score: max_score = score; matched_role = role; tags = current_tags
    return matched_role, json.dumps(tags)

def parse_nmap_xml(filepath):
    import xml.etree.ElementTree as ET
    tree = ET.parse(filepath); root = tree.getroot(); assets = []
    for host in root.findall('host'):
        status = host.find('status')
        if status is None or status.get('state') != 'up': continue
        addr = host.find('address'); ip = addr.get('addr') if addr is not None else 'Unknown'
        hostnames = host.find('hostnames'); hostname = 'Unknown'
        if hostnames is not None:
            name_elem = hostnames.find('hostname')
            if name_elem is not None: hostname = name_elem.get('name')
        os_info = 'Unknown'; os_elem = host.find('os')
        if os_elem is not None:
            os_match = os_elem.find('osmatch')
            if os_match is not None: os_info = os_match.get('name')
        ports = []; ports_elem = host.find('ports')
        if ports_elem is not None:
            for port in ports_elem.findall('port'):
                state = port.find('state')
                if state is not None and state.get('state') == 'open':
                    port_id = port.get('portid')
                    service = port.find('service'); service_name = service.get('name') if service is not None else ''
                    ports.append(f"{port_id}/{service_name}")
        assets.append({'ip_address': ip, 'hostname': hostname, 'os_info': os_info, 'status': 'up', 'open_ports': ', '.join(ports)})
    return assets

def build_group_tree(groups, parent_id=None):
    tree = []
    for group in groups:
        if group.parent_id == parent_id:
            children = build_group_tree(groups, group.id)
            if group.is_dynamic and group.filter_query:
                try:
                    filter_struct = json.loads(group.filter_query)
                    count_query = build_complex_query(Asset, filter_struct, Asset.query)
                    count = count_query.count()
                except: count = 0
            else: count = len(group.assets)
            tree.append({'id': group.id, 'name': group.name, 'children': children, 'count': count, 'is_dynamic': group.is_dynamic})
    return tree

def build_complex_query(model, filters_structure, base_query=None):
    if base_query is None: base_query = model.query
    if not filters_structure or 'conditions' not in filters_structure: return base_query
    logic = filters_structure.get('logic', 'AND')
    conditions = filters_structure.get('conditions', [])
    sqlalchemy_filters = []
    for item in conditions:
        if item.get('type') == 'group':
            sub_query = build_complex_query(model, item, model.query)
            ids = [a.id for a in sub_query.all()]
            if ids: sqlalchemy_filters.append(model.id.in_(ids))
            elif logic == 'AND': sqlalchemy_filters.append(model.id == -1)
        else:
            field = item.get('field'); op = item.get('op'); val = item.get('value')
            col = getattr(model, field, None)
            if col is None: continue
            if op == 'eq': sqlalchemy_filters.append(col == val)
            elif op == 'ne': sqlalchemy_filters.append(col != val)
            elif op == 'like': sqlalchemy_filters.append(col.like(f'%{val}%'))
            elif op == 'gt': sqlalchemy_filters.append(col > val)
            elif op == 'lt': sqlalchemy_filters.append(col < val)
            elif op == 'in': sqlalchemy_filters.append(col.in_(val.split(',')))
    if sqlalchemy_filters:
        if logic == 'AND': base_query = base_query.filter(and_(*sqlalchemy_filters))
        else: base_query = base_query.filter(or_(*sqlalchemy_filters))
    return base_query

def log_asset_change(asset_id, change_type, field_name, old_value, new_value, scan_job_id=None, notes=None):
    change = AssetChangeLog(asset_id=asset_id, change_type=change_type, field_name=field_name,
                            old_value=json.dumps(old_value) if old_value else None,
                            new_value=json.dumps(new_value) if new_value else None,
                            scan_job_id=scan_job_id, notes=notes)
    db.session.add(change)
""",
    "scanner.py": """import os, re, subprocess, time, json, xml.etree.ElementTree as ET
from datetime import datetime
from extensions import db
from models import ScanJob, Asset, ScanResult, ServiceInventory
from utils import log_asset_change, detect_device_role_and_tags

def update_job(job_id, **kwargs):
    try:
        with db.session.no_autoflush:
            job = ScanJob.query.get(job_id)
            if not job: return
            for k, v in kwargs.items(): setattr(job, k, v)
            db.session.commit()
    except Exception: db.session.rollback()

def parse_targets(target_str): return [t.strip() for t in re.split('[,\\s]+', target_str) if t.strip()]

def run_rustscan_scan(scan_job_id, target, custom_args=''):
    targets = parse_targets(target)
    update_job(scan_job_id, progress=5, total_hosts=len(targets), hosts_processed=0, current_target='Инициализация...')
    try:
        cmd = ['rustscan', '-a', target, '--greppable']
        cmd.extend(custom_args.split() if custom_args else [])
        if '-o' not in custom_args and '--output' not in custom_args:
            ts = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
            res_dir = os.path.join('scan_results', f'rustscan_{ts}')
            os.makedirs(res_dir, exist_ok=True)
            cmd.extend(['-o', os.path.join(res_dir, 'output.txt')])
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
        processed = 0
        for line in iter(process.stdout.readline, ''):
            db.session.remove()
            job = ScanJob.query.get(scan_job_id)
            if not job or job.status == 'stopped':
                process.terminate(); update_job(scan_job_id, status='stopped', error_message='Остановлено пользователем', completed_at=datetime.utcnow()); return
            if job.status == 'paused': time.sleep(0.5); continue
            match = re.match(r'^(\\S+)\\s+->', line)
            if match:
                processed += 1
                update_job(scan_job_id, progress=min(95, 10 + (processed/len(targets))*85), current_target=match.group(1), hosts_processed=processed)
        process.wait()
        job = ScanJob.query.get(scan_job_id)
        if not job: return
        if process.returncode == 0 and job.status != 'stopped':
            update_job(scan_job_id, progress=98, current_target='Парсинг результатов...')
            out_f = cmd[-1]
            if os.path.exists(out_f):
                with open(out_f, 'r') as f: job.rustscan_output = f.read()
            parse_rustscan_results(scan_job_id, job.rustscan_output, target)
            update_job(scan_job_id, progress=100, status='completed', current_target='Готово', completed_at=datetime.utcnow())
        elif job.status != 'stopped':
            update_job(scan_job_id, status='failed', error_message=f'Exit code: {process.returncode}', completed_at=datetime.utcnow())
    except Exception as e: update_job(scan_job_id, status='failed', error_message=str(e), completed_at=datetime.utcnow())

def run_nmap_scan(scan_job_id, target, ports=None, custom_args=''):
    targets = parse_targets(target)
    update_job(scan_job_id, progress=5, total_hosts=len(targets), hosts_processed=0, current_target='Инициализация...')
    try:
        ts = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        res_dir = os.path.join('scan_results', f'nmap_{ts}')
        os.makedirs(res_dir, exist_ok=True)
        base = os.path.join(res_dir, 'scan')
        cmd = ['nmap', target]
        cmd.extend(custom_args.split() if custom_args else [])
        if '-p' not in custom_args and ports: cmd.extend(['-p', ports])
        for def_arg in ['-sV', '-sC', '-O', '-v']:
            if def_arg not in custom_args: cmd.append(def_arg)
        if not any(a in custom_args for a in ['-oA', '-oX', '-oG', '-oN']): cmd.extend(['-oA', base])
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
        for line in iter(process.stdout.readline, ''):
            db.session.remove()
            job = ScanJob.query.get(scan_job_id)
            if not job or job.status == 'stopped':
                process.terminate(); update_job(scan_job_id, status='stopped', error_message='Остановлено пользователем', completed_at=datetime.utcnow()); return
            if job.status == 'paused':
                if os.name != 'nt':
                    os.kill(process.pid, 19)
                    while ScanJob.query.get(scan_job_id).status == 'paused': time.sleep(0.5)
                    os.kill(process.pid, 18)
                else:
                    while ScanJob.query.get(scan_job_id).status == 'paused': time.sleep(0.5)
                continue
            hm = re.search(r'Nmap scan report for (.+)', line)
            if hm: update_job(scan_job_id, current_target=hm.group(1))
            sm = re.search(r'(\\d+(?:\\.\\d+)?)%.*?(\\d+)\\s+hosts scanned', line)
            pm = re.search(r'(\\d+(?:\\.\\d+)?)%', line)
            if sm: update_job(scan_job_id, progress=int(float(sm.group(1))), hosts_processed=int(sm.group(2)))
            elif pm: update_job(scan_job_id, progress=int(float(pm.group(1))))
        process.wait()
        job = ScanJob.query.get(scan_job_id)
        if not job: return
        if process.returncode == 0 and job.status != 'stopped':
            update_job(scan_job_id, progress=98, current_target='Парсинг XML...')
            job.nmap_xml_path = f'{base}.xml'; job.nmap_grep_path = f'{base}.gnmap'; job.nmap_normal_path = f'{base}.nmap'
            if os.path.exists(job.nmap_xml_path): parse_nmap_results(scan_job_id, job.nmap_xml_path)
            update_job(scan_job_id, progress=100, status='completed', current_target='Готово', completed_at=datetime.utcnow())
        elif job.status != 'stopped': update_job(scan_job_id, status='failed', error_message=f'Exit code: {process.returncode}', completed_at=datetime.utcnow())
    except Exception as e: update_job(scan_job_id, status='failed', error_message=str(e), completed_at=datetime.utcnow())

def parse_rustscan_results(scan_job_id, output, target):
    if not output: return
    for line in output.strip().split('\\n'):
        if '->' in line:
            try:
                parts = line.split('->'); ip = parts[0].strip()
                ports_str = parts[1].strip() if len(parts)>1 else ''
                new_ports = [p.strip() for p in ports_str.split(',') if p.strip()]
                asset = Asset.query.filter_by(ip_address=ip).first()
                if not asset:
                    asset = Asset(ip_address=ip, status='up'); db.session.add(asset); db.session.flush()
                    log_asset_change(asset.id, 'asset_created', 'ip_address', None, ip, scan_job_id, 'Создан через rustscan')
                else:
                    existing = set(asset.open_ports.split(', ')) if asset.open_ports else set()
                    added, removed = set(new_ports)-existing, existing-set(new_ports)
                    for p in added: log_asset_change(asset.id, 'port_added', 'open_ports', None, p, scan_job_id)
                    for p in removed: log_asset_change(asset.id, 'port_removed', 'open_ports', p, None, scan_job_id)
                    if new_ports:
                        asset.open_ports = ', '.join(sorted((existing|set(new_ports)), key=lambda x: int(x.split('/')[0]) if '/' in x else int(x)))
                        asset.device_role, asset.device_tags = detect_device_role_and_tags(asset.open_ports)
                asset.last_scanned = datetime.utcnow()
                scanners = json.loads(asset.scanners_used) if asset.scanners_used else []
                if 'rustscan' not in scanners: scanners.append('rustscan')
                asset.scanners_used = json.dumps(scanners)
                db.session.add(ScanResult(asset_id=asset.id, ip_address=ip, scan_job_id=scan_job_id, ports=json.dumps(new_ports), scanned_at=datetime.utcnow()))
            except Exception as e: print(f"⚠️ Ошибка парсинга rustscan: {e}")
    db.session.commit()

def parse_nmap_results(scan_job_id, xml_path):
    try:
        tree = ET.parse(xml_path); root = tree.getroot()
        for host in root.findall('host'):
            st = host.find('status')
            if st is None or st.get('state') != 'up': continue
            addr = host.find('address')
            ip = addr.get('addr') if addr is not None else None
            if not ip: continue
            hostname, os_info = 'Unknown', 'Unknown'
            hn = host.find('hostnames')
            if hn is not None:
                ne = hn.find('hostname')
                if ne is not None: hostname = ne.get('name')
            oe = host.find('os')
            if oe is not None:
                om = oe.find('osmatch')
                if om is not None: os_info = om.get('name')
            ports, services = [], []
            pe = host.find('ports')
            if pe is not None:
                for port in pe.findall('port'):
                    state = port.find('state')
                    if state is not None and state.get('state') == 'open':
                        pid, proto = port.get('portid'), port.get('protocol')
                        svc = port.find('service')
                        s = {'name': svc.get('name') if svc is not None else '', 'product': svc.get('product') if svc is not None else '', 'version': svc.get('version') if svc is not None else '', 'extrainfo': svc.get('extrainfo') if svc is not None else ''}
                        pstr = f"{pid}/{proto}"; ports.append(pstr); services.append(s)
                        asset = Asset.query.filter_by(ip_address=ip).first()
                        if asset:
                            ex = ServiceInventory.query.filter_by(asset_id=asset.id, port=pstr).first()
                            if ex: ex.service_name, ex.product, ex.version, ex.extrainfo, ex.last_seen, ex.is_active = s['name'], s['product'], s['version'], s['extrainfo'], datetime.utcnow(), True
                            else:
                                db.session.add(ServiceInventory(asset_id=asset.id, port=pstr, protocol=proto, service_name=s['name'], product=s['product'], version=s['version'], extrainfo=s['extrainfo']))
                                log_asset_change(asset.id, 'service_detected', 'service_inventory', None, s['name'], scan_job_id, f'Порт {pstr}')
            asset = Asset.query.filter_by(ip_address=ip).first()
            if not asset: asset = Asset(ip_address=ip, status='up'); db.session.add(asset); db.session.flush()
            if asset.os_info != os_info and os_info != 'Unknown': log_asset_change(asset.id, 'os_changed', 'os_info', asset.os_info, os_info, scan_job_id)
            asset.hostname, asset.os_info = (hostname if hostname!='Unknown' else asset.hostname), (os_info if os_info!='Unknown' else asset.os_info)
            if ports:
                asset.open_ports = ', '.join(ports)
                asset.device_role, asset.device_tags = detect_device_role_and_tags(asset.open_ports, services)
            asset.last_scanned = datetime.utcnow()
            scanners = json.loads(asset.scanners_used) if asset.scanners_used else []
            if 'nmap' not in scanners: scanners.append('nmap')
            asset.scanners_used = json.dumps(scanners)
            db.session.add(ScanResult(asset_id=asset.id, ip_address=ip, scan_job_id=scan_job_id, ports=json.dumps(ports), services=json.dumps(services), os_detection=os_info, scanned_at=datetime.utcnow()))
        db.session.commit()
    except Exception as e: print(f"❌ Ошибка парсинга nmap XML: {e}")
""",
    "utils/osquery_validator.py": """import re, json

OSQUERY_SCHEMA = {
    "system_info": ["hostname", "cpu_brand", "cpu_type", "cpu_logical_cores", "cpu_physical_cores", "physical_memory", "hardware_vendor", "hardware_model"],
    "os_version": ["name", "version", "major", "minor", "patch", "build", "platform", "platform_like", "codename"],
    "processes": ["pid", "name", "path", "cmdline", "state", "parent", "uid", "gid", "start_time", "resident_size", "total_size"],
    "users": ["uid", "gid", "username", "description", "directory", "shell", "uuid"],
    "network_connections": ["pid", "local_address", "local_port", "remote_address", "remote_port", "state", "protocol", "family"],
    "listening_ports": ["pid", "port", "address", "protocol", "family"],
    "kernel_info": ["version", "arguments", "path", "device", "driver"],
    "uptime": ["days", "hours", "minutes", "seconds", "total_seconds"],
    "hash": ["path", "md5", "sha1", "sha256", "ssdeep", "file_size"],
    "file": ["path", "filename", "directory", "mode", "type", "size", "last_accessed", "last_modified", "last_status_change", "uid", "gid"],
    "crontab": ["uid", "minute", "hour", "day_of_month", "month", "day_of_week", "command", "path"],
    "logged_in_users": ["type", "user", "tty", "host", "time", "pid"],
    "routes": ["destination", "gateway", "mask", "mtu", "metric", "type", "flags", "interface"],
    "groups": ["gid", "groupname"]
}

def validate_osquery_query(query):
    errors, warnings = [], []
    query = query.strip().rstrip(';')
    if not re.match(r'(?i)^\\s*SELECT\\s+', query): errors.append("Запрос должен начинаться с SELECT"); return errors, warnings
    from_match = re.search(r'(?i)\\bFROM\\s+([\\w\\.]+)', query)
    if not from_match: errors.append("Отсутствует таблица в FROM"); return errors, warnings
    table_name = from_match.group(1).split('.')[0].lower()
    select_match = re.search(r'(?i)SELECT\\s+(.*?)\\s+FROM', query, re.DOTALL)
    if not select_match: errors.append("Не удалось извлечь список колонок"); return errors, warnings
    cols_str = select_match.group(1).strip()
    if cols_str == '*': warnings.append("Использование SELECT * не рекомендуется"); return errors, warnings
    cols = [c.strip().split(' as ')[0].split(' AS ')[0].strip().split('(')[-1] for c in cols_str.split(',')]
    cols = [c for c in cols if c and c != ')']
    if table_name in OSQUERY_SCHEMA:
        valid_cols = [vc.lower() for vc in OSQUERY_SCHEMA[table_name]]
        for col in cols:
            if '(' in col or col.lower() in ['true', 'false']: continue
            if col.lower() not in valid_cols: errors.append(f"Колонка '{col}' не найдена в таблице '{table_name}'")
    else: warnings.append(f"Таблица '{table_name}' отсутствует в словаре валидации.")
    return errors, warnings

def validate_osquery_config(config_dict):
    errors, warnings = [], []
    for sec in ["options", "schedule"]:
        if sec not in config_dict: errors.append(f"Отсутствует обязательный раздел: '{sec}'")
    if errors: return errors, warnings
    for name, query_obj in config_dict.get("schedule", {}).items():
        if not isinstance(query_obj, dict) or "query" not in query_obj: errors.append(f"schedule.{name}: некорректная структура"); continue
        q_errors, q_warnings = validate_osquery_query(query_obj["query"])
        for e in q_errors: errors.append(f"schedule.{name}: {e}")
        for w in q_warnings: warnings.append(f"schedule.{name}: {w}")
    return errors, warnings
""",
    "utils/wazuh_api.py": """import requests
from datetime import datetime

class WazuhAPI:
    def __init__(self, url, user, password, verify_ssl=False):
        self.url = url.rstrip('/'); self.auth = (user, password); self.verify = verify_ssl
        self.token = None; self.token_expires = None
    def _get_token(self):
        if self.token and self.token_expires and self.token_expires > datetime.utcnow(): return self.token
        try:
            res = requests.post(f"{self.url}/security/user/authenticate", auth=self.auth, verify=self.verify); res.raise_for_status()
            data = res.json(); self.token = data['data']['token']; self.token_expires = datetime.utcnow() + 800; return self.token
        except Exception as e: raise ConnectionError(f"Ошибка авторизации Wazuh: {str(e)}")
    def get_agents_page(self, limit=500, offset=0):
        token = self._get_token(); headers = {"Authorization": f"Bearer {token}"}
        params = {"limit": limit, "offset": offset, "sort": "-lastKeepAlive"}
        res = requests.get(f"{self.url}/agents", headers=headers, params=params, verify=self.verify, timeout=15); res.raise_for_status(); return res.json()
    def fetch_all_agents(self):
        all_agents = []; offset = 0
        while True:
            try:
                data = self.get_agents_page(limit=500, offset=offset)
                agents = data.get('data', {}).get('affected_items', []); all_agents.extend(agents)
                if len(agents) < 500: break
                offset += 500
            except Exception as e: raise Exception(f"Ошибка получения агентов: {str(e)}")
        return all_agents
""",
    "configs/osquery/osquery.conf": """{
  "options": {
    "config_plugin": "filesystem", "logger_plugin": "filesystem", "logger_path": "/var/log/osquery",
    "database_path": "/var/osquery/osquery.db", "disable_events": "false", "events_expiry": "3600",
    "enable_monitor": "true", "verbose": "false", "worker_threads": "2", "disable_logging": "false",
    "log_result_events": "true", "schedule_splay_percent": "10", "utc": "true", "host_identifier": "uuid"
  },
  "schedule": {
    "wazuh_system_info": {"query": "SELECT hostname, cpu_brand, physical_memory FROM system_info;", "interval": 86400},
    "wazuh_os_version": {"query": "SELECT name, version, build FROM os_version;", "interval": 86400},
    "wazuh_uptime": {"query": "SELECT days, hours, minutes, seconds FROM uptime;", "interval": 3600}
  },
  "decorators": {"load": ["SELECT uuid AS host_uuid FROM system_info;", "SELECT user AS username FROM logged_in_users ORDER BY time DESC LIMIT 1;"]}
}
""",
    "configs/osquery/packs/linux_inventory.conf": """{"queries": {"cpu_info_linux": {"query": "SELECT * FROM cpu_info;", "interval": 43200}, "disk_linux": {"query": "SELECT path, blocks_size, type FROM mounts WHERE type NOT IN ('tmpfs','devtmpfs');", "interval": 43200}}}
""",
    "configs/osquery/packs/windows_inventory.conf": """{"queries": {"cpu_info_windows": {"query": "SELECT * FROM cpu_info;", "interval": 43200}, "disk_windows": {"query": "SELECT device_id, free_space, size FROM logical_drives;", "interval": 43200}}}
""",
    "routes/__init__.py": """from .main import main_bp
from .scans import scans_bp
from .wazuh import wazuh_bp
from .osquery import osquery_bp
from .utilities import utilities_bp

def register_blueprints(app):
    app.register_blueprint(main_bp)
    app.register_blueprint(scans_bp)
    app.register_blueprint(wazuh_bp)
    app.register_blueprint(osquery_bp)
    app.register_blueprint(utilities_bp)
""",
    "routes/main.py": """from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from extensions import db
from models import Group, Asset, AssetChangeLog, ServiceInventory, ScanResult, ScanJob
from utils import build_group_tree, build_complex_query
from sqlalchemy import func
import json

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def index():
    all_groups = Group.query.all(); group_tree = build_group_tree(all_groups); assets = Asset.query.all()
    ungrouped_count = Asset.query.filter(Asset.group_id.is_(None)).count()
    current_filter = request.args.get('group_id')
    if request.args.get('ungrouped') == 'true': current_filter = 'ungrouped'
    elif not current_filter or current_filter == 'all': current_filter = 'ungrouped'
    return render_template('index.html', assets=assets, group_tree=group_tree, all_groups=all_groups, ungrouped_count=ungrouped_count, current_filter=current_filter)

@main_bp.route('/api/assets', methods=['GET'])
def get_assets_api():
    query = Asset.query
    filters_raw = request.args.get('filters'); ungrouped = request.args.get('ungrouped'); data_source = request.args.get('data_source')
    if data_source and data_source != 'all': query = query.filter(Asset.data_source == data_source)
    if ungrouped and ungrouped.lower() == 'true': query = query.filter(Asset.group_id.is_(None))
    else:
        group_id = request.args.get('group_id')
        if group_id and group_id != 'all':
            try:
                group_id_int = int(group_id)
                group = Group.query.get(group_id_int)
                if group and group.is_dynamic and group.filter_query:
                    try: query = build_complex_query(Asset, json.loads(group.filter_query), query)
                    except: query = query.filter(Asset.group_id == group_id_int)
                else: query = query.filter(Asset.group_id == group_id_int)
            except ValueError: return jsonify({'error': 'Invalid group_id'}), 400
    if filters_raw:
        try: query = build_complex_query(Asset, json.loads(filters_raw), query)
        except: pass
    assets = query.all()
    data = [{'id': a.id, 'ip': a.ip_address, 'hostname': a.hostname, 'os': a.os_info, 'ports': a.open_ports, 'group': a.group.name if a.group else 'Без группы', 'last_scan': a.last_scanned.strftime('%Y-%m-%d %H:%M'), 'source': a.data_source or 'manual'} for a in assets]
    return jsonify(data)

@main_bp.route('/api/analytics', methods=['GET'])
def get_analytics():
    filters_raw = request.args.get('filters'); group_by_field = request.args.get('group_by', 'os_info')
    query = Asset.query
    if filters_raw:
        try: query = build_complex_query(Asset, json.loads(filters_raw), query)
        except: pass
    group_col = getattr(Asset, group_by_field, Asset.os_info)
    results = db.session.query(group_col, func.count(Asset.id).label('count')).group_by(group_col).all()
    return jsonify([{'label': r[0] or 'Unknown', 'value': r[1]} for r in results])

@main_bp.route('/api/groups', methods=['POST'])
def api_create_group():
    data = request.json; name = data.get('name'); parent_id = data.get('parent_id'); filter_query = data.get('filter_query')
    is_dynamic = True if filter_query else False
    if parent_id == '': parent_id = None
    if not name: return jsonify({'error': 'Имя обязательно'}), 400
    new_group = Group(name=name, parent_id=parent_id, filter_query=filter_query, is_dynamic=is_dynamic)
    db.session.add(new_group); db.session.commit()
    return jsonify({'id': new_group.id, 'name': new_group.name, 'is_dynamic': is_dynamic}), 201

@main_bp.route('/api/groups/<int:id>', methods=['PUT'])
def api_update_group(id):
    group = Group.query.get_or_404(id); data = request.json
    if 'name' in data: group.name = data['name']
    if 'parent_id' in data:
        new_parent_id = data['parent_id']
        if new_parent_id == '': new_parent_id = None
        if new_parent_id and int(new_parent_id) == group.id: return jsonify({'error': 'Группа не может быть родителем самой себя'}), 400
        group.parent_id = new_parent_id
    if 'filter_query' in data: group.filter_query = data['filter_query'] if data['filter_query'] else None; group.is_dynamic = bool(data['filter_query'])
    db.session.commit()
    return jsonify({'success': True})

@main_bp.route('/api/groups/<int:id>', methods=['DELETE'])
def api_delete_group(id):
    group = Group.query.get_or_404(id); move_to_id = request.args.get('move_to')
    if move_to_id: Asset.query.filter_by(group_id=id).update({'group_id': move_to_id})
    db.session.delete(group); db.session.commit()
    return jsonify({'success': True})

@main_bp.route('/api/groups/tree')
def api_get_tree():
    all_groups = Group.query.all(); tree = build_group_tree(all_groups); flat_list = []
    def flatten(nodes, level=0):
        for node in nodes:
            flat_list.append({'id': node['id'], 'name': '  ' * level + node['name'], 'is_dynamic': node.get('is_dynamic', False)})
            flatten(node['children'], level + 1)
    flatten(tree)
    return jsonify({'tree': tree, 'flat': flat_list})

@main_bp.route('/groups', methods=['POST'])
def manage_groups():
    name = request.form.get('name'); parent_id = request.form.get('parent_id')
    if parent_id == '': parent_id = None
    db.session.add(Group(name=name, parent_id=parent_id)); db.session.commit()
    return redirect(url_for('main.index'))

@main_bp.route('/asset/<int:id>')
def asset_detail(id):
    asset = Asset.query.get_or_404(id); all_groups = Group.query.all()
    ports_detail = []
    if asset.open_ports:
        for port_str in asset.open_ports.split(', '):
            if '/' in port_str:
                port_id, service = port_str.split('/', 1)
                ports_detail.append({'port': port_id, 'service': service if service else 'unknown'})
    return render_template('asset_detail.html', asset=asset, ports_detail=ports_detail, all_groups=all_groups)

@main_bp.route('/asset/<int:id>/history')
def asset_history(id):
    asset = Asset.query.get_or_404(id); all_groups = Group.query.all(); group_tree = build_group_tree(all_groups)
    changes = AssetChangeLog.query.filter_by(asset_id=id).order_by(AssetChangeLog.changed_at.desc()).all()
    services = ServiceInventory.query.filter_by(asset_id=id, is_active=True).all()
    return render_template('asset_history.html', asset=asset, changes=changes, services=services, group_tree=group_tree, all_groups=all_groups)

@main_bp.route('/api/assets/<int:asset_id>/scans')
def get_asset_scans(asset_id):
    search = request.args.get('search', '').strip()
    query = db.session.query(ScanResult, ScanJob).join(ScanJob, isouter=True).filter(ScanResult.asset_id == asset_id)
    if search: query = query.filter(db.or_(ScanJob.scan_type.like(f'%{search}%'), ScanJob.status.like(f'%{search}%')))
    results = query.order_by(ScanResult.scanned_at.desc()).limit(100).all()
    return jsonify([{'id': res.id, 'scan_type': job.scan_type if job else 'unknown', 'status': job.status if job else 'completed',
        'scanned_at': res.scanned_at.strftime('%Y-%m-%d %H:%M:%S'), 'ports': json.loads(res.ports) if res.ports else [], 'os': res.os_detection or '-'} for res, job in results])

@main_bp.route('/api/assets/bulk-delete', methods=['POST'])
def bulk_delete_assets():
    data = request.json; asset_ids = data.get('ids', [])
    if not asset_ids: return jsonify({'error': 'No IDs provided'}), 400
    deleted_count = Asset.query.filter(Asset.id.in_(asset_ids)).delete(synchronize_session=False)
    db.session.commit()
    return jsonify({'success': True, 'deleted': deleted_count})

@main_bp.route('/api/assets/bulk-move', methods=['POST'])
def bulk_move_assets():
    data = request.json; asset_ids = data.get('ids', []); group_id = data.get('group_id')
    if group_id == '': group_id = None
    elif group_id: group_id = int(group_id)
    if not asset_ids: return jsonify({'error': 'No IDs provided'}), 400
    moved_count = Asset.query.filter(Asset.id.in_(asset_ids)).update({'group_id': group_id}, synchronize_session=False)
    db.session.commit()
    return jsonify({'success': True, 'moved': moved_count})
""",
    "routes/scans.py": """from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, Response, send_file
from extensions import db
from models import Group, Asset, ScanJob, ScanProfile
from utils import build_group_tree
from scanner import run_rustscan_scan, run_nmap_scan
from datetime import datetime
import os, threading, json

scans_bp = Blueprint('scans', __name__)

@scans_bp.route('/scans')
def scans_page():
    all_groups = Group.query.all(); group_tree = build_group_tree(all_groups)
    scan_jobs = ScanJob.query.order_by(ScanJob.created_at.desc()).limit(50).all()
    profiles = ScanProfile.query.order_by(ScanProfile.name).all()
    return render_template('scans.html', scan_jobs=scan_jobs, group_tree=group_tree, all_groups=all_groups, profiles=profiles)

def get_assets_for_group(group_id):
    if group_id == 'ungrouped': return Asset.query.filter(Asset.group_id.is_(None)).all(), "Без группы"
    group = Group.query.get(group_id)
    if not group: return None, None
    def get_child_group_ids(parent_id, all_groups, result=[]):
        children = [g for g in all_groups if g.parent_id == parent_id]
        for child in children: result.append(child.id); get_child_group_ids(child.id, all_groups, result)
        return result
    all_groups = Group.query.all(); group_ids = [group_id] + get_child_group_ids(group_id, all_groups)
    return Asset.query.filter(Asset.group_id.in_(group_ids)).all(), group.name

@scans_bp.route('/api/scans/rustscan', methods=['POST'])
def start_rustscan():
    data = request.json; target = data.get('target', ''); group_id = data.get('group_id'); custom_args = data.get('custom_args', '')
    if group_id:
        assets, group_name = get_assets_for_group(group_id)
        if not assets: return jsonify({'error': 'В группе нет активов'}), 400
        target = ' '.join([a.ip_address for a in assets]); target_description = f"Группа: {group_name} ({len(assets)} активов)"
    else:
        if not target: return jsonify({'error': 'Цель сканирования не указана'}), 400
        target_description = target
    scan_job = ScanJob(scan_type='rustscan', target=target_description, status='pending', rustscan_output=custom_args if custom_args else None)
    db.session.add(scan_job); db.session.commit()
    thread = threading.Thread(target=run_rustscan_scan, args=(scan_job.id, target, custom_args)); thread.daemon = True; thread.start()
    return jsonify({'success': True, 'job_id': scan_job.id, 'message': f'Rustscan запущен для {target_description}'})

@scans_bp.route('/api/scans/nmap', methods=['POST'])
def start_nmap():
    data = request.json; target = data.get('target', ''); group_id = data.get('group_id'); ports = data.get('ports', ''); custom_args = data.get('custom_args', '')
    if group_id:
        assets, group_name = get_assets_for_group(group_id)
        if not assets: return jsonify({'error': 'В группе нет активов'}), 400
        target = ' '.join([a.ip_address for a in assets]); target_description = f"Группа: {group_name} ({len(assets)} активов)"
    else:
        if not target: return jsonify({'error': 'Цель сканирования не указана'}), 400
        target_description = target
    scan_job = ScanJob(scan_type='nmap', target=target_description, status='pending', rustscan_output=f'Ports: {ports}' if ports else None)
    db.session.add(scan_job); db.session.commit()
    thread = threading.Thread(target=run_nmap_scan, args=(scan_job.id, target, ports, custom_args)); thread.daemon = True; thread.start()
    return jsonify({'success': True, 'job_id': scan_job.id, 'message': f'Nmap запущен для {target_description}'})

@scans_bp.route('/api/scans/<int:job_id>')
def get_scan_status(job_id): return jsonify(ScanJob.query.get_or_404(job_id).to_dict())

@scans_bp.route('/api/scans/<int:job_id>/results')
def get_scan_results(job_id):
    scan_job = ScanJob.query.get_or_404(job_id)
    results = [{'ip': r.ip_address, 'ports': json.loads(r.ports) if r.ports else [], 'services': json.loads(r.services) if r.services else [], 'os': r.os_detection, 'scanned_at': r.scanned_at.strftime('%Y-%m-%d %H:%M:%S')} for r in scan_job.results]
    return jsonify({'job': scan_job.to_dict(), 'results': results})

@scans_bp.route('/scans/<int:job_id>/download/<format_type>')
def download_scan_results(job_id, format_type):
    scan_job = ScanJob.query.get_or_404(job_id)
    if scan_job.scan_type == 'rustscan':
        if format_type == 'greppable':
            if not scan_job.rustscan_output: flash('Результаты недоступны', 'danger'); return redirect(url_for('scans.scans_page'))
            return Response(scan_job.rustscan_output, mimetype='text/plain', headers={'Content-Disposition': f'attachment; filename=rustscan_{datetime.utcnow().strftime("%Y%m%d_%H%M%S")}.txt'})
    elif scan_job.scan_type == 'nmap':
        file_path = None; mimetype = 'text/plain'; filename = ''
        if format_type == 'xml': file_path, mimetype, filename = scan_job.nmap_xml_path, 'application/xml', 'nmap_results.xml'
        elif format_type == 'greppable': file_path, filename = scan_job.nmap_grep_path, 'nmap_results.gnmap'
        elif format_type == 'normal': file_path, filename = scan_job.nmap_normal_path, 'nmap_results.txt'
        if file_path and os.path.exists(file_path): return send_file(file_path, mimetype=mimetype, as_attachment=True, download_name=filename)
        else: flash('Файл результатов не найден', 'danger'); return redirect(url_for('scans.scans_page'))
    flash('Неподдерживаемый формат', 'danger'); return redirect(url_for('scans.scans_page'))

@scans_bp.route('/api/scans/<int:job_id>/control', methods=['POST'])
def control_scan_job(job_id):
    data = request.json; action = data.get('action'); scan_job = ScanJob.query.get_or_404(job_id)
    try:
        if action == 'stop':
            if scan_job.status in ['running', 'paused']: scan_job.status = 'stopped'; scan_job.error_message = "Остановлено пользователем."; scan_job.completed_at = datetime.utcnow(); db.session.commit(); return jsonify({'success': True})
            return jsonify({'error': f'Нельзя остановить задание в статусе: {scan_job.status}'}), 400
        elif action == 'pause':
            if scan_job.status == 'running': scan_job.status = 'paused'; db.session.commit(); return jsonify({'success': True})
            return jsonify({'error': f'Нельзя приостановить задание в статусе: {scan_job.status}'}), 400
        elif action == 'resume':
            if scan_job.status == 'paused': scan_job.status = 'running'; db.session.commit(); return jsonify({'success': True})
            return jsonify({'error': f'Нельзя возобновить задание в статусе: {scan_job.status}'}), 400
        elif action == 'delete':
            if scan_job.status in ['pending', 'completed', 'failed', 'stopped']:
                for f in [scan_job.nmap_xml_path, scan_job.nmap_grep_path, scan_job.nmap_normal_path]:
                    if f and os.path.exists(f):
                        try: os.remove(f)
                        except: pass
                db.session.delete(scan_job); db.session.commit(); return jsonify({'success': True})
            return jsonify({'error': 'Нельзя удалить активное задание'}), 400
        return jsonify({'error': 'Неизвестная команда'}), 400
    except Exception as e: db.session.rollback(); return jsonify({'error': str(e)}), 500

@scans_bp.route('/api/scans/status')
def get_active_scans_status():
    active_jobs = ScanJob.query.filter(ScanJob.status.in_(['pending', 'running'])).order_by(ScanJob.created_at.desc()).limit(10).all()
    return jsonify({'active': [job.to_dict() for job in active_jobs], 'total_active': len(active_jobs)})

@scans_bp.route('/api/scans/profiles', methods=['GET'])
def get_scan_profiles(): return jsonify([p.to_dict() for p in ScanProfile.query.order_by(ScanProfile.name).all()])

@scans_bp.route('/api/scans/profiles', methods=['POST'])
def save_scan_profile():
    data = request.json
    if not data.get('name'): return jsonify({'error': 'Имя профиля обязательно'}), 400
    if ScanProfile.query.filter_by(name=data['name']).first(): return jsonify({'error': 'Профиль уже существует'}), 409
    profile = ScanProfile(name=data['name'], scan_type=data['scan_type'], target_method=data.get('target_method', 'ip'), ports=data.get('ports'), custom_args=data.get('custom_args'))
    db.session.add(profile); db.session.commit()
    return jsonify(profile.to_dict()), 201

@scans_bp.route('/api/scans/profiles/<int:id>', methods=['DELETE'])
def delete_scan_profile(id):
    profile = ScanProfile.query.get_or_404(id); db.session.delete(profile); db.session.commit()
    return jsonify({'success': True})
""",
    "routes/wazuh.py": """from flask import Blueprint, request, jsonify
from extensions import db
from models import Asset, WazuhConfig
from utils.wazuh_api import WazuhAPI
from datetime import datetime

wazuh_bp = Blueprint('wazuh', __name__)

@wazuh_bp.route('/api/wazuh/config', methods=['GET'])
def get_wazuh_config():
    cfg = WazuhConfig.query.first() or WazuhConfig()
    if not cfg.id: db.session.add(cfg); db.session.commit()
    return jsonify({'url': cfg.url, 'username': cfg.username, 'password': cfg.password, 'verify_ssl': cfg.verify_ssl, 'is_active': cfg.is_active})

@wazuh_bp.route('/api/wazuh/config', methods=['POST'])
def save_wazuh_config():
    data = request.json; cfg = WazuhConfig.query.first() or WazuhConfig()
    cfg.url = data.get('url', cfg.url); cfg.username = data.get('username', cfg.username)
    cfg.password = data.get('password', cfg.password); cfg.verify_ssl = data.get('verify_ssl', False); cfg.is_active = data.get('is_active', False)
    db.session.add(cfg); db.session.commit()
    return jsonify({'success': True})

@wazuh_bp.route('/api/wazuh/sync', methods=['POST'])
def sync_wazuh():
    cfg = WazuhConfig.query.first()
    if not cfg or not cfg.is_active: return jsonify({'error': 'Wazuh интеграция отключена'}), 400
    try:
        api = WazuhAPI(cfg.url, cfg.username, cfg.password, cfg.verify_ssl)
        agents = api.fetch_all_agents(); synced, updated = 0, 0
        for agent in agents:
            ip = agent.get('ip') or agent.get('registerIP')
            if not ip: continue
            asset = Asset.query.filter_by(wazuh_agent_id=agent['id']).first()
            if not asset: asset = Asset.query.filter_by(ip_address=ip).first()
            if not asset: asset = Asset(ip_address=ip, data_source='wazuh'); db.session.add(asset); db.session.flush(); synced += 1
            else: updated += 1
            asset.wazuh_agent_id = agent['id']; asset.hostname = agent.get('name') or asset.hostname
            os_data = agent.get('os', {})
            if os_data: asset.os_info = f"{os_data.get('name','')} {os_data.get('version','')}".strip() or asset.os_info
            asset.status = 'up' if agent.get('status') == 'active' else 'down'
            if agent.get('lastKeepAlive'):
                try: asset.last_scanned = datetime.fromisoformat(agent['lastKeepAlive'].replace('Z','+00:00'))
                except: pass
            asset.data_source = 'wazuh'
        db.session.commit()
        return jsonify({'success': True, 'new': synced, 'updated': updated, 'total': len(agents)})
    except Exception as e: db.session.rollback(); return jsonify({'error': str(e)}), 500
""",
    "routes/osquery.py": """from flask import Blueprint, render_template, request, jsonify, redirect, url_for
from extensions import db
from models import Asset, OSqueryInventory
from utils.osquery_validator import validate_osquery_config
import os, json
from datetime import datetime

osquery_bp = Blueprint('osquery', __name__)
CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'configs', 'osquery', 'osquery.conf')

@osquery_bp.route('/osquery')
def dashboard(): return render_template('osquery_dashboard.html', assets=Asset.query.filter(Asset.osquery_node_key.isnot(None)).all())

@osquery_bp.route('/osquery/api/register', methods=['POST'])
def register_node():
    data = request.json; ip = request.remote_addr; node_key = data.get('node_key')
    asset = Asset.query.filter_by(ip_address=ip).first()
    if not asset: asset = Asset(ip_address=ip, status='up'); db.session.add(asset); db.session.flush()
    asset.osquery_node_key = node_key; asset.osquery_status = 'pending'; db.session.commit()
    return jsonify({'status': 'registered'}), 200

@osquery_bp.route('/osquery/api/ingest', methods=['POST'])
def ingest_inventory():
    data = request.json; asset = Asset.query.filter_by(osquery_node_key=data.get('node_key')).first()
    if not asset: return jsonify({'error': 'Node key not found'}), 404
    asset.osquery_version = data.get('osquery_version', 'unknown'); asset.osquery_status = 'online'; asset.osquery_last_seen = datetime.utcnow()
    asset.osquery_cpu = data.get('cpu_model'); asset.osquery_ram = f"{int(data.get('memory_total', 0) / (1024**3))} GB" if data.get('memory_total') else None
    asset.osquery_disk = f"{int(data.get('disk_total', 0) / (1024**3))} GB" if data.get('disk_total') else None
    asset.osquery_os = data.get('os_name'); asset.osquery_kernel = data.get('kernel_version'); asset.osquery_uptime = data.get('uptime_seconds')
    db.session.add(OSqueryInventory(asset_id=asset.id, cpu_model=data.get('cpu_model'), memory_total=data.get('memory_total'), disk_total=data.get('disk_total'), os_name=data.get('os_name'), kernel_version=data.get('kernel_version'), uptime_seconds=data.get('uptime_seconds')))
    db.session.commit()
    return jsonify({'status': 'ok'}), 200

@osquery_bp.route('/osquery/deploy')
def deploy_page(): return render_template('osquery_deploy.html')

@osquery_bp.route('/osquery/instructions')
def instructions_page(): return render_template('osquery_instructions.html')

@osquery_bp.route('/osquery/config-editor')
def config_editor(): return render_template('osquery_config_editor.html')

@osquery_bp.route('/osquery/api/config', methods=['GET'])
def get_config():
    try:
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f: return jsonify(json.load(f))
    except Exception as e: return jsonify({'error': str(e)}), 500

@osquery_bp.route('/osquery/api/config/validate', methods=['POST'])
def validate_config():
    data = request.json
    if not data: return jsonify({'valid': False, 'errors': ['Пустой запрос']}), 400
    try:
        config = json.loads(json.dumps(data))
        errors, warnings = validate_osquery_config(config)
        return jsonify({'valid': len(errors) == 0, 'errors': errors, 'warnings': warnings})
    except json.JSONDecodeError as e: return jsonify({'valid': False, 'errors': [f"JSON ошибка: {str(e)}"]}), 400
    except Exception as e: return jsonify({'valid': False, 'errors': [f"Внутренняя ошибка: {str(e)}"]}), 500

@osquery_bp.route('/osquery/api/config', methods=['POST'])
def save_config():
    try:
        config = request.json
        errors, _ = validate_osquery_config(config)
        if errors: return jsonify({'error': 'Конфигурация содержит ошибки', 'errors': errors}), 400
        os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
        with open(CONFIG_PATH, 'w', encoding='utf-8') as f: json.dump(config, f, indent=2, ensure_ascii=False)
        return jsonify({'success': True})
    except Exception as e: return jsonify({'error': str(e)}), 500
""",
    "routes/utilities.py": """from flask import Blueprint, request, jsonify, Response
from datetime import datetime
import xml.etree.ElementTree as ET

utilities_bp = Blueprint('utilities', __name__)

@utilities_bp.route('/utilities')
def utilities_page():
    from models import Group; from utils import build_group_tree
    all_groups = Group.query.all()
    return render_template('utilities.html', group_tree=build_group_tree(all_groups), all_groups=all_groups)

@utilities_bp.route('/utilities/nmap-to-rustscan', methods=['POST'])
def nmap_to_rustscan():
    if 'file' not in request.files: return jsonify({'error': 'Файл не найден'}), 400
    file = request.files['file']
    if file.filename == '': return jsonify({'error': 'Файл не выбран'}), 400
    if not file.filename.endswith('.xml'): return jsonify({'error': 'Требуется XML файл'}), 400
    try:
        tree = ET.parse(file.stream); root = tree.getroot()
        ips = [addr.get('addr') for host in root.findall('host') if (status := host.find('status')) is not None and status.get('state') == 'up' and (addr := host.find('address')) is not None and addr.get('addr')]
        if not ips: return jsonify({'error': 'Не найдено активных хостов'}), 400
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        return Response('\\n'.join(ips), mimetype='text/plain', headers={'Content-Disposition': f'attachment; filename=rustscan_targets_{timestamp}.txt'})
    except Exception as e: return jsonify({'error': f'Ошибка: {str(e)}'}), 500

@utilities_bp.route('/utilities/extract-ports', methods=['POST'])
def extract_ports():
    if 'file' not in request.files: return jsonify({'error': 'Файл не найден'}), 400
    file = request.files['file']
    if file.filename == '': return jsonify({'error': 'Файл не выбран'}), 400
    try:
        tree = ET.parse(file.stream); root = tree.getroot()
        all_ports, host_ports = set(), {}
        for host in root.findall('host'):
            status = host.find('status')
            if status is not None and status.get('state') == 'up':
                addr = host.find('address'); ip = addr.get('addr') if addr is not None else 'unknown'
                ports = []; ports_elem = host.find('ports')
                if ports_elem is not None:
                    for port in ports_elem.findall('port'):
                        state = port.find('state')
                        if state is not None and state.get('state') == 'open':
                            port_id, protocol = port.get('portid'), port.get('protocol')
                            service = port.find('service'); service_name = service.get('name') if service is not None else ''
                            port_str = f"{port_id}/{protocol}" + (f" ({service_name})" if service_name else '')
                            ports.append(port_str); all_ports.add(port_id)
                if ports: host_ports[ip] = ports
        content = "="*60 + "\\nNMAP PORTS EXTRACTION REPORT\\n" + f"Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}\\n" + "="*60 + "\\n\\n"
        content += f"Total hosts: {len(host_ports)}\\nUnique ports: {len(all_ports)}\\n\\n"
        content += "-"*60 + "\\nUNIQUE PORTS (for rustscan -p):\\n" + "-"*60 + "\\n" + ','.join(sorted(all_ports, key=int)) + "\\n\\n"
        content += "-"*60 + "\\nHOSTS WITH PORTS:\\n" + "-"*60 + "\\n"
        for ip, ports in host_ports.items(): content += f"\\n{ip}:\\n" + "".join(f"  - {p}\\n" for p in ports)
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        return Response(content, mimetype='text/plain', headers={'Content-Disposition': f'attachment; filename=nmap_ports_report_{timestamp}.txt'})
    except Exception as e: return jsonify({'error': f'Ошибка: {str(e)}'}), 500
""",
    "static/css/style.css": """/* ═══════════════════════════════════════════════════════════════
   BOOTSTRAP 5 THEME - LIGHT & DARK MODE
   ═══════════════════════════════════════════════════════════════ */
:root {
    --bs-primary: #0d6efd; --bs-secondary: #6c757d; --bs-success: #198754; --bs-info: #0dcaf0; --bs-warning: #ffc107; --bs-danger: #dc3545;
    --bg-body: #f8f9fa; --bg-card: #ffffff; --bg-sidebar: #ffffff; --bg-hover: #f1f3f5; --bg-input: #ffffff;
    --text-primary: #212529; --text-secondary: #6c757d; --text-muted: #adb5bd;
    --border-color: #dee2e6; --shadow-sm: 0 0.125rem 0.25rem rgba(0,0,0,0.075); --shadow-md: 0 0.5rem 1rem rgba(0,0,0,0.15);
    --font-primary: system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
}
[data-bs-theme="dark"] {
    --bs-primary: #3d8bfd; --bs-secondary: #6c757d; --bs-success: #20c997; --bs-info: #6edff6; --bs-warning: #ffda6a; --bs-danger: #ea868f;
    --bg-body: #212529; --bg-card: #2b3035; --bg-sidebar: #2b3035; --bg-hover: #343a40; --bg-input: #2b3035;
    --text-primary: #f8f9fa; --text-secondary: #adb5bd; --text-muted: #6c757d;
    --border-color: #495057; --shadow-sm: 0 0.125rem 0.25rem rgba(0,0,0,0.3); --shadow-md: 0 0.5rem 1rem rgba(0,0,0,0.4);
}
body { background-color: var(--bg-body); color: var(--text-primary); font-family: var(--font-primary); transition: background-color 0.3s ease, color 0.3s ease; }
::-webkit-scrollbar { width: 8px; } ::-webkit-scrollbar-track { background: var(--bg-body); } ::-webkit-scrollbar-thumb { background: var(--bs-secondary); border-radius: 4px; }
.sidebar { min-height: 100vh; background: var(--bg-sidebar); border-right: 1px solid var(--border-color); transition: all 0.3s ease; }
.navbar { background: var(--bg-card) !important; border: 1px solid var(--border-color); border-radius: 0.5rem; box-shadow: var(--shadow-sm); }
.card { background: var(--bg-card); border: 1px solid var(--border-color); border-radius: 0.5rem; box-shadow: var(--shadow-sm); transition: all 0.3s ease; }
.table { color: var(--text-primary); } .table thead { background: var(--bg-body); border-bottom: 2px solid var(--border-color); }
.form-control, .form-select { background: var(--bg-input); border: 1px solid var(--border-color); color: var(--text-primary); }
.tree-node { cursor: pointer; padding: 0.5rem 0.75rem; border-radius: 0.375rem; border-left: 3px solid transparent; color: var(--text-secondary); }
.tree-node:hover { background-color: var(--bg-hover); border-left-color: var(--bs-primary); color: var(--text-primary); }
.tree-node.active { background: rgba(13, 110, 253, 0.1); border-left-color: var(--bs-primary); color: var(--bs-primary); }
.context-menu { display: none; position: absolute; z-index: 1050; min-width: 220px; background: var(--bg-card); border: 1px solid var(--border-color); box-shadow: var(--shadow-md); border-radius: 0.5rem; padding: 0.5rem 0; }
.context-menu-item { display: flex; align-items: center; gap: 0.625rem; width: 100%; padding: 0.5rem 0.875rem; color: var(--text-primary); text-decoration: none; background: transparent; border: 0; cursor: pointer; }
.context-menu-item:hover { background: var(--bg-hover); color: var(--bs-primary); }
.filter-group { border: 1px solid var(--border-color); padding: 1rem; border-radius: 0.5rem; margin-bottom: 0.75rem; background: var(--bg-card); position: relative; }
.filter-condition { display: flex; gap: 0.5rem; align-items: center; margin-bottom: 0.5rem; background: var(--bg-body); padding: 0.5rem; border-radius: 0.375rem; }
@media (max-width: 768px) { .sidebar { display: none !important; } }
""",
    "static/js/main.js": """// ═══════════════════════════════════════════════════════════════
// ГЛОБАЛЬНЫЕ ПЕРЕМЕННЫЕ
// ═══════════════════════════════════════════════════════════════
let currentGroupId = null; let contextMenu = null;
let editModal, moveModal, deleteModal, bulkDeleteModalInstance;
let lastSelectedIndex = -1; let selectedAssetIds = new Set();

const FILTER_FIELDS = [
    { value: 'ip_address', text: 'IP Адрес' }, { value: 'hostname', text: 'Hostname' },
    { value: 'os_info', text: 'ОС (Сканирование)' }, { value: 'device_role', text: 'Роль устройства' },
    { value: 'open_ports', text: 'Открытые порты' }, { value: 'status', text: 'Статус' },
    { value: 'notes', text: 'Заметки' }, { value: 'osquery_status', text: 'Статус OSquery' },
    { value: 'osquery_os', text: 'ОС (OSquery)' }, { value: 'scanners_used', text: 'Сканеры (JSON)' }
];
const FILTER_OPS = [
    { value: 'eq', text: '=' }, { value: 'ne', text: '≠' }, { value: 'like', text: 'содержит' }, { value: 'in', text: 'в списке' }
];

// ═══════════════════════════════════════════════════════════════
// ТЕМА & ГРУППЫ
// ═══════════════════════════════════════════════════════════════
function initTheme() {
    const savedTheme = localStorage.getItem('theme') || 'light';
    document.documentElement.setAttribute('data-bs-theme', savedTheme === 'dark' ? 'dark' : 'light');
    updateThemeIcon(savedTheme);
}
function toggleTheme() {
    const html = document.documentElement; const newTheme = html.getAttribute('data-bs-theme') === 'dark' ? 'light' : 'dark';
    document.body.classList.add('theme-transition'); html.setAttribute('data-bs-theme', newTheme); localStorage.setItem('theme', newTheme);
    updateThemeIcon(newTheme); setTimeout(() => document.body.classList.remove('theme-transition'), 300);
}
function updateThemeIcon(theme) {
    const toggle = document.querySelector('.theme-toggle'); if (!toggle) return;
    toggle.querySelector('.bi-moon').style.display = theme === 'dark' ? 'none' : 'block';
    toggle.querySelector('.bi-sun').style.display = theme === 'dark' ? 'block' : 'none';
}
function initTreeTogglers() {
    const groupTree = document.getElementById('group-tree'); if (!groupTree) return;
    const newGroupTree = groupTree.cloneNode(true); groupTree.parentNode.replaceChild(newGroupTree, groupTree);
    newGroupTree.addEventListener('click', function(e) {
        const treeNode = e.target.closest('.tree-node'); if (!treeNode) return;
        if (e.target.classList.contains('caret') || e.target.closest('.caret')) {
            e.preventDefault(); e.stopPropagation();
            const nested = treeNode.querySelector(".nested");
            if (nested) { nested.classList.toggle("active"); const caret = treeNode.querySelector('.caret'); if (caret) caret.classList.toggle("caret-down"); }
            return;
        }
        filterByGroup(treeNode.dataset.id);
    });
}
function filterByGroup(groupId) {
    document.querySelectorAll('.tree-node').forEach(el => el.classList.remove('active'));
    const activeNode = document.querySelector(`.tree-node[data-id="${groupId}"]`);
    if (activeNode) activeNode.classList.add('active');
    fetch(`/api/assets?group_id=${groupId === 'ungrouped' ? '' : groupId}&ungrouped=${groupId === 'ungrouped'}`)
        .then(r => r.json()).then(data => renderAssets(data)).catch(console.error);
}

// ═══════════════════════════════════════════════════════════════
// ВЫДЕЛЕНИЕ & ФИЛЬТРЫ
// ═══════════════════════════════════════════════════════════════
function initAssetSelection() {
    const tbody = document.getElementById('assets-body'); if (!tbody) return;
    const selAll = document.getElementById('select-all');
    if(selAll) selAll.addEventListener('change', function() {
        document.querySelectorAll('.asset-checkbox').forEach(cb => {
            cb.checked = this.checked; toggleRowSelection(cb.closest('tr'), this.checked);
            if(this.checked) selectedAssetIds.add(cb.value); else selectedAssetIds.delete(cb.value);
        });
        lastSelectedIndex = this.checked ? getRowIndex(document.querySelectorAll('.asset-checkbox').pop().closest('tr')) : -1;
        updateBulkToolbar(); updateSelectAllCheckbox();
    });
    tbody.addEventListener('change', e => { if(e.target.classList.contains('asset-checkbox')) handleCheckboxChange(e.target); });
    tbody.addEventListener('click', e => {
        const row = e.target.closest('.asset-row'); if(!row || e.target.closest('a, button, .asset-checkbox')) return;
        const cb = row.querySelector('.asset-checkbox');
        if(cb) { if(e.shiftKey && lastSelectedIndex >= 0) { e.preventDefault(); selectRange(lastSelectedIndex, getRowIndex(row)); } else { cb.checked = !cb.checked; handleCheckboxChange(cb); } }
    });
}
function handleCheckboxChange(cb) {
    const row = cb.closest('tr'); const id = cb.value; const checked = cb.checked;
    toggleRowSelection(row, checked);
    if(checked) { selectedAssetIds.add(id); lastSelectedIndex = getRowIndex(row); }
    else { selectedAssetIds.delete(id); if(lastSelectedIndex === getRowIndex(row)) lastSelectedIndex = -1; }
    updateBulkToolbar(); updateSelectAllCheckbox();
}
function toggleRowSelection(row, isSel) { if(isSel) row.classList.add('selected'); else row.classList.remove('selected'); }
function getRowIndex(row) { return Array.from(document.querySelectorAll('#assets-body .asset-row')).indexOf(row); }
function selectRange(start, end) {
    const [s, e] = start <= end ? [start, end] : [end, start];
    document.querySelectorAll('#assets-body .asset-row').forEach((row, i) => {
        if(i >= s && i <= e) {
            const cb = row.querySelector('.asset-checkbox');
            if(cb && !cb.checked) { cb.checked = true; toggleRowSelection(row, true); selectedAssetIds.add(cb.value); }
        }
    }); updateBulkToolbar(); updateSelectAllCheckbox();
}
function clearSelection() {
    document.querySelectorAll('#assets-body .asset-checkbox:checked').forEach(cb => { cb.checked = false; toggleRowSelection(cb.closest('tr'), false); selectedAssetIds.delete(cb.value); });
    lastSelectedIndex = -1; updateBulkToolbar(); updateSelectAllCheckbox();
}
function updateSelectAllCheckbox() {
    const selAll = document.getElementById('select-all'); const cbs = document.querySelectorAll('#assets-body .asset-checkbox');
    const checked = document.querySelectorAll('#assets-body .asset-checkbox:checked').length;
    if(selAll && cbs.length > 0) { selAll.checked = checked === cbs.length; selAll.indeterminate = checked > 0 && checked < cbs.length; }
}
function updateBulkToolbar() {
    const tb = document.getElementById('bulk-toolbar'); const c = selectedAssetIds.size;
    tb.style.display = c > 0 ? 'flex' : 'none'; document.getElementById('selected-count').textContent = c;
}
function confirmBulkDelete() {
    if(selectedAssetIds.size === 0) return;
    document.getElementById('bulk-delete-count').textContent = selectedAssetIds.size;
    if(bulkDeleteModalInstance) bulkDeleteModalInstance.show();
}
async function executeBulkDelete() {
    const ids = Array.from(selectedAssetIds);
    await fetch('/api/assets/bulk-delete', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ids}) });
    clearSelection(); if(bulkDeleteModalInstance) bulkDeleteModalInstance.hide(); location.reload();
}

// ═══════════════════════════════════════════════════════════════
// КОНСТРУКТОР ФИЛЬТРОВ
// ═══════════════════════════════════════════════════════════════
function createConditionElement() {
    const div = document.createElement('div'); div.className = 'filter-condition'; div.dataset.type = 'condition';
    div.innerHTML = `<input type="text" class="form-control form-control-sm f-field" list="filter-fields-list" placeholder="Поле..." style="width:160px">
        <select class="form-select form-select-sm f-op" style="width:120px">${FILTER_OPS.map(o=>`<option value="${o.value}">${o.text}</option>`).join('')}</select>
        <input type="text" class="form-control form-control-sm f-val" placeholder="Значение" style="flex:1">
        <button class="btn btn-sm btn-outline-danger" onclick="this.parentElement.remove()">×</button>`;
    return div;
}
function createGroupElement() {
    const g = document.createElement('div'); g.className = 'filter-group'; g.dataset.type = 'group';
    g.innerHTML = `<div class="d-flex justify-content-between mb-2"><span class="badge bg-primary" onclick="this.textContent=this.textContent==='AND'?'OR':'AND'">AND</span><button class="btn btn-sm btn-close" onclick="this.closest('.filter-group').remove()"></button></div><div class="filter-group-content"></div><button class="btn btn-xs btn-outline-primary mt-1" onclick="this.closest('.filter-group').querySelector('.filter-group-content').appendChild(createConditionElement())">+ Условие</button>`;
    return g;
}
function initFilterRoot() {
    const r = document.getElementById('filter-root');
    if(r && !r.querySelector('.filter-group-content')) { r.innerHTML = '<div class="filter-group-content"></div>'; r.appendChild(createConditionElement()); }
}
function initFilterFieldDatalist() {
    if(!document.getElementById('filter-fields-list')) {
        const dl = document.createElement('datalist'); dl.id = 'filter-fields-list';
        dl.innerHTML = FILTER_FIELDS.map(f => `<option value="${f.value}">${f.text}</option>`).join('');
        document.body.appendChild(dl);
    }
}
function buildFilterJSON() {
    const root = document.getElementById('filter-root'); if(!root) return {logic:'AND', conditions:[]};
    const logic = root.querySelector('.badge')?.textContent || 'AND'; const conds = [];
    root.querySelectorAll('.filter-condition').forEach(c => {
        conds.push({field: c.querySelector('.f-field').value.trim(), op: c.querySelector('.f-op').value, value: c.querySelector('.f-val').value.trim()});
    });
    return {logic, conditions: conds};
}
function applyFilters() {
    const valid = new Set(FILTER_FIELDS.map(f=>f.value)); let err = false;
    document.querySelectorAll('.filter-condition').forEach(c => {
        const v = c.querySelector('.f-field').value.trim();
        if(!valid.has(v)) { c.classList.add('border-danger'); err = true; } else c.classList.remove('border-danger');
    });
    if(err) { alert('⚠️ Проверьте имена полей.'); return; }
    fetch(`/api/assets?filters=${encodeURIComponent(JSON.stringify(buildFilterJSON()))}`).then(r=>r.json()).then(renderAssets);
}
function resetFilters() { document.getElementById('filter-root').querySelector('.filter-group-content').innerHTML = ''; document.getElementById('filter-root').appendChild(createConditionElement()); loadAssets(); }
function loadAssets() { fetch('/api/assets').then(r=>r.json()).then(renderAssets); }

// ═══════════════════════════════════════════════════════════════
// РЕНДЕР & МОДАЛКИ
// ═══════════════════════════════════════════════════════════════
window.renderAssets = function(data) {
    const tb = document.getElementById('assets-body'); if(!tb) return;
    tb.innerHTML = ''; clearSelection();
    if(data.length===0) { tb.innerHTML='<tr><td colspan="7" class="text-center py-4 text-muted"><i class="bi bi-inbox fs-1 d-block mb-2"></i>Ничего не найдено</td></tr>'; return; }
    data.forEach(a => {
        const tr = document.createElement('tr'); tr.className='asset-row'; tr.dataset.assetId=a.id;
        tr.innerHTML=`<td><input type="checkbox" class="form-check-input asset-checkbox" value="${a.id}"></td>
            <td><a href="/asset/${a.id}"><strong>${a.ip}</strong></a></td><td>${a.hostname||'—'}</td>
            <td><span class="text-muted small">${a.os||'—'}</span></td><td><small class="text-muted">${a.ports||'—'}</small></td>
            <td><span class="badge bg-light text-dark border">${a.group}</span></td>
            <td><a href="/asset/${a.id}" class="btn btn-sm btn-outline-info"><i class="bi bi-eye"></i></a></td>`;
        tb.appendChild(tr);
    });
};

// ═══════════════════════════════════════════════════════════════
// WAZUH & ПРОФИЛИ
// ═══════════════════════════════════════════════════════════════
document.getElementById('data-source-filter')?.addEventListener('change', function() {
    const p = new URLSearchParams(window.location.search); p.set('data_source', this.value); window.location.search = p.toString();
});
async function saveWazuhConfig() {
    const btn = event.target; btn.disabled = true; btn.textContent = '⏳ Синхронизация...';
    const st = document.getElementById('waz-status');
    const body = { url: document.getElementById('waz-url').value, username: document.getElementById('waz-user').value, password: document.getElementById('waz-pass').value, verify_ssl: document.getElementById('waz-ssl').checked, is_active: document.getElementById('waz-active').checked };
    await fetch('/api/wazuh/config', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body) });
    const res = await fetch('/api/wazuh/sync', { method: 'POST' }); const d = await res.json();
    if(res.ok) { st.innerHTML=`<span class="text-success">✅ +${d.new} | обн. ${d.updated}</span>`; setTimeout(()=>location.reload(), 1500); }
    else { st.innerHTML=`<span class="text-danger">❌ ${d.error}</span>`; }
    btn.disabled = false; btn.textContent = '💾 Сохранить и синхронизировать';
}
document.getElementById('wazuhModal')?.addEventListener('show.bs.modal', async () => {
    const c = await (await fetch('/api/wazuh/config')).json();
    document.getElementById('waz-url').value = c.url; document.getElementById('waz-user').value = c.username;
    document.getElementById('waz-pass').value = c.password; document.getElementById('waz-ssl').checked = c.verify_ssl; document.getElementById('waz-active').checked = c.is_active;
});

// ═══════════════════════════════════════════════════════════════
// ИНИЦИАЛИЗАЦИЯ
// ═══════════════════════════════════════════════════════════════
document.addEventListener('DOMContentLoaded', () => {
    initTheme(); initFilterFieldDatalist(); initTreeTogglers(); initFilterRoot(); initAssetSelection();
    contextMenu = document.getElementById('group-context-menu');
    const e = document.getElementById('groupEditModal'); const m = document.getElementById('groupMoveModal');
    const d = document.getElementById('groupDeleteModal'); const b = document.getElementById('bulkDeleteModal');
    if(e) editModal = new bootstrap.Modal(e); if(m) moveModal = new bootstrap.Modal(m);
    if(d) deleteModal = new bootstrap.Modal(d); if(b) bulkDeleteModalInstance = new bootstrap.Modal(b);
    document.addEventListener('keydown', e => { if(e.ctrlKey && e.key==='a' && !['INPUT','TEXTAREA','SELECT'].includes(e.target.tagName)) { e.preventDefault(); document.querySelectorAll('#assets-body .asset-checkbox').forEach(cb => { cb.checked=true; toggleRowSelection(cb.closest('tr'),true); selectedAssetIds.add(cb.value); }); updateBulkToolbar(); updateSelectAllCheckbox(); } });
});
""",
    "templates/base.html": """<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8"> <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}Asset Manager{% endblock %}</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.10.0/font/bootstrap-icons.css" rel="stylesheet">
    <link href="{{ url_for('static', filename='css/style.css') }}" rel="stylesheet">
    {% block extra_css %}{% endblock %}
</head>
<body>
    {% block content %}{% endblock %}
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
    <script src="{{ url_for('static', filename='js/main.js') }}"></script>
    {% block extra_js %}{% endblock %}
</body>
</html>
""",
    "templates/index.html": """<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8"> <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Asset Manager</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.10.0/font/bootstrap-icons.css" rel="stylesheet">
    <link href="{{ url_for('static', filename='css/style.css') }}" rel="stylesheet">
</head>
<body>
    <div class="container-fluid">
        <div class="row">
            <div class="col-md-3 col-lg-2 sidebar p-3 d-none d-md-block">{% include 'components/group_tree.html' %}</div>
            <div class="col-md-9 col-lg-10 p-4">
                <nav class="navbar navbar-light mb-4 px-3">
                    <span class="navbar-brand mb-0 h1"><i class="bi bi-shield-check"></i> Asset Manager</span>
                    <div class="d-flex align-items-center">
                        <button class="theme-toggle me-2" onclick="toggleTheme()"><i class="bi bi-moon"></i><i class="bi bi-sun"></i></button>
                        <a href="{{ url_for('scans.scans_page') }}" class="btn btn-outline-dark me-2"><i class="bi bi-wifi"></i> Сканирования</a>
                        <button class="btn btn-primary me-2" data-bs-toggle="modal" data-bs-target="#scanModal"><i class="bi bi-upload"></i> Импорт</button>
                        <button class="btn btn-outline-dark me-2" data-bs-toggle="collapse" data-bs-target="#filterPanel"><i class="bi bi-funnel"></i> Фильтры</button>
                        <select id="data-source-filter" class="form-select form-select-sm" style="width: 160px;">
                            <option value="all">Все источники</option><option value="wazuh">🛡️ Wazuh</option><option value="osquery">📦 OSquery</option><option value="scanning">🔍 Сканирование</option><option value="manual">✏️ Ручной</option>
                        </select>
                    </div>
                </nav>
                <div class="collapse mb-4" id="filterPanel">
                    <div class="card card-body">
                        <div class="d-flex justify-content-between mb-3"><h6 class="mb-0">Конструктор запросов</h6><div><button class="btn btn-sm btn-primary" onclick="applyFilters()">Применить</button><button class="btn btn-sm btn-secondary" onclick="resetFilters()">Сброс</button></div></div>
                        <div id="filter-root" class="filter-group"></div>
                    </div>
                </div>
                {% with messages = get_flashed_messages(with_categories=true) %}{% if messages %}{% for c, m in messages %}<div class="alert alert-{{ c }} alert-dismissible fade show">{{ m }}<button type="button" class="btn-close" data-bs-dismiss="alert"></button></div>{% endfor %}{% endif %}{% endwith %}
                <div class="card">
                    <div class="card-header d-flex justify-content-between align-items-center" id="bulk-toolbar" style="display: none;">
                        <div class="d-flex align-items-center gap-2"><span class="badge bg-primary" id="selected-count">0</span><span class="text-muted small">выбрано</span></div>
                        <div class="d-flex gap-2"><button class="btn btn-sm btn-outline-secondary" onclick="clearSelection()"><i class="bi bi-x-lg"></i> Снять</button><button class="btn btn-sm btn-danger" onclick="confirmBulkDelete()"><i class="bi bi-trash"></i> Удалить</button></div>
                    </div>
                    <div class="card-body p-0">
                        <table class="table table-hover mb-0">
                            <thead class="table-light"><tr><th style="width:40px"><input type="checkbox" class="form-check-input" id="select-all"></th><th>IP</th><th>Hostname</th><th>OS</th><th>Порты</th><th>Группа</th><th>Действия</th></tr></thead>
                            <tbody id="assets-body">{% include 'components/assets_rows.html' %}</tbody>
                        </table>
                    </div>
                </div>
            </div>
        </div>
    </div>
    {% include 'components/modals.html' %}
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>
""",
    "templates/asset_detail.html": """<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8"> <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ asset.ip_address }}</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.10.0/font/bootstrap-icons.css" rel="stylesheet">
    <link href="{{ url_for('static', filename='css/style.css') }}" rel="stylesheet">
</head>
<body>
    <div class="container-fluid">
        <div class="row">
            <div class="col-md-3 col-lg-2 sidebar p-3 d-none d-md-block"><h5 class="mb-3"><i class="bi bi-folder-tree"></i> Группы</h5><div id="group-tree">{% include 'components/group_tree.html' %}</div></div>
            <div class="col-md-9 col-lg-10 p-4">
                <nav class="navbar navbar-light mb-4 px-3"><div class="d-flex align-items-center"><a href="{{ url_for('main.index') }}" class="btn btn-outline-dark me-3"><i class="bi bi-arrow-left"></i> Назад</a><span class="navbar-brand mb-0 h1"><i class="bi bi-pc-display"></i> {{ asset.ip_address }}</span></div><div class="d-flex align-items-center"><button class="theme-toggle me-2" onclick="toggleTheme()"><i class="bi bi-moon"></i><i class="bi bi-sun"></i></button><a href="{{ url_for('main.asset_history', id=asset.id) }}" class="btn btn-outline-info me-2"><i class="bi bi-clock-history"></i> История</a><a href="{{ url_for('main.delete_asset', id=asset.id) }}" class="btn btn-outline-danger" onclick="return confirm('Удалить?')"><i class="bi bi-trash"></i></a></div></nav>
                <div class="row">
                    <div class="col-lg-8">
                        <div class="card mb-4 {% if asset.status=='up' %}border-success{% else %}border-danger{% endif %}"><div class="card-body d-flex align-items-center justify-content-between"><div class="d-flex align-items-center"><span class="status-indicator-large {% if asset.status=='up' %}bg-success{% else %}bg-danger{% endif %} rounded-circle me-3" style="width:12px;height:12px"></span><div><h4 class="mb-0">{% if asset.status=='up' %}<span class="text-success">Активен</span>{% else %}<span class="text-danger">Не доступен</span>{% endif %}</h4><small class="text-muted">Последнее сканирование: {{ asset.last_scanned.strftime('%Y-%m-%d %H:%M') }}</small></div></div><span class="badge {% if asset.status=='up' %}bg-success{% else %}bg-danger{% endif %} fs-6">{{ asset.status.upper() }}</span></div></div>
                        <div class="card mb-4"><div class="card-header"><i class="bi bi-info-circle"></i> Информация</div><div class="card-body"><div class="row"><div class="col-md-6 mb-3"><div class="text-muted small text-uppercase">IP Адрес</div><div class="fw-medium"><i class="bi bi-globe"></i> {{ asset.ip_address }}</div></div><div class="col-md-6 mb-3"><div class="text-muted small text-uppercase">Hostname</div><div class="fw-medium"><i class="bi bi-pc-display"></i> {{ asset.hostname or 'Не определён' }}</div></div><div class="col-md-6 mb-3"><div class="text-muted small text-uppercase">ОС</div><div class="fw-medium"><i class="bi bi-windows"></i> {{ asset.os_info or 'Не определена' }}</div></div></div></div></div>
                    </div>
                    <div class="col-lg-4">
                        <div class="card mb-4"><div class="card-header"><i class="bi bi-lightning"></i> Действия</div><div class="card-body"><div class="d-grid gap-2"><a href="#" class="btn btn-outline-primary" onclick="navigator.clipboard.writeText('{{ asset.ip_address }}');alert('IP скопирован');return false"><i class="bi bi-clipboard"></i> Копировать IP</a><a href="ssh://{{ asset.ip_address }}" class="btn btn-outline-dark" target="_blank"><i class="bi bi-terminal"></i> SSH</a><form action="{{ url_for('main.scan_asset_nmap', id=asset.id) }}" method="POST" class="d-inline"><button type="submit" class="btn btn-outline-danger w-100"><i class="bi bi-radar"></i> Nmap сканирование</button></form></div></div></div>
                    </div>
                </div>
            </div>
        </div>
    </div>
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>
""",
    "templates/asset_history.html": """<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8"> <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>История - {{ asset.ip_address }}</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.10.0/font/bootstrap-icons.css" rel="stylesheet">
    <link href="{{ url_for('static', filename='css/style.css') }}" rel="stylesheet">
</head>
<body>
    <div class="container-fluid">
        <div class="row">
            <div class="col-md-3 col-lg-2 sidebar p-3 d-none d-md-block"><h5 class="mb-3"><i class="bi bi-folder-tree"></i> Группы</h5><div id="group-tree">{% include 'components/group_tree.html' %}</div></div>
            <div class="col-md-9 col-lg-10 p-4">
                <nav class="navbar navbar-light mb-4 px-3"><div class="d-flex align-items-center"><a href="{{ url_for('main.asset_detail', id=asset.id) }}" class="btn btn-outline-dark me-3"><i class="bi bi-arrow-left"></i> Назад</a><span class="navbar-brand mb-0 h1"><i class="bi bi-clock-history"></i> История: {{ asset.ip_address }}</span></div><button class="theme-toggle" onclick="toggleTheme()"><i class="bi bi-moon"></i><i class="bi bi-sun"></i></button></nav>
                <div class="row">
                    <div class="col-lg-8">
                        <div class="card mb-4"><div class="card-header"><i class="bi bi-activity"></i> Таймлайн <span class="badge bg-primary float-end">{{ changes|length }}</span></div>
                            <div class="card-body">{% if changes %}<div class="timeline">{% for c in changes %}<div class="timeline-item"><div class="timeline-marker">{{ c.changed_at.strftime('%Y-%m-%d %H:%M') }}</div><div class="timeline-dot"></div><div class="timeline-content"><div class="d-flex justify-content-between align-items-start mb-2"><h6 class="mb-0">{{ c.change_type }}</h6><span class="badge bg-secondary">{{ c.field_name or '-' }}</span></div>{% if c.old_value %}<div class="mb-1"><small class="text-muted">Было:</small><code>{{ c.old_value }}</code></div>{% endif %}{% if c.new_value %}<div class="mb-1"><small class="text-muted">Стало:</small><code>{{ c.new_value }}</code></div>{% endif %}{% if c.notes %}<div class="mt-2"><small class="text-muted"><i class="bi bi-chat-left-text"></i> {{ c.notes }}</small></div>{% endif %}</div></div>{% endfor %}</div>{% else %}<p class="text-muted text-center py-4">История пуста</p>{% endif %}</div></div>
                    </div>
                </div>
            </div>
        </div>
    </div>
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>
""",
    "templates/scans.html": """<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8"> <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Сканирования</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.10.0/font/bootstrap-icons.css" rel="stylesheet">
    <link href="{{ url_for('static', filename='css/style.css') }}" rel="stylesheet">
</head>
<body>
    <div class="container-fluid">
        <div class="row">
            <div class="col-md-3 col-lg-2 sidebar p-3 d-none d-md-block"><h5 class="mb-3"><i class="bi bi-folder-tree"></i> Группы</h5><div id="group-tree">{% include 'components/group_tree.html' %}</div></div>
            <div class="col-md-9 col-lg-10 p-4">
                <nav class="navbar navbar-light mb-4 px-3"><span class="navbar-brand mb-0 h1"><i class="bi bi-wifi"></i> Сканирования</span><div class="d-flex align-items-center"><button class="theme-toggle me-2" onclick="toggleTheme()"><i class="bi bi-moon"></i><i class="bi bi-sun"></i></button><a href="{{ url_for('main.index') }}" class="btn btn-outline-dark"><i class="bi bi-arrow-left"></i> На главную</a></div></nav>
                {% with messages = get_flashed_messages(with_categories=true) %}{% if messages %}{% for c, m in messages %}<div class="alert alert-{{ c }} alert-dismissible fade show">{{ m }}<button type="button" class="btn-close" data-bs-dismiss="alert"></button></div>{% endfor %}{% endif %}{% endwith %}
                <div class="card mb-3 bg-light"><div class="card-body py-2 d-flex align-items-center gap-3 flex-wrap"><label class="fw-bold mb-0"><i class="bi bi-collection"></i> Профили:</label><select id="scan-profile-select" class="form-select form-select-sm" style="width: 250px;"><option value="">-- Без профиля --</option>{% for p in profiles %}<option value="{{ p.id }}" data-json='{{ p.to_dict()|tojson|forceescape }}'>{{ p.name }} ({{ p.scan_type }})</option>{% endfor %}</select><button type="button" class="btn btn-sm btn-success" data-bs-toggle="modal" data-bs-target="#saveProfileModal"><i class="bi bi-save"></i> Сохранить</button><button type="button" class="btn btn-sm btn-outline-danger" onclick="deleteCurrentProfile()"><i class="bi bi-trash"></i></button></div></div>
                <div class="card mb-4"><div class="card-header"><i class="bi bi-plus-circle"></i> Новое сканирование</div><div class="card-body">
                    <form id="scanForm">
                        <div class="row mb-3"><div class="col-md-6"><label class="form-label">Тип сканирования</label><select id="scan-type" class="form-select" onchange="toggleScanOptions()"><option value="rustscan">🚀 Rustscan</option><option value="nmap">🔍 Nmap</option></select></div><div class="col-md-6"><label class="form-label">Метод выбора цели</label><select id="target-method" class="form-select" onchange="toggleTargetInput()"><option value="ip">IP / CIDR</option><option value="group">Группа активов</option></select></div></div>
                        <div class="mb-3" id="target-ip-section"><label class="form-label">Цель</label><input type="text" id="scan-target" class="form-control" placeholder="192.168.1.0/24"></div>
                        <div class="mb-3" id="target-group-section" style="display: none;"><label class="form-label">Группа активов</label><select id="scan-group" class="form-select"><option value="">-- Выберите группу --</option><option value="ungrouped">📂 Без группы</option>{% for g in all_groups %}<option value="{{ g.id }}">{{ g.name }}</option>{% endfor %}</select></div>
                        <div class="mb-3" id="ports-section" style="display: none;"><label class="form-label">Порты (для Nmap)</label><input type="text" id="scan-ports" class="form-control" placeholder="22,80,443"></div>
                        <div class="mb-3"><label class="form-label"><i class="bi bi-sliders"></i> Кастомные аргументы</label><input type="text" id="scan-custom-args" class="form-control" placeholder="--batch-size 500 (Rustscan) или -sS -T4 (Nmap)"></div>
                        <div class="d-grid gap-2 d-md-flex justify-content-md-end"><button type="button" class="btn btn-secondary" onclick="resetScanForm()"><i class="bi bi-arrow-counterclockwise"></i> Сброс</button><button type="submit" class="btn btn-primary"><i class="bi bi-play-fill"></i> Запустить</button></div>
                    </form>
                </div></div>
                <div class="card mb-4"><div class="card-header"><i class="bi bi-activity"></i> Активные сканирования</div><div class="card-body"><div id="active-scans"><p class="text-muted mb-0"><i class="bi bi-check-circle"></i> Нет активных сканирований</p></div></div></div>
                <div class="card"><div class="card-header"><i class="bi bi-clock-history"></i> История сканирований</div><div class="card-body p-0"><table class="table table-hover mb-0"><thead class="table-light"><tr><th>ID</th><th>Тип</th><th>Цель</th><th>Статус</th><th>Прогресс</th><th>Начало</th><th>Действия</th></tr></thead><tbody>{% for job in scan_jobs %}<tr><td>{{ job.id }}</td><td><span class="badge bg-{{ 'danger' if job.scan_type=='rustscan' else 'info text-dark' }}">{{ job.scan_type.upper() }}</span></td><td><code>{{ job.target }}</code></td><td><span class="badge bg-{{ 'secondary' if job.status=='pending' else 'warning text-dark' if job.status=='running' else 'success' if job.status=='completed' else 'danger' }}">{{ job.status }}</span></td><td><div class="progress" style="width:100px"><div class="progress-bar" style="width:{{ job.progress }}%"></div></div><small>{{ job.progress }}%</small></td><td>{{ job.started_at.strftime('%Y-%m-%d %H:%M') if job.started_at else '-' }}</td><td>{% if job.status=='pending' %}<button class="btn btn-sm btn-outline-danger" onclick="controlScan('{{ job.id }}', 'delete')"><i class="bi bi-trash"></i></button>{% elif job.status=='running' %}<button class="btn btn-sm btn-outline-warning" onclick="controlScan('{{ job.id }}', 'pause')"><i class="bi bi-pause-fill"></i></button><button class="btn btn-sm btn-outline-danger" onclick="controlScan('{{ job.id }}', 'stop')"><i class="bi bi-stop-fill"></i></button>{% elif job.status=='paused' %}<button class="btn btn-sm btn-outline-success" onclick="controlScan('{{ job.id }}', 'resume')"><i class="bi bi-play-fill"></i></button><button class="btn btn-sm btn-outline-danger" onclick="controlScan('{{ job.id }}', 'stop')"><i class="bi bi-stop-fill"></i></button>{% elif job.status in ['completed','failed','stopped'] %}<button class="btn btn-sm btn-outline-danger" onclick="controlScan('{{ job.id }}', 'delete')"><i class="bi bi-trash"></i></button>{% endif %}{% if job.status!='pending' %}<button class="btn btn-sm btn-outline-info" onclick="viewScanResults('{{ job.id }}')"><i class="bi bi-eye"></i></button>{% endif %}</td></tr>{% else %}<tr><td colspan="7" class="text-center py-4 text-muted">Нет сканирований</td></tr>{% endfor %}</tbody></table></div></div>
            </div>
        </div>
    </div>
    <div class="modal fade" id="scanResultsModal" tabindex="-1"><div class="modal-dialog modal-lg"><div class="modal-content"><div class="modal-header"><h5 class="modal-title">Результаты</h5><button type="button" class="btn-close" data-bs-dismiss="modal"></button></div><div class="modal-body"><div id="scan-results-content"></div></div><div class="modal-footer"><button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Закрыть</button></div></div></div></div>
    <div class="modal fade" id="saveProfileModal" tabindex="-1"><div class="modal-dialog modal-sm"><div class="modal-content"><div class="modal-header"><h6>💾 Сохранить профиль</h6><button type="button" class="btn-close" data-bs-dismiss="modal"></button></div><div class="modal-body"><input type="text" id="profile-name-input" class="form-control" placeholder="Название" required></div><div class="modal-footer"><button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Отмена</button><button type="button" class="btn btn-primary" onclick="saveProfile()">Сохранить</button></div></div></div></div>
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
    <script>
        function toggleTargetInput(){const m=document.getElementById('target-method').value;document.getElementById('target-ip-section').style.display=m==='group'?'none':'block';document.getElementById('target-group-section').style.display=m==='group'?'block':'none';}
        function toggleScanOptions(){const t=document.getElementById('scan-type').value;document.getElementById('ports-section').style.display=t==='nmap'?'block':'none';}
        function resetScanForm(){document.getElementById('scanForm').reset();toggleTargetInput();toggleScanOptions();}
        document.getElementById('scanForm').addEventListener('submit', async e=>{e.preventDefault();const t=document.getElementById('scan-type').value;const m=document.getElementById('target-method').value;const tg=m==='ip'?document.getElementById('scan-target').value:null;const gr=m==='group'?document.getElementById('scan-group').value:null;if(m==='ip'&&!tg){alert('⚠️ Укажите цель');return;}if(m==='group'&&!gr){alert('⚠️ Выберите группу');return;}const body={target:tg,group_id:gr};if(t==='nmap' && document.getElementById('scan-ports').value) body.ports=document.getElementById('scan-ports').value;if(document.getElementById('scan-custom-args').value) body.custom_args=document.getElementById('scan-custom-args').value;const res=await fetch(`/api/scans/${t}`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});const d=await res.json();if(res.ok){alert(`✅ ${d.message}`);location.reload();}else alert(`❌ ${d.error}`);});
        async function viewScanResults(id){const m=new bootstrap.Modal(document.getElementById('scanResultsModal'));const c=document.getElementById('scan-results-content');c.innerHTML='<div class="text-center"><div class="spinner-border"></div><p class="mt-2">Загрузка...</p></div>';m.show();try{const r=await fetch(`/api/scans/${id}/results`);const d=await r.json();let h=`<h6>#${d.job.id} - ${d.job.scan_type.toUpperCase()}</h6><p><strong>Цель:</strong> ${d.job.target}</p><p><strong>Статус:</strong> ${d.job.status}</p><hr>`;if(d.results.length===0) h+='<p class="text-muted">Нет результатов</p>';else{h+=`<p><strong>Хостов:</strong> ${d.results.length}</p><div class="list-group">`;d.results.forEach(x=>{h+=`<div class="list-group-item"><div class="d-flex justify-content-between"><h6 class="mb-1">${x.ip}</h6></div><p class="mb-1"><strong>Порты:</strong> ${x.ports.join(', ')||'Нет'}</p></div>`;});h+='</div>';}c.innerHTML=h;}catch(e){c.innerHTML=`<div class="alert alert-danger">❌ ${e.message}</div>`;}}
        function pollActiveScans(){fetch('/api/scans/status').then(r=>r.json()).then(d=>{const c=document.getElementById('active-scans');if(d.active?.length){let h='<div class="row">';d.active.forEach(j=>{const cls=j.status==='running'?'progress-bar-striped progress-bar-animated':'';const b=j.scan_type==='rustscan'?'bg-danger':'bg-info text-dark';const s=j.status==='running'?'bg-warning text-dark':j.status==='paused'?'bg-info text-dark':'bg-secondary';h+=`<div class="col-md-6 mb-3"><div class="card border-${j.status==='failed'?'danger':j.status==='running'?'warning':'info'}"><div class="card-body"><div class="d-flex justify-content-between align-items-center mb-2"><h6 class="mb-0"><span class="badge ${b} me-2">${j.scan_type.toUpperCase()}</span>${j.target}</h6><span class="badge ${s}">${j.status}</span></div><div class="progress mb-2" style="height:6px"><div class="progress-bar ${cls}" style="width:${j.progress}%"></div></div><small>${j.current_target&&j.status==='running'?`📡 Сканируется: <strong>${j.current_target}</strong><br>`:''}Прогресс: ${j.progress}%</small></div></div></div>`;});h+='</div>';c.innerHTML=h;}else c.innerHTML='<p class="text-muted mb-0"><i class="bi bi-check-circle"></i> Нет активных сканирований</p>';}).catch(e=>console.warn('⚠️ Polling error:',e));}
        document.addEventListener('DOMContentLoaded',()=>{toggleTargetInput();toggleScanOptions();pollActiveScans();setInterval(pollActiveScans,5000);const ps=document.getElementById('scan-profile-select');if(ps)ps.addEventListener('change',function(){const o=this.options[this.selectedIndex];if(o.dataset.json){const p=JSON.parse(o.dataset.json);document.getElementById('scan-type').value=p.scan_type;document.getElementById('target-method').value=p.target_method||'ip';toggleTargetInput();toggleScanOptions();document.getElementById('scan-ports').value=p.ports||'';document.getElementById('scan-custom-args').value=p.custom_args||'';}});});
        async function saveProfile(){const n=document.getElementById('profile-name-input').value;if(!n)return alert('Введите название');const p={name:n,scan_type:document.getElementById('scan-type').value,target_method:document.getElementById('target-method').value,ports:document.getElementById('scan-ports').value,custom_args:document.getElementById('scan-custom-args').value};const r=await fetch('/api/scans/profiles',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(p)});if(r.ok)location.reload();else alert('❌ Ошибка');}
        async function deleteCurrentProfile(){const id=document.getElementById('scan-profile-select').value;if(!id)return alert('Выберите профиль');if(!confirm('Удалить профиль?'))return;await fetch(`/api/scans/profiles/${id}`,{method:'DELETE'});location.reload();}
        async function controlScan(id, action){if(action==='delete'&&!confirm('Удалить запись?'))return;if(action==='stop'&&!confirm('Остановить?'))return;const r=await fetch(`/api/scans/${id}/control`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action})});const d=await r.json();if(r.ok)location.reload();else alert(`❌ ${d.error}`);}
    </script>
</body>
</html>
""",
    "templates/utilities.html": """<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8"> <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Утилиты</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.10.0/font/bootstrap-icons.css" rel="stylesheet">
    <link href="{{ url_for('static', filename='css/style.css') }}" rel="stylesheet">
</head>
<body>
    <div class="container-fluid">
        <div class="row">
            <div class="col-md-3 col-lg-2 sidebar p-3 d-none d-md-block"><h5 class="mb-3"><i class="bi bi-folder-tree"></i> Группы</h5><div id="group-tree">{% include 'components/group_tree.html' %}</div></div>
            <div class="col-md-9 col-lg-10 p-4">
                <nav class="navbar navbar-light mb-4 px-3"><span class="navbar-brand mb-0 h1"><i class="bi bi-tools"></i> Утилиты</span><div class="d-flex align-items-center"><button class="theme-toggle me-2" onclick="toggleTheme()"><i class="bi bi-moon"></i><i class="bi bi-sun"></i></button><a href="{{ url_for('main.index') }}" class="btn btn-outline-dark"><i class="bi bi-arrow-left"></i> На главную</a></div></nav>
                <div class="row">
                    <div class="col-md-6 col-lg-4 mb-4"><div class="card h-100" data-bs-toggle="modal" data-bs-target="#nmapRustscanModal" style="cursor: pointer;"><div class="card-body text-center p-4"><i class="bi bi-lightning-charge display-4 text-primary mb-3"></i><h5>Nmap → Rustscan</h5><p class="text-muted">Конвертация XML в список IP</p></div></div></div>
                    <div class="col-md-6 col-lg-4 mb-4"><div class="card h-100" data-bs-toggle="modal" data-bs-target="#extractPortsModal" style="cursor: pointer;"><div class="card-body text-center p-4"><i class="bi bi-door-open display-4 text-info mb-3"></i><h5>Извлечь порты</h5><p class="text-muted">Извлечение портов из Nmap XML</p></div></div></div>
                </div>
            </div>
        </div>
    </div>
    <div class="modal fade" id="nmapRustscanModal" tabindex="-1"><div class="modal-dialog"><div class="modal-content"><form id="nmapRustscanForm" enctype="multipart/form-data"><div class="modal-header"><h5>Nmap → Rustscan</h5><button type="button" class="btn-close" data-bs-dismiss="modal"></button></div><div class="modal-body"><div class="mb-3"><label>XML файл</label><input type="file" name="file" class="form-control" accept=".xml" required></div><div id="nmapRustscanResult" class="mt-3"></div></div><div class="modal-footer"><button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Отмена</button><button type="submit" class="btn btn-primary"><i class="bi bi-download"></i> Скачать</button></div></form></div></div></div>
    <div class="modal fade" id="extractPortsModal" tabindex="-1"><div class="modal-dialog"><div class="modal-content"><form id="extractPortsForm" enctype="multipart/form-data"><div class="modal-header"><h5>Извлечь порты</h5><button type="button" class="btn-close" data-bs-dismiss="modal"></button></div><div class="modal-body"><div class="mb-3"><label>XML файл</label><input type="file" name="file" class="form-control" accept=".xml" required></div><div id="extractPortsResult" class="mt-3"></div></div><div class="modal-footer"><button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Отмена</button><button type="submit" class="btn btn-primary"><i class="bi bi-download"></i> Скачать</button></div></form></div></div></div>
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
    <script>
        function handleUpload(formId, resId, url){document.getElementById(formId).addEventListener('submit', async e=>{e.preventDefault();const f=e.target;const fd=new FormData(f);const r=document.getElementById(resId);r.innerHTML='<div class="text-center"><div class="spinner-border"></div></div>';try{const res=await fetch(url,{method:'POST',body:fd});if(res.ok){const blob=await res.blob();const u=window.URL.createObjectURL(blob);const a=document.createElement('a');a.href=u;a.download=res.headers.get('Content-Disposition').split('filename=')[1];document.body.appendChild(a);a.click();r.innerHTML='<div class="alert alert-success">Готово!</div>';setTimeout(()=>{bootstrap.Modal.getInstance(document.getElementById(formId.replace('Form','Modal'))).hide();r.innerHTML='';f.reset();},2000);}else{const err=await res.json();r.innerHTML=`<div class="alert alert-danger">${err.error}</div>`;}}catch(err){r.innerHTML=`<div class="alert alert-danger">${err.message}</div>`;}});}
        handleUpload('nmapRustscanForm','nmapRustscanResult','/utilities/nmap-to-rustscan');
        handleUpload('extractPortsForm','extractPortsResult','/utilities/extract-ports');
    </script>
</body>
</html>
""",
    "templates/osquery_dashboard.html": """<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8"> <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>OSquery Управление</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.10.0/font/bootstrap-icons.css" rel="stylesheet">
    <link href="{{ url_for('static', filename='css/style.css') }}" rel="stylesheet">
</head>
<body>
    <div class="container-fluid p-4">
        <nav class="navbar navbar-light mb-4 px-3"><span class="navbar-brand mb-0 h1"><i class="bi bi-hdd-network"></i> OSquery Агенты</span><div class="d-flex align-items-center"><button class="theme-toggle me-2" onclick="toggleTheme()"><i class="bi bi-moon"></i><i class="bi bi-sun"></i></button><a href="{{ url_for('main.index') }}" class="btn btn-outline-dark"><i class="bi bi-arrow-left"></i> На главную</a><a href="{{ url_for('osquery.deploy_page') }}" class="btn btn-outline-primary"><i class="bi bi-rocket-takeoff"></i> Деплой</a><a href="{{ url_for('osquery.config_editor') }}" class="btn btn-outline-secondary"><i class="bi bi-gear"></i> Конфиг</a></div></nav>
        <div class="row">{% for asset in assets %}<div class="col-md-4 mb-3"><div class="card border-{{ 'success' if asset.osquery_status=='online' else 'secondary' }}"><div class="card-body"><h5 class="card-title">{{ asset.ip_address }}</h5><p class="card-text small"><strong>Статус:</strong> {{ asset.osquery_status }}<br><strong>Версия:</strong> {{ asset.osquery_version or '-' }}<br><strong>Последний отчет:</strong> {{ asset.osquery_last_seen.strftime('%Y-%m-%d %H:%M') if asset.osquery_last_seen else '-' }}<br><strong>Node Key:</strong> <code>{{ asset.osquery_node_key }}</code></p><a href="{{ url_for('main.asset_detail', id=asset.id) }}" class="btn btn-sm btn-outline-primary">Перейти к активу</a></div></div></div>{% else %}<div class="col-12 text-center text-muted py-5"><i class="bi bi-hdd-network fs-1 d-block mb-2"></i>Нет зарегистрированных агентов OSquery</div>{% endfor %}</div>
    </div>
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>
""",
    "templates/osquery_deploy.html": """<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8"> <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Деплой OSquery</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.10.0/font/bootstrap-icons.css" rel="stylesheet">
    <link href="{{ url_for('static', filename='css/style.css') }}" rel="stylesheet">
</head>
<body>
    <div class="container-fluid p-4">
        <nav class="navbar navbar-light mb-4 px-3"><span class="navbar-brand mb-0 h1"><i class="bi bi-rocket-takeoff"></i> Деплой агентов</span><button class="theme-toggle" onclick="toggleTheme()"><i class="bi bi-moon"></i><i class="bi bi-sun"></i></button></nav>
        <div class="card mb-4"><div class="card-header">📜 Ansible Плейбук</div><div class="card-body"><p>Скачайте плейбук и инвентарь, запустите: <code>ansible-playbook -i inventory.ini ansible/deploy_osquery.yml</code></p><a href="/osquery/instructions" class="btn btn-outline-secondary">📖 Инструкция по установке</a></div></div>
        <div class="card"><div class="card-header">🌐 Генератор inventory.ini</div><div class="card-body"><form id="inventory-form"><div class="mb-3"><label>IP-адреса (через запятую)</label><input type="text" id="ips" class="form-control" placeholder="192.168.1.10, 10.0.0.5"></div><button type="button" class="btn btn-primary" onclick="downloadInventory()">Скачать inventory.ini</button></form></div></div>
    </div>
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
    <script>function downloadInventory(){const i=document.getElementById('ips').value.trim();if(!i)return alert('Введите IP-адреса');const b=new Blob([`[osquery_agents]\\n${i.split(',').map(x=>x.trim()).join('\\n')}`],{type:'text/plain'});const u=URL.createObjectURL(b);const a=document.createElement('a');a.href=u;a.download='inventory.ini';a.click();}</script>
</body>
</html>
""",
    "templates/osquery_instructions.html": """<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8"> <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Инструкции OSquery</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.10.0/font/bootstrap-icons.css" rel="stylesheet">
    <link href="{{ url_for('static', filename='css/style.css') }}" rel="stylesheet">
</head>
<body>
    <div class="container-fluid p-4">
        <nav class="navbar navbar-light mb-4 px-3"><span class="navbar-brand mb-0 h1"><i class="bi bi-book"></i> Установка OSquery</span><button class="theme-toggle" onclick="toggleTheme()"><i class="bi bi-moon"></i><i class="bi bi-sun"></i></button></nav>
        <div class="accordion" id="installAccordion">
            <div class="accordion-item"><h2 class="accordion-header"><button class="accordion-button" type="button" data-bs-toggle="collapse" data-bs-target="#linux-inst">🐧 Linux</button></h2><div id="linux-inst" class="accordion-collapse collapse show" data-bs-parent="#installAccordion"><div class="accordion-body"><pre class="bg-light p-2">sudo apt update && sudo apt install osquery -y</pre><p>Скопируйте <code>osquery.conf</code> в <code>/etc/osquery/</code>. Запустите: <code>sudo systemctl enable --now osqueryd</code></p></div></div></div>
            <div class="accordion-item"><h2 class="accordion-header"><button class="accordion-button collapsed" type="button" data-bs-toggle="collapse" data-bs-target="#win-inst">🪟 Windows</button></h2><div id="win-inst" class="accordion-collapse collapse" data-bs-parent="#installAccordion"><div class="accordion-body"><p>Скачайте MSI: <code>https://pkg.osquery.io/windows/osquery.msi</code><br>Установка: <code>msiexec /i osquery.msi /qn</code>. Конфиг в <code>C:\\ProgramData\\osquery\\osquery.conf</code>. Запуск: <code>sc start osqueryd</code></p></div></div></div>
        </div>
    </div>
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>
""",
    "templates/osquery_config_editor.html": """<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8"> <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Редактор osquery</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.10.0/font/bootstrap-icons.css" rel="stylesheet">
    <link href="{{ url_for('static', filename='css/style.css') }}" rel="stylesheet">
</head>
<body>
    <div class="container-fluid p-4">
        <nav class="navbar navbar-light mb-4 px-3"><span class="navbar-brand mb-0 h1"><i class="bi bi-gear"></i> Редактор osquery.conf</span><button class="theme-toggle" onclick="toggleTheme()"><i class="bi bi-moon"></i><i class="bi bi-sun"></i></button></nav>
        <div class="row g-4">
            <div class="col-lg-8"><div class="card"><div class="card-header d-flex justify-content-between align-items-center"><span><i class="bi bi-filetype-json"></i> osquery.conf</span><div><button class="btn btn-sm btn-outline-secondary me-1" onclick="formatJSON()"><i class="bi bi-braces"></i> Формат</button><button class="btn btn-sm btn-warning me-1" onclick="validateConfig()"><i class="bi bi-shield-check"></i> Валидация</button><button class="btn btn-sm btn-success" onclick="saveConfig()"><i class="bi bi-save"></i> Сохранить</button></div></div><div class="card-body p-0"><textarea id="config-editor" class="form-control font-monospace" style="height:500px;border:0" spellcheck="false"></textarea></div></div></div>
            <div class="col-lg-4"><div class="card mb-3"><div class="card-header bg-info text-white">📊 Результат валидации</div><div class="card-body" id="validation-results"><p class="text-muted">Нажмите "Валидация" для проверки.</p></div></div></div>
        </div>
    </div>
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
    <script>
        async function loadConfig(){try{const r=await fetch('/osquery/api/config');if(!r.ok)throw new Error('Ошибка');document.getElementById('config-editor').value=JSON.stringify(await r.json(),null,2);}catch(e){alert('❌ '+e.message);}}
        function formatJSON(){try{document.getElementById('config-editor').value=JSON.stringify(JSON.parse(document.getElementById('config-editor').value),null,2);}catch(e){alert('JSON ошибка');}}
        async function validateConfig(){const d=document.getElementById('validation-results');d.innerHTML='<div class="spinner-border spinner-border-sm"></div> Проверка...';try{const r=await fetch('/osquery/api/config/validate',{method:'POST',headers:{'Content-Type':'application/json'},body:document.getElementById('config-editor').value});const res=await r.json();let h=res.errors.map(e=>`<div class="text-danger">❌ ${e}</div>`).join('')+res.warnings.map(w=>`<div class="text-warning">⚠️ ${w}</div>`).join('');if(!h)h='<div class="text-success">✅ Валидно</div>';d.innerHTML=h;}catch(e){d.innerHTML=`<div class="text-danger">❌ ${e.message}</div>`;}}
        async function saveConfig(){try{const r=await fetch('/osquery/api/config',{method:'POST',headers:{'Content-Type':'application/json'},body:document.getElementById('config-editor').value});const d=await r.json();if(r.ok)alert('✅ '+d.message);else alert('❌ '+d.error);}catch(e){alert('❌ '+e.message);}}
        document.addEventListener('DOMContentLoaded', loadConfig);
    </script>
</body>
</html>
""",
    "templates/components/group_tree.html": """<div class="group-tree-container">
    <div class="d-flex justify-content-between align-items-center mb-3"><h6 class="mb-0 text-uppercase text-muted small fw-bold"><i class="bi bi-folder-tree me-2"></i>Группы активов</h6><button class="btn btn-sm btn-outline-primary" onclick="showCreateGroupModal(null)"><i class="bi bi-plus-lg"></i></button></div>
    <div class="group-tree" id="groupTree"><ul class="list-group list-group-flush">
        <li class="list-group-item px-0 border-0"><div class="group-item d-flex align-items-center justify-content-between py-2 {% if current_filter == 'ungrouped' or current_filter is none %}active{% endif %}" data-group-id="ungrouped" data-bs-toggle="tooltip" title="Активы без группы"><div class="d-flex align-items-center flex-grow-1" style="cursor:pointer" onclick="filterByGroup('ungrouped')"><span class="me-2" style="width:16px"></span><i class="bi bi-folder-minus-fill text-muted me-2"></i><span class="group-name flex-grow-1">Без группы</span><span class="badge bg-light text-dark rounded-pill ms-2" id="ungrouped-count">{{ ungrouped_count if ungrouped_count is defined else 0 }}</span></div></div></li>
        {% if group_tree %}
        {% macro render_groups(nodes, level=0) %}{% for node in nodes %}<li class="list-group-item px-0 border-0" style="padding-left:{{ level * 20 }}px !important"><div class="group-item d-flex align-items-center justify-content-between py-2 {% if node.is_dynamic %}group-dynamic{% endif %}" data-group-id="{{ node.id }}" data-bs-toggle="tooltip" title="{% if node.is_dynamic %}Динамическая группа{% else %}Статическая группа{% endif %}"><div class="d-flex align-items-center flex-grow-1" style="cursor:pointer" onclick="filterByGroup({{ node.id }})">{% if node.children %}<i class="bi bi-caret-right-fill me-2 text-muted group-toggle" data-group-id="{{ node.id }}" onclick="event.stopPropagation();toggleGroup(this,{{ node.id }})"></i>{% else %}<span class="me-2" style="width:16px"></span>{% endif %}<i class="bi {% if node.is_dynamic %}bi-lightning-charge-fill text-warning{% else %}bi-folder-fill text-primary{% endif %} me-2"></i><span class="group-name flex-grow-1">{{ node.name }}</span><span class="badge bg-light text-dark rounded-pill ms-2">{{ node.count }}</span></div><div class="group-actions btn-group"><button class="btn btn-sm btn-link text-muted p-0 me-1" onclick="event.stopPropagation();showRenameModal({{ node.id }})"><i class="bi bi-pencil"></i></button><button class="btn btn-sm btn-link text-muted p-0" onclick="event.stopPropagation();showMoveModal({{ node.id }})"><i class="bi bi-arrow-left-right"></i></button></div></div>{% if node.children %}<ul class="list-group list-group-flush ms-3 d-none" id="group-children-{{ node.id }}">{{ render_groups(node.children, level + 1) }}</ul>{% endif %}</li>{% endfor %}{% endmacro %}
        {{ render_groups(group_tree) }}
        {% endif %}
    </ul></div>
</div>
<script>function toggleGroup(e,id){const c=document.getElementById(`group-children-${id}`);if(c){c.classList.toggle('d-none');e.classList.toggle('bi-caret-right-fill');e.classList.toggle('bi-caret-down-fill');}}document.addEventListener('DOMContentLoaded',()=>{if(typeof bootstrap!=='undefined'){const t=[].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));t.map(x=>new bootstrap.Tooltip(x));}});</script>
<style>.group-tree-container{background:var(--bg-body);border-radius:0.5rem}.group-tree .list-group-item{background:transparent;border:none;padding-left:0!important}.group-item{border-radius:0.375rem;transition:all 0.2s ease;margin-bottom:0.25rem}.group-item:hover{background:var(--bg-hover)}.group-item.active{background:rgba(13,110,253,0.1);border-left:3px solid var(--bs-primary)}.group-dynamic{border-left:2px solid var(--bs-warning);padding-left:8px!important}.group-toggle{transition:transform 0.2s ease;cursor:pointer}.group-actions{opacity:0;transition:opacity 0.2s ease}.group-item:hover .group-actions{opacity:1}@media(max-width:768px){.group-actions{opacity:1}}</style>
""",
    "templates/components/assets_rows.html": """{% for asset in assets %}
<tr data-asset-id="{{ asset.id }}" class="asset-row">
    <td><input type="checkbox" class="form-check-input asset-checkbox" value="{{ asset.id }}"></td>
    <td><a href="/asset/{{ asset.id }}" class="text-decoration-none"><strong>{{ asset.ip_address }}</strong></a></td>
    <td>{{ asset.hostname or '—' }}</td>
    <td><span class="text-muted small">{{ asset.os_info or '—' }}</span></td>
    <td><small class="text-muted">{{ asset.open_ports or '—' }}</small></td>
    <td><span class="badge bg-light text-dark border">{{ asset.group.name if asset.group else '—' }}</span></td>
    <td><a href="/asset/{{ asset.id }}" class="btn btn-sm btn-outline-info"><i class="bi bi-eye"></i></a></td>
</tr>
{% else %}
<tr><td colspan="7" class="text-center py-4 text-muted">Нет данных</td></tr>
{% endfor %}
""",
    "templates/components/modals.html": """<div class="modal fade" id="scanModal" tabindex="-1"><div class="modal-dialog"><div class="modal-content"><form action="{{ url_for('main.import_scan') }}" method="post" enctype="multipart/form-data"><div class="modal-header"><h5>Импорт Nmap</h5><button type="button" class="btn-close" data-bs-dismiss="modal"></button></div><div class="modal-body"><div class="mb-3"><label>XML файл</label><input type="file" name="file" class="form-control" accept=".xml" required></div><div class="mb-3"><label>Группа</label><select name="group_id" class="form-select"><option value="">Без группы</option>{% for g in all_groups %}<option value="{{ g.id }}">{{ g.name }}</option>{% endfor %}</select></div></div><div class="modal-footer"><button type="submit" class="btn btn-primary">Загрузить</button></div></form></div></div></div>
<div class="modal fade" id="groupEditModal" tabindex="-1"><div class="modal-dialog modal-lg"><div class="modal-content"><form id="groupEditForm"><div class="modal-header"><h5 id="groupEditTitle">Группа</h5><button type="button" class="btn-close" data-bs-dismiss="modal"></button></div><div class="modal-body"><input type="hidden" id="edit-group-id"><div class="mb-3"><label>Название</label><input type="text" id="edit-group-name" class="form-control" required></div><div class="mb-3"><label>Родитель</label><select id="edit-group-parent" class="form-select"><option value="">-- Корень --</option>{% for g in all_groups %}<option value="{{ g.id }}">{{ g.name }}</option>{% endfor %}</select></div></div><div class="modal-footer"><button type="submit" class="btn btn-primary">Сохранить</button></div></form></div></div></div>
<div class="modal fade" id="groupMoveModal" tabindex="-1"><div class="modal-dialog"><div class="modal-content"><form id="groupMoveForm"><div class="modal-header"><h5>Переместить</h5><button type="button" class="btn-close" data-bs-dismiss="modal"></button></div><div class="modal-body"><input type="hidden" id="move-group-id"><div class="mb-3"><label>Новый родитель</label><select id="move-group-parent" class="form-select"></select></div></div><div class="modal-footer"><button type="submit" class="btn btn-primary">Переместить</button></div></form></div></div></div>
<div class="modal fade" id="groupDeleteModal" tabindex="-1"><div class="modal-dialog"><div class="modal-content"><div class="modal-header"><h5 class="text-danger">Удаление</h5><button type="button" class="btn-close" data-bs-dismiss="modal"></button></div><div class="modal-body"><input type="hidden" id="delete-group-id"><p class="text-warning"><i class="bi bi-exclamation-triangle"></i> Вы уверены?</p><div class="mb-3"><label>Перенести активы:</label><select id="delete-move-assets" class="form-select"></select></div></div><div class="modal-footer"><button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Отмена</button><button type="button" class="btn btn-danger" onclick="confirmDeleteGroup()">Удалить</button></div></div></div></div>
<div class="modal fade" id="bulkDeleteModal" tabindex="-1"><div class="modal-dialog"><div class="modal-content"><div class="modal-header"><h5 class="text-danger">Удаление активов</h5><button type="button" class="btn-close" data-bs-dismiss="modal"></button></div><div class="modal-body"><p>Удалить <strong id="bulk-delete-count">0</strong> активов?</p></div><div class="modal-footer"><button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Отмена</button><button type="button" class="btn btn-danger" onclick="executeBulkDelete()">Удалить</button></div></div></div></div>
<div class="modal fade" id="wazuhModal" tabindex="-1"><div class="modal-dialog"><div class="modal-content"><div class="modal-header"><h6>⚙️ Настройка Wazuh API</h6><button type="button" class="btn-close" data-bs-dismiss="modal"></button></div><div class="modal-body"><div class="mb-2"><label>URL API</label><input type="text" id="waz-url" class="form-control form-control-sm" placeholder="https://manager:55000"></div><div class="mb-2"><label>Логин</label><input type="text" id="waz-user" class="form-control form-control-sm" placeholder="wazuh"></div><div class="mb-2"><label>Пароль</label><input type="password" id="waz-pass" class="form-control form-control-sm" placeholder="••••••"></div><div class="form-check form-switch mb-2"><input class="form-check-input" type="checkbox" id="waz-ssl"><label class="form-check-label small">Проверять SSL</label></div><div class="form-check form-switch mb-3"><input class="form-check-input" type="checkbox" id="waz-active" checked><label class="form-check-label small">Включить интеграцию</label></div><button class="btn btn-sm btn-success w-100" onclick="saveWazuhConfig()">💾 Сохранить и синхронизировать</button><div id="waz-status" class="mt-2 small text-center text-muted"></div></div></div></div></div>
"""
}

def backup_files():
    print(f"\n📦 Создание резервной копии в: {BACKUP_DIR}")
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    for rel_path in PROJECT_FILES:
        src = PROJECT_ROOT / rel_path
        if src.exists():
            dst = BACKUP_DIR / rel_path
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
    print("✅ Резервное копирование завершено.\n")

def apply_replacement(dry_run=False):
    changes = 0
    for rel_path, content in PROJECT_FILES.items():
        target = PROJECT_ROOT / rel_path
        target.parent.mkdir(parents=True, exist_ok=True)
        if dry_run:
            print(f"[DRY-RUN] 📝 Пропуск записи: {rel_path}")
            continue
        current_content = ""
        if target.exists():
            try: current_content = target.read_text(encoding='utf-8')
            except: pass
        if current_content.strip() == content.strip():
            print(f"✅ Без изменений: {rel_path}")
            continue
        target.write_text(content, encoding='utf-8')
        print(f"🔄 Обновлён: {rel_path}")
        changes += 1
    print(f"\n🎉 Готово. Изменено файлов: {changes}")

def main():
    parser = argparse.ArgumentParser(description="Полная замена файлов проекта с резервным копированием")
    parser.add_argument('--dry-run', action='store_true', help="Показать, что будет изменено, без записи")
    parser.add_argument('--no-backup', action='store_true', help="Пропустить создание резервной копии")
    args = parser.parse_args()

    if not args.dry_run:
        if not args.no_backup:
            backup_files()
        else:
            print("⚠️ Резервное копирование пропущено по запросу.\n")

        if input("⚠️ Продолжить перезапись файлов? (y/N): ").strip().lower() != 'y':
            print("❌ Отменено пользователем.")
            return

    apply_replacement(dry_run=args.dry_run)

if __name__ == '__main__':
    main()
```

### 📄 `models.py`

```python
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from extensions import db
import json

class Group(db.Model):
    __tablename__ = 'group'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    parent_id = db.Column(db.Integer, db.ForeignKey('group.id'), nullable=True)
    is_dynamic = db.Column(db.Boolean, default=False)
    filter_rules = db.Column(db.Text, nullable=True)  # JSON строка с правилами
    
    # Рекурсивная связь
    children = db.relationship('Group', backref=db.backref('parent', remote_side=[id]), lazy='dynamic')
    assets = db.relationship('Asset', backref='group', lazy='dynamic', cascade='all, delete-orphan')

class Asset(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ip_address = db.Column(db.String(50), nullable=False, index=True)
    hostname = db.Column(db.String(255), nullable=True)
    os_info = db.Column(db.String(100), nullable=True)
    mac_address = db.Column(db.String(50), nullable=True)
    group_id = db.Column(db.Integer, db.ForeignKey('group.id'), nullable=True, index=True)
    
    # Дополнительные поля
    device_role = db.Column(db.String(100), nullable=True)
    device_tags = db.Column(db.Text, nullable=True)  # 🔥 JSON список тегов (добавлено)
    status = db.Column(db.String(50), default='active')
    notes = db.Column(db.Text, nullable=True)
    
    # Поля для DNS (из nslookup)
    dns_names = db.Column(db.Text, nullable=True)  # JSON список доменов
    
    # Поля для совместимости со старым кодом и scanner.py
    data_source = db.Column(db.String(50), default='manual')
    last_scanned = db.Column(db.DateTime, nullable=True)
    scanners_used = db.Column(db.Text, nullable=True)  # JSON список сканеров
    
    # Порты от разных сканеров (строки)
    open_ports = db.Column(db.Text, nullable=True)      # Объединенный список "22/tcp, 80/tcp"
    ports_list = db.Column(db.Text, nullable=True)      # JSON список портов
    
    rustscan_ports = db.Column(db.Text, nullable=True)  # 🔥 Порты только от RustScan (добавлено)
    nmap_ports = db.Column(db.Text, nullable=True)      # 🔥 Порты только от Nmap (добавлено)
    
    # Даты последних сканирований конкретными утилитами
    last_rustscan = db.Column(db.DateTime, nullable=True)  # 🔥 (добавлено)
    last_nmap = db.Column(db.DateTime, nullable=True)      # 🔥 (добавлено)

    # Связи
    scan_results = db.relationship('ScanResult', backref='asset', lazy='select', cascade='all, delete-orphan')
    change_log = db.relationship('AssetChangeLog', backref='asset', lazy='select', cascade='all, delete-orphan')
    services = db.relationship('ServiceInventory', backref='asset', lazy='select', cascade='all, delete-orphan')
    
    # Особое внимание здесь: если это one-to-one, uselist=False обязательно, но lazy не может быть 'dynamic'
    osquery_inventory = db.relationship('OsqueryInventory', backref='asset', lazy='select', uselist=False, cascade='all, delete-orphan')

class AssetChangeLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    asset_id = db.Column(db.Integer, db.ForeignKey('asset.id'), nullable=False)
    changed_at = db.Column(db.DateTime, default=datetime.utcnow)
    field_name = db.Column(db.String(100))
    old_value = db.Column(db.Text)
    new_value = db.Column(db.Text)
    changed_by = db.Column(db.String(100), default='system')
    # Для совместимости со старым кодом
    change_type = db.Column(db.String(50), nullable=True)
    scan_job_id = db.Column(db.Integer, db.ForeignKey('scan_job.id'), nullable=True)
    notes = db.Column(db.Text, nullable=True)

class ServiceInventory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    asset_id = db.Column(db.Integer, db.ForeignKey('asset.id'), nullable=False)
    port = db.Column(db.Integer) # Или String если хранится как "22/tcp"
    protocol = db.Column(db.String(10))
    service_name = db.Column(db.String(100))
    version = db.Column(db.String(100))
    state = db.Column(db.String(50))
    last_seen = db.Column(db.DateTime, default=datetime.utcnow)
    # Для совместимости
    is_active = db.Column(db.Boolean, default=True)
    # Дополнительные поля из парсера nmap (если используются)
    product = db.Column(db.String(255), nullable=True)
    extrainfo = db.Column(db.Text, nullable=True)

class OsqueryInventory(db.Model):
    __tablename__ = 'osquery_inventory'
    id = db.Column(db.Integer, primary_key=True)
    asset_id = db.Column(db.Integer, db.ForeignKey('asset.id'), nullable=False, unique=True)
    
    # Основная информация из OSquery
    osquery_version = db.Column(db.String(50))
    os_name = db.Column(db.String(100))
    os_version = db.Column(db.String(100))
    os_build = db.Column(db.String(50))
    os_platform = db.Column(db.String(50))
    platform_like = db.Column(db.String(50))
    code_name = db.Column(db.String(50))
    
    # Система
    hostname = db.Column(db.String(255))
    uuid = db.Column(db.String(100))
    cpu_type = db.Column(db.String(100))
    cpu_subtype = db.Column(db.String(100))
    cpu_brand = db.Column(db.String(100))
    cpu_physical_cores = db.Column(db.Integer)
    cpu_logical_cores = db.Column(db.Integer)
    cpu_microcode = db.Column(db.String(50))
    
    # Память и диск
    physical_memory = db.Column(db.BigInteger)
    hardware_vendor = db.Column(db.String(100))
    hardware_model = db.Column(db.String(100))
    hardware_version = db.Column(db.String(50))
    hardware_serial = db.Column(db.String(100))
    board_vendor = db.Column(db.String(100))
    board_model = db.Column(db.String(100))
    board_version = db.Column(db.String(50))
    board_serial = db.Column(db.String(100))
    chassis_type = db.Column(db.String(50))
    
    # Статус агента
    status = db.Column(db.String(20), default='unknown')
    last_seen = db.Column(db.DateTime, default=datetime.utcnow)
    config_hash = db.Column(db.String(64))

class ScanJob(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    scan_type = db.Column(db.String(50), nullable=False)
    target = db.Column(db.String(255), nullable=False)
    status = db.Column(db.String(20), default='pending')
    progress = db.Column(db.Integer, default=0)
    
    current_target = db.Column(db.String(255), nullable=True)
    total_hosts = db.Column(db.Integer, default=0)
    hosts_processed = db.Column(db.Integer, default=0)
    error_message = db.Column(db.Text, nullable=True)
    
    # Вывод сканеров
    rustscan_output = db.Column(db.Text, nullable=True)
    rustscan_text_path = db.Column(db.String(500), nullable=True)
    
    nmap_xml_path = db.Column(db.String(500), nullable=True)
    nmap_grep_path = db.Column(db.String(500), nullable=True)
    nmap_normal_path = db.Column(db.String(500), nullable=True)
    
    nmap_xml_content = db.Column(db.Text, nullable=True)
    nmap_grep_content = db.Column(db.Text, nullable=True)
    nmap_normal_content = db.Column(db.Text, nullable=True)
    
    nslookup_output = db.Column(db.Text, nullable=True)
    nslookup_file_path = db.Column(db.String(500), nullable=True)
    
    scan_parameters = db.Column(db.Text, nullable=True)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    started_at = db.Column(db.DateTime, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)

class ScanResult(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    asset_id = db.Column(db.Integer, db.ForeignKey('asset.id'), nullable=False)
    scan_job_id = db.Column(db.Integer, db.ForeignKey('scan_job.id'), nullable=True)
    scanned_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    ip = db.Column(db.String(50))
    ports = db.Column(db.Text)
    os = db.Column(db.String(100), nullable=True)
    hostname = db.Column(db.String(255), nullable=True)
    os_detection = db.Column(db.String(100), nullable=True)
    services = db.Column(db.Text, nullable=True) # JSON
    scan_type = db.Column(db.String(50), nullable=True) # Для совместимости со старым кодом
    ip_address = db.Column(db.String(50), nullable=True) # Для совместимости

class ScanProfile(db.Model):
    __tablename__ = 'scan_profile'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    description = db.Column(db.Text, nullable=True)
    
    scan_type = db.Column(db.String(50), nullable=False)
    targets = db.Column(db.Text, nullable=True)
    ports = db.Column(db.String(255), nullable=True)
    timing = db.Column(db.String(10), default='T3')
    scripts = db.Column(db.Text, nullable=True)
    extra_args = db.Column(db.Text, nullable=True)
    
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class WazuhConfig(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    url = db.Column(db.String(255), nullable=False)
    username = db.Column(db.String(100), nullable=False)
    password = db.Column(db.String(255), nullable=False)
    verify_ssl = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)
    last_sync = db.Column(db.DateTime, nullable=True)
```

### 📄 `requirements.txt`

```text
Flask==3.0.3
Flask-SQLAlchemy==3.1.1
Flask-Login==0.6.3
Flask-WTF==1.2.1
Flask-Migrate==4.0.7
Werkzeug==3.0.3
SQLAlchemy==2.0.36
requests==2.32.3
python-nmap==0.7.1
email-validator==2.2.0
gunicorn==22.0.0
```

### 📄 `scanner.py`

```python
# scanner.py
import os
import re
import subprocess
import time
import json
import xml.etree.ElementTree as ET
from datetime import datetime
from extensions import db
from models import ScanJob, Asset, ScanResult, ServiceInventory
from utils import log_asset_change, detect_device_role_and_tags, MOSCOW_TZ

def update_job(job_id, **kwargs):
    """Безопасное обновление статуса задания в фоновом потоке"""
    try:
        db.session.remove()
        job = ScanJob.query.get(job_id)
        if not job:
            print(f"⚠️ Job {job_id} не найден в БД")
            return
        for k, v in kwargs.items():
            setattr(job, k, v)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print(f"❌ Ошибка БД при обновлении job {job_id}: {e}")

def parse_targets(target_str):
    """Разбивает строку целей на список IP/CIDR"""
    return [t.strip() for t in re.split(r'[,\s]+', target_str) if t.strip()]

def check_scan_conflicts(target, scan_type):
    """
    Проверка на конфликты сканирований
    Возвращает: (is_blocked, error_message)
    """
    active_jobs = ScanJob.query.filter(
        ScanJob.status.in_(['pending', 'running', 'paused']),
        ScanJob.target == target
    ).all()
    
    if active_jobs:
        return True, f"Активное сканирование уже выполняется для {target} (job #{active_jobs[0].id})"
    
    same_type_jobs = ScanJob.query.filter(
        ScanJob.status.in_(['pending', 'running', 'paused']),
        ScanJob.scan_type == scan_type
    ).all()
    
    if same_type_jobs:
        return True, f"Активное сканирование {scan_type.upper()} уже выполняется (job #{same_type_jobs[0].id})"
    
    return False, None

def validate_custom_args(scan_type, custom_args):
    """
    Проверка корректности кастомных аргументов перед запуском
    Возвращает: (is_valid, error_message, parsed_args)
    """
    if not custom_args or not custom_args.strip():
        return True, None, {'rustscan': [], 'nmap': []}
    
    args_list = custom_args.split()
    errors = []
    parsed_rustscan = []
    parsed_nmap = []
    
    i = 0
    while i < len(args_list):
        arg = args_list[i]
        if arg == '--':
            i += 1
            continue
        value_args = ['-p', '--ports', '--batch-size', '--timeout', '--top', '-u', '--ulimit']
        if arg in value_args:
            if i + 1 >= len(args_list):
                errors.append(f"❌ Аргументу '{arg}' требуется значение")
            elif args_list[i+1].startswith('-') and not args_list[i+1][1:].isdigit():
                errors.append(f"❌ Аргументу '{arg}' требуется значение")
            else:
                i += 1
        i += 1
    
    i = 0
    while i < len(args_list):
        if args_list[i] in ['-p', '--ports'] and i + 1 < len(args_list):
            port_val = args_list[i+1]
            if not re.match(r'^[\d,\-\s]+$', port_val):
                errors.append(f"❌ Неверный формат портов: '{port_val}'")
        i += 1
    
    in_nmap_section = False
    for arg in args_list:
        if arg == '--':
            in_nmap_section = True
            continue
        if in_nmap_section:
            parsed_nmap.append(arg)
        else:
            parsed_rustscan.append(arg)
    
    if errors:
        return False, '\n'.join(errors), {'rustscan': parsed_rustscan, 'nmap': parsed_nmap}
    return True, None, {'rustscan': parsed_rustscan, 'nmap': parsed_nmap}

def run_rustscan_scan(app, scan_job_id, target, ports, custom_args=''):
    """Фоновое выполнение Rustscan с отладкой вывода"""
    with app.app_context():
        try:
            db.session.remove()
            targets = parse_targets(target)
            
            is_valid, error_msg, parsed_args = validate_custom_args('rustscan', custom_args)
            if not is_valid:
                update_job(scan_job_id, status='failed', progress=100,
                          error_message=f"Ошибка валидации аргументов:\n{error_msg}", 
                          completed_at=datetime.now(MOSCOW_TZ))
                print(f"❌ Ошибка валидации: {error_msg}")
                return
            
            update_job(scan_job_id, status='running', progress=5, total_hosts=len(targets), 
                      hosts_processed=0, current_target='Инициализация...')
            
            cmd = ['rustscan', '-a', target, '--greppable']
            cmd.extend(parsed_args['rustscan'])
            if parsed_args['nmap']:
                cmd.append('--')
                cmd.extend(parsed_args['nmap'])
            
            cmd_str = ' '.join(cmd)
            print(f"🚀 Запуск rustscan job {scan_job_id}")
            print(f"   📜 Команда: {cmd_str}")
            print(f"   🎯 Цель: {target}")
            
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1)
            start_time = time.time()
            processed = 0
            output_lines = []

            for line in iter(process.stdout.readline, ''):
                line = line.strip()
                if line:
                    output_lines.append(line)
                
                job = ScanJob.query.get(scan_job_id)
                if not job: break
                if job.status == 'stopped':
                    process.terminate()
                    update_job(scan_job_id, status='stopped', progress=100, 
                              error_message='Остановлено пользователем', completed_at=datetime.now(MOSCOW_TZ))
                    return
                if job.status == 'paused':
                    time.sleep(0.5)
                    continue

                match = re.match(r'^(\S+)\s+->\s+(.+)$', line)
                if match:
                    processed += 1
                    prog = min(95, 10 + (processed / max(1, len(targets))) * 85)
                    update_job(scan_job_id, progress=int(prog), current_target=match.group(1), hosts_processed=processed)
                else:
                    elapsed = time.time() - start_time
                    if elapsed > 2:
                        update_job(scan_job_id, progress=min(90, 10 + (elapsed / 60) * 80), current_target='Сканирование...')

            process.wait()
            stdout_data, stderr_data = process.communicate()
            
            job = ScanJob.query.get(scan_job_id)
            if not job: 
                print("❌ Job не найден после завершения процесса")
                return

            if process.returncode != 0:
                err_msg = stderr_data.strip() or f"Код возврата: {process.returncode}"
                full_error = f"Ошибка выполнения:\n{err_msg}\n\nКоманда: {cmd_str}"
                update_job(scan_job_id, status='failed', progress=100, error_message=full_error, 
                          completed_at=datetime.now(MOSCOW_TZ))
                print(f"❌ Ошибка rustscan: {err_msg}")
                return

            job.rustscan_output = '\n'.join(output_lines) if output_lines else stdout_data
            
            ts = datetime.now(MOSCOW_TZ).strftime('%Y%m%d_%H%M%S')
            res_dir = os.path.join('scan_results', f'rustscan_{ts}')
            os.makedirs(res_dir, exist_ok=True)
            text_path = os.path.join(res_dir, 'scan.txt')
            with open(text_path, 'w', encoding='utf-8') as f:
                f.write(job.rustscan_output)
            job.rustscan_text_path = text_path
            
            update_job(scan_job_id, progress=98, current_target='Парсинг результатов...')
            
            parse_rustscan_results(scan_job_id, job.rustscan_output, target)
            
            update_job(scan_job_id, progress=100, status='completed', current_target='Готово', 
                      completed_at=datetime.now(MOSCOW_TZ))
            print(f"✅ Job {scan_job_id} завершён успешно")

        except FileNotFoundError:
            update_job(scan_job_id, status='failed', progress=100, 
                      error_message="Утилита rustscan не найдена в PATH.", completed_at=datetime.now(MOSCOW_TZ))
            print("❌ rustscan не установлен или не в PATH")
        except Exception as e:
            update_job(scan_job_id, status='failed', progress=100, 
                      error_message=f"Критическая ошибка: {str(e)}", completed_at=datetime.now(MOSCOW_TZ))
            print(f"❌ Критическая ошибка: {e}")
            import traceback
            traceback.print_exc()
        finally:
            db.session.remove()

def run_nmap_scan(app, scan_job_id, target, ports, scripts, custom_args=''):
    """Фоновое выполнение Nmap"""
    with app.app_context():
        try:
            db.session.remove()
            targets = parse_targets(target)
            
            is_valid, error_msg, parsed_args = validate_custom_args('nmap', custom_args)
            if not is_valid:
                update_job(scan_job_id, status='failed', progress=100,
                          error_message=f"Ошибка валидации аргументов:\n{error_msg}", 
                          completed_at=datetime.now(MOSCOW_TZ))
                print(f"❌ Ошибка валидации аргументов nmap job {scan_job_id}: {error_msg}")
                return
            
            update_job(scan_job_id, status='running', progress=5, total_hosts=len(targets), 
                      hosts_processed=0, current_target='Инициализация...')
            
            ts = datetime.now(MOSCOW_TZ).strftime('%Y%m%d_%H%M%S')
            res_dir = os.path.join('scan_results', f'nmap_{ts}')
            os.makedirs(res_dir, exist_ok=True)
            base = os.path.join(res_dir, 'scan')
            
            cmd = ['nmap', target]
            cmd.extend(parsed_args['rustscan'] + parsed_args['nmap'])
            if '-p' not in custom_args and ports: 
                cmd.extend(['-p', ports])
            for def_arg in ['-sV', '-sC', '-O', '-v']:
                if def_arg not in custom_args: 
                    cmd.append(def_arg)
            if not any(a in custom_args for a in ['-oA', '-oX', '-oG', '-oN']): 
                cmd.extend(['-oA', base])

            cmd_str = ' '.join(cmd)
            print(f"🚀 Запуск nmap job {scan_job_id}")
            print(f"   📜 Команда: {cmd_str}")
            print(f"   🎯 Цель: {target}")
            
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1)
            start_time = time.time()

            for line in iter(process.stdout.readline, ''):
                line = line.strip()
                if not line: continue
                job = ScanJob.query.get(scan_job_id)
                if not job: break
                if job.status == 'stopped':
                    process.terminate()
                    update_job(scan_job_id, status='stopped', progress=100, 
                              error_message='Остановлено пользователем', completed_at=datetime.now(MOSCOW_TZ))
                    return
                if job.status == 'paused':
                    if os.name != 'nt':
                        try:
                            os.kill(process.pid, 19)
                            while True:
                                cur_job = ScanJob.query.get(scan_job_id)
                                if not cur_job or cur_job.status != 'paused':
                                    break
                                time.sleep(0.5)
                            os.kill(process.pid, 18)
                        except ProcessLookupError:
                            break
                    else:
                        while True:
                            cur_job = ScanJob.query.get(scan_job_id)
                            if not cur_job or cur_job.status != 'paused':
                                break
                            time.sleep(0.5)
                    continue

                hm = re.search(r'Nmap scan report for (.+)', line)
                if hm: update_job(scan_job_id, current_target=hm.group(1))
                sm = re.search(r'(\d+(?:\.\d+)?)%.*?(\d+)\s+hosts scanned', line)
                pm = re.search(r'(\d+(?:\.\d+)?)%', line)
                if sm: update_job(scan_job_id, progress=int(float(sm.group(1))), hosts_processed=int(sm.group(2)))
                elif pm: update_job(scan_job_id, progress=int(float(pm.group(1))))
                else:
                    if time.time() - start_time > 2:
                        update_job(scan_job_id, progress=min(90, 10 + ((time.time()-start_time)/120)*80), current_target='Сканирование...')

            process.wait()
            _, stderr_data = process.communicate()
            
            job = ScanJob.query.get(scan_job_id)
            if not job: return

            if process.returncode != 0:
                err_msg = stderr_data.strip() or f"Код возврата: {process.returncode}"
                full_error = f"Ошибка выполнения:\n{err_msg}\n\nКоманда: {cmd_str}"
                update_job(scan_job_id, status='failed', progress=100, error_message=full_error, 
                          completed_at=datetime.now(MOSCOW_TZ))
                print(f"❌ Ошибка nmap job {scan_job_id}: {err_msg}")
                return

            update_job(scan_job_id, progress=98, current_target='Парсинг XML...')
            job.nmap_xml_path = f'{base}.xml'
            job.nmap_grep_path = f'{base}.gnmap'
            job.nmap_normal_path = f'{base}.nmap'
            
            if os.path.exists(job.nmap_xml_path):
                with open(job.nmap_xml_path, 'r', encoding='utf-8') as f:
                    job.nmap_xml_content = f.read()
                parse_nmap_results(scan_job_id, job.nmap_xml_path)
            
            if os.path.exists(job.nmap_grep_path):
                with open(job.nmap_grep_path, 'r', encoding='utf-8') as f:
                    job.nmap_grep_content = f.read()
            
            if os.path.exists(job.nmap_normal_path):
                with open(job.nmap_normal_path, 'r', encoding='utf-8') as f:
                    job.nmap_normal_content = f.read()
            
            update_job(scan_job_id, progress=100, status='completed', current_target='Готово', 
                      completed_at=datetime.now(MOSCOW_TZ))
            print(f"✅ Job {scan_job_id} завершён успешно")

        except FileNotFoundError:
            update_job(scan_job_id, status='failed', progress=100, 
                      error_message="Утилита nmap не найдена в PATH.", completed_at=datetime.now(MOSCOW_TZ))
            print("❌ nmap не установлен или не в PATH")
        except PermissionError:
            update_job(scan_job_id, status='failed', progress=100, 
                      error_message="Нет прав на выполнение nmap.", completed_at=datetime.now(MOSCOW_TZ))
            print("❌ Нет прав на nmap")
        except Exception as e:
            update_job(scan_job_id, status='failed', progress=100, 
                      error_message=f"Критическая ошибка: {str(e)}", completed_at=datetime.now(MOSCOW_TZ))
            print(f"❌ Критическая ошибка nmap job {scan_job_id}: {e}")
            import traceback
            traceback.print_exc()
        finally:
            db.session.remove()

def run_nslookup_scan(app, job_id, targets_text, dns_server='77.88.8.8', cli_args=''):
    """
    Выполняет nslookup для списка доменов.
    ВАЖНО: Первый аргумент - app (объект Flask), чтобы работать в контексте.
    """
    with app.app_context():
        try:
            db.session.remove()
            job = ScanJob.query.get(job_id)
            if not job:
                return

            job.status = 'running'
            job.started_at = datetime.now(MOSCOW_TZ)
            db.session.commit()

            domains = [d.strip() for d in targets_text.split('\n') if d.strip()]
            total = len(domains)
            output_lines = []

            for i, domain in enumerate(domains):
                job.current_target = domain
                job.progress = int((i / total) * 100)
                db.session.commit()

                # Формирование команды: nslookup [опции] домен [сервер]
                cmd = ['nslookup']
                if cli_args:
                    cmd.extend(cli_args.split())
                cmd.append(domain)
                if dns_server:
                    cmd.append(dns_server)

                result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
                output_lines.append(f">>> {domain}\n{result.stdout}")
                if result.stderr:
                    output_lines.append(f"ERROR: {result.stderr}")
                
                # Парсинг результатов сразу
                parse_nslookup_output(result.stdout, domain)

            job.status = 'completed'
            job.nslookup_output = "\n".join(output_lines)
            job.progress = 100
            job.completed_at = datetime.now(MOSCOW_TZ)
            db.session.commit()
            
        except Exception as e:
            if job:
                job.status = 'failed'
                job.error_message = str(e)
                job.nslookup_output = "\n".join(output_lines) if 'output_lines' in locals() else ""
                db.session.commit()
            print(f"❌ Ошибка nslookup: {e}")
            import traceback
            traceback.print_exc()
        finally:
            db.session.remove()

def parse_nslookup_output(output, domain_query):
    """Парсинг вывода nslookup и создание активов"""
    lines = output.split('\n')
    current_ip = None
    current_name = None
    
    for line in lines:
        line = line.strip()
        if line.startswith('Name:'):
            current_name = line.split(':', 1)[1].strip()
        elif line.startswith('Address:') and '#' not in line:
            current_ip = line.split(':', 1)[1].strip()
            
            if current_ip and current_name:
                try:
                    asset = Asset.query.filter_by(ip_address=current_ip).first()
                    if not asset:
                        asset = Asset(
                            ip_address=current_ip,
                            hostname=current_name,
                            status='up',
                            data_source='nslookup'
                        )
                        db.session.add(asset)
                        db.session.flush()
                        log_asset_change(asset.id, 'asset_created', 'ip_address', None, current_ip, None, 'Создан через nslookup')
                    
                    # Обновляем DNS имена
                    if asset.dns_names:
                        try:
                            names = json.loads(asset.dns_names)
                        except:
                            names = []
                    else:
                        names = []
                    
                    if current_name not in names:
                        names.append(current_name)
                        asset.dns_names = json.dumps(names)
                    
                    asset.last_scanned = datetime.now(MOSCOW_TZ)
                    db.session.commit()
                    print(f"✅ NSLookup: Добавлен/обновлен актив {current_ip} ({current_name})")
                    
                except Exception as e:
                    print(f"❌ Ошибка сохранения актива из nslookup: {e}")
                    db.session.rollback()
                
                current_name = None # Сброс для следующей записи

def parse_rustscan_results(scan_job_id, output, target):
    """Парсинг вывода Rustscan с обработкой квадратных скобок"""
    if not output:
        print(f"⚠️ ПУСТОЙ вывод rustscan для job {scan_job_id}")
        return
    
    parsed_count = 0
    
    for line in output.strip().split('\n'):
        line = line.strip()
        if not line or '->' not in line:
            continue
            
        try:
            parts = line.split('->')
            ip = parts[0].strip()
            ports_str = parts[1].strip() if len(parts) > 1 else ''
            
            # Удаляем квадратные скобки
            ports_str = ports_str.replace('[', '').replace(']', '')
            
            new_ports = [p.strip() for p in ports_str.split(',') if p.strip() and p.strip().isdigit()]
            
            if not new_ports:
                continue
            
            formatted_ports = [f"{p}/tcp" for p in new_ports]
            ports_string = ', '.join(sorted(formatted_ports, key=lambda x: int(x.split('/')[0])))
            
            asset = Asset.query.filter_by(ip_address=ip).first()
            if not asset:
                asset = Asset(ip_address=ip, status='up', data_source='scanning',
                             rustscan_ports=ports_string, last_rustscan=datetime.now(MOSCOW_TZ))
                db.session.add(asset)
                db.session.flush()
                log_asset_change(asset.id, 'asset_created', 'ip_address', None, ip, scan_job_id, 'Создан через rustscan')
            else:
                asset.rustscan_ports = ports_string
                asset.last_rustscan = datetime.now(MOSCOW_TZ)
                
                all_ports = set()
                if asset.rustscan_ports: all_ports.update(asset.rustscan_ports.split(', '))
                if asset.nmap_ports: all_ports.update(asset.nmap_ports.split(', '))
                asset.open_ports = ', '.join(sorted(all_ports, key=lambda x: int(x.split('/')[0]) if '/' in x else int(x)))
                asset.device_role, asset.device_tags = detect_device_role_and_tags(asset.open_ports)
            
            asset.last_scanned = datetime.now(MOSCOW_TZ)
            asset.status = 'up'
            
            scanners = json.loads(asset.scanners_used) if asset.scanners_used else []
            if 'rustscan' not in scanners:
                scanners.append('rustscan')
                asset.scanners_used = json.dumps(scanners)
            
            db.session.add(ScanResult(asset_id=asset.id, ip_address=ip, scan_job_id=scan_job_id, 
                                     scan_type='rustscan', ports=json.dumps(formatted_ports), 
                                     scanned_at=datetime.now(MOSCOW_TZ)))
            
            parsed_count += 1
            
        except Exception as e:
            print(f"❌ Ошибка парсинга строки rustscan: {line} - {e}")
            import traceback
            traceback.print_exc()
    
    if parsed_count > 0:
        db.session.commit()
        print(f"🎉 Закоммичено {parsed_count} активов из rustscan job {scan_job_id}")
    else:
        print(f"⚠️ Ни один актив не был обновлён")
        db.session.rollback()

def parse_nmap_results(scan_job_id, xml_path):
    """Парсинг Nmap XML с разделением полей"""
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
        for host in root.findall('host'):
            st = host.find('status')
            if st is None or st.get('state') != 'up': continue
            addr = host.find('address')
            ip = addr.get('addr') if addr is not None else None
            if not ip: continue
            
            hostname, os_info = 'Unknown', 'Unknown'
            hn = host.find('hostnames')
            if hn is not None:
                ne = hn.find('hostname')
                if ne is not None: hostname = ne.get('name')
            oe = host.find('os')
            if oe is not None:
                om = oe.find('osmatch')
                if om is not None: os_info = om.get('name')
            
            ports, services = [], []
            pe = host.find('ports')
            if pe is not None:
                for port in pe.findall('port'):
                    state = port.find('state')
                    if state is not None and state.get('state') == 'open':
                        pid, proto = port.get('portid'), port.get('protocol')
                        svc = port.find('service')
                        s = {'name': svc.get('name') if svc is not None else '', 
                             'product': svc.get('product') if svc is not None else '', 
                             'version': svc.get('version') if svc is not None else '', 
                             'extrainfo': svc.get('extrainfo') if svc is not None else ''}
                        pstr = f"{pid}/{proto}"
                        ports.append(pstr)
                        services.append(s)
                        asset = Asset.query.filter_by(ip_address=ip).first()
                        if asset:
                            ex = ServiceInventory.query.filter_by(asset_id=asset.id, port=pstr).first()
                            if ex:
                                ex.service_name = s['name']
                                ex.product = s['product']
                                ex.version = s['version']
                                ex.extrainfo = s['extrainfo']
                                ex.last_seen = datetime.now(MOSCOW_TZ)
                                ex.is_active = True
                            else:
                                db.session.add(ServiceInventory(asset_id=asset.id, port=pstr, protocol=proto, 
                                                               service_name=s['name'], product=s['product'], 
                                                               version=s['version'], extrainfo=s['extrainfo']))
                                log_asset_change(asset.id, 'service_detected', 'service_inventory', None, s['name'], scan_job_id, f'Порт {pstr}')
            
            asset = Asset.query.filter_by(ip_address=ip).first()
            if not asset:
                asset = Asset(ip_address=ip, status='up')
                db.session.add(asset)
                db.session.flush()
            
            if asset.os_info != os_info and os_info != 'Unknown':
                log_asset_change(asset.id, 'os_changed', 'os_info', asset.os_info, os_info, scan_job_id)
            asset.hostname = hostname if hostname != 'Unknown' else asset.hostname
            asset.os_info = os_info if os_info != 'Unknown' else asset.os_info
            
            if ports:
                ports_string = ', '.join(sorted(ports, key=lambda x: int(x.split('/')[0])))
                old_nmap = asset.nmap_ports or ''
                if old_nmap != ports_string:
                    log_asset_change(asset.id, 'nmap_ports_changed', 'nmap_ports', old_nmap, ports_string, scan_job_id)
                asset.nmap_ports = ports_string
                all_ports = set()
                if asset.rustscan_ports: all_ports.update(asset.rustscan_ports.split(', '))
                if asset.nmap_ports: all_ports.update(asset.nmap_ports.split(', '))
                asset.open_ports = ', '.join(sorted(all_ports, key=lambda x: int(x.split('/')[0]) if '/' in x else int(x)))
                asset.device_role, asset.device_tags = detect_device_role_and_tags(asset.open_ports, services)
            
            asset.last_scanned = datetime.now(MOSCOW_TZ)
            asset.last_nmap = datetime.now(MOSCOW_TZ)
            asset.data_source = 'scanning'
            scanners = json.loads(asset.scanners_used) if asset.scanners_used else []
            if 'nmap' not in scanners:
                scanners.append('nmap')
                asset.scanners_used = json.dumps(scanners)
            
            db.session.add(ScanResult(asset_id=asset.id, ip_address=ip, scan_job_id=scan_job_id, 
                                     scan_type='nmap', ports=json.dumps(ports), services=json.dumps(services), 
                                     os_detection=os_info, scanned_at=datetime.now(MOSCOW_TZ)))
        
        db.session.commit()
        print(f"🎉 Закоммичены результаты nmap job {scan_job_id}")
    except Exception as e:
        print(f"❌ Ошибка парсинга nmap XML: {e}")
        import traceback
        traceback.print_exc()
```

### 📄 `utils.py`

```python
from datetime import datetime, timezone, timedelta

# 🔥 Московское время (UTC+3)
MOSCOW_TZ = timezone(timedelta(hours=3))

def to_moscow_time(dt):
    """Конвертирует datetime в московское время"""
    if not dt:
        return None
    if dt.tzinfo is None:
        # Если время без timezone, считаем что это UTC
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(MOSCOW_TZ)

def format_moscow_time(dt, format_str='%Y-%m-%d %H:%M:%S'):
    """Форматирует datetime в строку с московским временем"""
    if not dt:
        return '—'
    moscow_dt = to_moscow_time(dt)
    return moscow_dt.strftime(format_str)
```

### 📄 `utils/__init__.py`

```python
# utils/__init__.py

import json
import os
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta

# Ленивый импорт для избежания циклических зависимостей
def get_db():
    from extensions import db
    return db

def get_models():
    from models import Asset, Group, AssetChangeLog, ServiceInventory, ScanResult
    return Asset, Group, AssetChangeLog, ServiceInventory, ScanResult

# ────────────────────────────────────────────────────────────────
# ВРЕМЯ (Москва)
# ────────────────────────────────────────────────────────────────

MOSCOW_TZ = timezone(timedelta(hours=3))

def to_moscow_time(dt):
    """Конвертирует datetime в московское время"""
    if not dt:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(MOSCOW_TZ)

def format_moscow_time(dt, format_str='%Y-%m-%d %H:%M:%S'):
    """Форматирует datetime в строку с московским временем"""
    if not dt:
        return '—'
    moscow_dt = to_moscow_time(dt)
    return moscow_dt.strftime(format_str)

# ────────────────────────────────────────────────────────────────
# РАБОТА С АКТИВАМИ (Создание, Обновление, DNS)
# ────────────────────────────────────────────────────────────────

def create_asset_if_not_exists(ip_string, hostname=None, group_id=None, source='scan'):
    """Создает актив если не существует, иначе обновляет hostname если пустой"""
    Asset, _, _, _, _ = get_models()
    db = get_db()
    
    asset = Asset.query.filter_by(ip_address=ip_string).first()
    if not asset:
        asset = Asset(
            ip_address=ip_string, 
            hostname=hostname, 
            group_id=group_id,
            data_source=source
        )
        db.session.add(asset)
        db.session.commit()
    elif hostname and not asset.hostname:
        asset.hostname = hostname
        db.session.commit()
        
    return asset

def update_asset_dns_names(asset, domain_name):
    """Обновление списка DNS имен актива"""
    if not domain_name:
        return
        
    db = get_db()
    
    current_names = []
    if asset.dns_names:
        try:
            current_names = json.loads(asset.dns_names)
        except Exception:
            current_names = []
            
    if domain_name not in current_names:
        current_names.append(domain_name)
        asset.dns_names = json.dumps(current_names)
        db.session.commit()

def log_asset_change(asset_id, change_type, field_name, old_value, new_value, scan_job_id=None, notes=None):
    """Логирование изменений актива"""
    _, _, AssetChangeLog, _, _ = get_models()
    db = get_db()
    
    change = AssetChangeLog(
        asset_id=asset_id, 
        change_type=change_type, 
        field_name=field_name,
        old_value=json.dumps(old_value) if old_value else None,
        new_value=json.dumps(new_value) if new_value else None,
        scan_job_id=scan_job_id, 
        notes=notes
    )
    db.session.add(change)
    # Коммит делается вызывающей стороной или внутри транзакции

# ────────────────────────────────────────────────────────────────
# ТАКСОНОМИЯ И РОЛИ
# ────────────────────────────────────────────────────────────────

def detect_device_role_and_tags(ports_str, services_data=None):
    """Определяет роль устройства и набор тегов на основе портов и сервисов"""
    ports_set = {p.strip().split('/')[0] for p in (ports_str or '').split(',') if p.strip()}
    service_str = ' '.join([f"{s.get('name','')} {s.get('product','')} {s.get('version','')} {s.get('extrainfo','')}" for s in (services_data or [])]).lower()
    
    tags = []
    rules = [
        ("Windows Server", {"ports": {"445", "135", "139", "3389"}, "svc": ["microsoft-ds", "smb", "windows", "rdp"]}, 2),
        ("Linux Server", {"ports": {"22", "80", "443"}, "svc": ["openssh", "linux", "ubuntu", "centos", "apache", "nginx"]}, 2),
        ("Контроллер домена (AD)", {"ports": {"88", "389", "445", "636"}, "svc": ["ldap", "kpasswd", "microsoft-ds"]}, 2),
        ("База данных", {"ports": {"1433", "3306", "5432", "27017", "6379"}, "svc": ["mysql", "postgresql", "mongodb", "redis", "mssql"]}, 1),
        ("Веб-сервер", {"ports": {"80", "443", "8080"}, "svc": ["http", "nginx", "apache", "iis"]}, 1),
        ("Почтовый сервер", {"ports": {"25", "110", "143", "465", "587"}, "svc": ["smtp", "pop3", "imap", "exchange"]}, 2),
        ("DNS Сервер", {"ports": {"53"}, "svc": ["dns", "bind"]}, 1),
        ("Файловый сервер", {"ports": {"21", "445", "2049"}, "svc": ["ftp", "smb", "nfs"]}, 1),
        ("Принтер", {"ports": {"515", "631", "9100"}, "svc": ["ipp", "jetdirect", "printer"]}, 1),
        ("Сетевое оборудование", {"ports": {"161", "162", "23"}, "svc": ["snmp", "telnet", "cisco"]}, 1),
    ]
    
    matched_role = "Не определено"
    max_score = 0
    
    for role, criteria, min_match in rules:
        score = 0
        current_tags = []
        
        port_matches = ports_set.intersection(criteria["ports"])
        if port_matches:
            score += len(port_matches)
            current_tags += [f"port:{p}" for p in port_matches]
            
        svc_matches = [s for s in criteria["svc"] if s in service_str]
        if svc_matches:
            score += len(svc_matches)
            current_tags += [f"svc:{s}" for s in svc_matches]
            
        if score >= min_match and score > max_score:
            max_score = score
            matched_role = role
            tags = current_tags
            
    return matched_role, json.dumps(tags)

def generate_asset_taxonomy(asset, services=None):
    """Генерирует таксономию актива"""
    ports = set()
    if asset.open_ports:
        for p in asset.open_ports.split(','):
            port_num = p.strip().split('/')[0]
            if port_num.isdigit():
                ports.add(port_num)
    
    device_class = "Не классифицировано"
    device_subclass = ""
    
    if asset.os_info:
        os_lower = asset.os_info.lower()
        if 'windows' in os_lower: 
            device_class = "Сервер/АРМ (Windows)"
            device_subclass = "Server" if 'server' in os_lower else "Workstation"
        elif 'linux' in os_lower: 
            device_class = "Сервер/АРМ (Linux)"
            device_subclass = "Linux"
        elif any(x in os_lower for x in ['cisco', 'juniper', 'switch', 'router']): 
            device_class = "Сетевое оборудование"
            device_subclass = "Network"
            
    if device_class == "Не классифицировано":
        if '3389' in ports or '445' in ports: 
            device_class = "Сервер/АРМ (Windows)"
        elif '22' in ports: 
            device_class = "Сервер/АРМ (Linux)"
        elif '161' in ports: 
            device_class = "Сетевое оборудование"

    role = asset.device_role or "Не определена"
    
    svc_map = {
        '22': ('Удаленный доступ', 'SSH'), '80': ('Веб', 'HTTP'), '443': ('Веб', 'HTTPS'),
        '3306': ('БД', 'MySQL'), '5432': ('БД', 'PostgreSQL'), '3389': ('RDP', 'RDP'),
        '53': ('Инфра', 'DNS'), '25': ('Почта', 'SMTP')
    }
    
    grouped_services = {}
    for port in sorted(ports):
        if port in svc_map:
            cat, svc_name = svc_map[port]
            grouped_services.setdefault(cat, []).append(svc_name)
            
    sources = [{'name': 'Сканирование', 'type': 'Автоматический'}]
        
    return {
        'asset_id': asset.id, 
        'ip_address': asset.ip_address, 
        'hostname': asset.hostname or 'N/A', 
        'nodes': [
            {'id': 'device', 'title': 'Класс', 'value': device_class, 'children': [{'title': 'Подкласс', 'value': device_subclass}] if device_subclass else []},
            {'id': 'role', 'title': 'Роль', 'value': role, 'children': []},
            {'id': 'services', 'title': 'Сервисы', 'value': f"{len(ports)} портов", 'children': [{'title': k, 'value': ', '.join(v)} for k, v in grouped_services.items()]},
            {'id': 'sources', 'title': 'Источники', 'value': 'Scan', 'children': sources}
        ]
    }

# ────────────────────────────────────────────────────────────────
# ПАРСИНГ NMAP XML
# ────────────────────────────────────────────────────────────────

def parse_nmap_xml(filepath):
    """Парсинг Nmap XML файла"""
    try:
        tree = ET.parse(filepath)
        root = tree.getroot()
        assets = []
        
        for host in root.findall('host'):
            status = host.find('status')
            if status is None or status.get('state') != 'up':
                continue
            
            addr = host.find('address')
            ip = addr.get('addr') if addr is not None else None
            if not ip: continue
            
            hostname = None
            hostnames = host.find('hostnames')
            if hostnames is not None:
                name_elem = hostnames.find('hostname')
                if name_elem is not None:
                    hostname = name_elem.get('name')
            
            os_info = None
            os_elem = host.find('os')
            if os_elem is not None:
                os_match = os_elem.find('osmatch')
                if os_match is not None:
                    os_info = os_match.get('name')
            
            ports = []
            ports_elem = host.find('ports')
            if ports_elem is not None:
                for port in ports_elem.findall('port'):
                    state = port.find('state')
                    if state is not None and state.get('state') == 'open':
                        port_id = port.get('portid')
                        service = port.find('service')
                        svc_name = service.get('name') if service is not None else ''
                        ports.append(f"{port_id}/{svc_name}" if svc_name else port_id)
            
            assets.append({
                'ip_address': ip,
                'hostname': hostname,
                'os_info': os_info,
                'status': 'up',
                'open_ports': ', '.join(ports),
                'ports_list': json.dumps(ports)
            })
        
        return assets
    except Exception as e:
        print(f"Ошибка парсинга Nmap XML: {e}")
        return []

# ────────────────────────────────────────────────────────────────
# ГРУППЫ И ФИЛЬТРЫ
# ────────────────────────────────────────────────────────────────

def build_group_tree(groups, parent_id=None, depth=0):
    """Построение дерева групп"""
    Asset, Group, _, _, _ = get_models()
    from sqlalchemy import and_, or_
    
    tree = []
    # Фильтруем группы текущего уровня
    current_level_groups = [g for g in groups if g.parent_id == parent_id]

    for group in current_level_groups:
        # Рекурсивно строим поддерево
        children = build_group_tree(groups, group.id, depth + 1)

        # Подсчёт активов: прямые + все вложенные группы
        count = 0
        if group.is_dynamic and group.filter_rules:
            try:
                filter_struct = json.loads(group.filter_rules)
                base_query = Asset.query
                complex_query = build_complex_query(Asset, filter_struct, base_query)
                count = complex_query.count()
            except Exception as e:
                print(f"Ошибка подсчета динамической группы {group.name}: {e}")
                count = 0
        else:
            count = group.assets.count()

        # Добавляем активы из всех вложенных групп
        for child in children:
            count += child.get('asset_count', 0)

        tree.append({
            'id': group.id,
            'name': group.name,
            'children': children,
            'count': count,
            'asset_count': count,
            'is_dynamic': group.is_dynamic,
            'parent_id': group.parent_id,
            'depth': depth
        })
    return tree

def build_complex_query(model, filters_structure, base_query=None):
    """Построение SQL запроса по JSON фильтру"""
    from sqlalchemy import and_, or_
    
    if base_query is None:
        base_query = model.query
        
    if not filters_structure or 'conditions' not in filters_structure:
        return base_query
        
    logic = filters_structure.get('logic', 'AND')
    conditions = filters_structure.get('conditions', [])
    sqlalchemy_filters = []
    
    for item in conditions:
        if item.get('type') == 'group':
            sub_query = build_complex_query(model, item, model.query)
            ids = [a.id for a in sub_query.all()]
            if ids:
                sqlalchemy_filters.append(model.id.in_(ids))
            elif logic == 'AND':
                sqlalchemy_filters.append(model.id == -1)
        else:
            field = item.get('field')
            op = item.get('op')
            val = item.get('value')
            
            col = getattr(model, field, None)
            if col is None: continue
                
            if op == 'eq': sqlalchemy_filters.append(col == val)
            elif op == 'ne': sqlalchemy_filters.append(col != val)
            elif op == 'like': sqlalchemy_filters.append(col.like(f'%{val}%'))
            elif op == 'gt': sqlalchemy_filters.append(col > val)
            elif op == 'lt': sqlalchemy_filters.append(col < val)
            elif op == 'in': sqlalchemy_filters.append(col.in_(val.split(',')))
    
    if sqlalchemy_filters:
        if logic == 'AND':
            base_query = base_query.filter(and_(*sqlalchemy_filters))
        else:
            base_query = base_query.filter(or_(*sqlalchemy_filters))
            
    return base_query

__all__ = [
    'to_moscow_time',
    'format_moscow_time',
    'create_asset_if_not_exists',
    'update_asset_dns_names',
    'log_asset_change',
    'detect_device_role_and_tags',
    'generate_asset_taxonomy',
    'parse_nmap_xml',
    'build_group_tree',
    'build_complex_query'
]
```

### 📄 `utils/network_utils.py`

```python
import ipaddress
from models import db, Group

def create_cidr_groups(network_str, mask_prefix, parent_id=None):
    """
    Создает группы для подсетей внутри указанной сети.
    
    :param network_str: Строка сети в формате CIDR (например, "192.168.0.0/16")
    :param mask_prefix: Префикс маски для подгрупп (например, 24 для /24)
    :param parent_id: ID родительской группы (опционально)
    :return: Список созданных объектов Group
    """
    try:
        network = ipaddress.ip_network(network_str, strict=False)
        subnets = network.subnets(new_prefix=mask_prefix)
        
        created_groups = []
        
        for subnet in subnets:
            group_name = str(subnet)
            
            # Проверяем, существует ли уже группа с таким именем и родителем
            existing_group = Group.query.filter_by(
                name=group_name, 
                parent_id=parent_id
            ).first()
            
            if not existing_group:
                new_group = Group(
                    name=group_name,
                    parent_id=parent_id,
                    description=f"Автоматически созданная группа для подсети {group_name}"
                )
                db.session.add(new_group)
                created_groups.append(new_group)
        
        db.session.commit()
        return created_groups
    
    except Exception as e:
        db.session.rollback()
        raise ValueError(f"Ошибка при создании CIDR групп: {str(e)}")
```

### 📄 `utils/osquery_validator.py`

```python
import re, json

OSQUERY_SCHEMA = {
    "system_info": ["hostname", "cpu_brand", "cpu_type", "cpu_logical_cores", "cpu_physical_cores", "physical_memory", "hardware_vendor", "hardware_model"],
    "os_version": ["name", "version", "major", "minor", "patch", "build", "platform", "platform_like", "codename"],
    "processes": ["pid", "name", "path", "cmdline", "state", "parent", "uid", "gid", "start_time", "resident_size", "total_size"],
    "users": ["uid", "gid", "username", "description", "directory", "shell", "uuid"],
    "network_connections": ["pid", "local_address", "local_port", "remote_address", "remote_port", "state", "protocol", "family"],
    "listening_ports": ["pid", "port", "address", "protocol", "family"],
    "kernel_info": ["version", "arguments", "path", "device", "driver"],
    "uptime": ["days", "hours", "minutes", "seconds", "total_seconds"],
    "hash": ["path", "md5", "sha1", "sha256", "ssdeep", "file_size"],
    "file": ["path", "filename", "directory", "mode", "type", "size", "last_accessed", "last_modified", "last_status_change", "uid", "gid"],
    "crontab": ["uid", "minute", "hour", "day_of_month", "month", "day_of_week", "command", "path"],
    "logged_in_users": ["type", "user", "tty", "host", "time", "pid"],
    "routes": ["destination", "gateway", "mask", "mtu", "metric", "type", "flags", "interface"],
    "groups": ["gid", "groupname"]
}

def validate_osquery_query(query):
    errors, warnings = [], []
    query = query.strip().rstrip(';')
    if not re.match(r'(?i)^\s*SELECT\s+', query): errors.append("Запрос должен начинаться с SELECT"); return errors, warnings
    from_match = re.search(r'(?i)\bFROM\s+([\w\.]+)', query)
    if not from_match: errors.append("Отсутствует таблица в FROM"); return errors, warnings
    table_name = from_match.group(1).split('.')[0].lower()
    select_match = re.search(r'(?i)SELECT\s+(.*?)\s+FROM', query, re.DOTALL)
    if not select_match: errors.append("Не удалось извлечь список колонок"); return errors, warnings
    cols_str = select_match.group(1).strip()
    if cols_str == '*': warnings.append("Использование SELECT * не рекомендуется"); return errors, warnings
    cols = [c.strip().split(' as ')[0].split(' AS ')[0].strip().split('(')[-1] for c in cols_str.split(',')]
    cols = [c for c in cols if c and c != ')']
    if table_name in OSQUERY_SCHEMA:
        valid_cols = [vc.lower() for vc in OSQUERY_SCHEMA[table_name]]
        for col in cols:
            if '(' in col or col.lower() in ['true', 'false']: continue
            if col.lower() not in valid_cols: errors.append(f"Колонка '{col}' не найдена в таблице '{table_name}'")
    else: warnings.append(f"Таблица '{table_name}' отсутствует в словаре валидации.")
    return errors, warnings

def validate_osquery_config(config_dict):
    errors, warnings = [], []
    for sec in ["options", "schedule"]:
        if sec not in config_dict: errors.append(f"Отсутствует обязательный раздел: '{sec}'")
    if errors: return errors, warnings
    for name, query_obj in config_dict.get("schedule", {}).items():
        if not isinstance(query_obj, dict) or "query" not in query_obj: errors.append(f"schedule.{name}: некорректная структура"); continue
        q_errors, q_warnings = validate_osquery_query(query_obj["query"])
        for e in q_errors: errors.append(f"schedule.{name}: {e}")
        for w in q_warnings: warnings.append(f"schedule.{name}: {w}")
    return errors, warnings

```

### 📄 `utils/wazuh_api.py`

```python
import requests
from datetime import datetime

class WazuhAPI:
    def __init__(self, url, user, password, verify_ssl=False):
        self.url = url.rstrip('/'); self.auth = (user, password); self.verify = verify_ssl
        self.token = None; self.token_expires = None
    def _get_token(self):
        if self.token and self.token_expires and self.token_expires > datetime.utcnow(): return self.token
        try:
            res = requests.post(f"{self.url}/security/user/authenticate", auth=self.auth, verify=self.verify); res.raise_for_status()
            data = res.json(); self.token = data['data']['token']; self.token_expires = datetime.utcnow() + 800; return self.token
        except Exception as e: raise ConnectionError(f"Ошибка авторизации Wazuh: {str(e)}")
    def get_agents_page(self, limit=500, offset=0):
        token = self._get_token(); headers = {"Authorization": f"Bearer {token}"}
        params = {"limit": limit, "offset": offset, "sort": "-lastKeepAlive"}
        res = requests.get(f"{self.url}/agents", headers=headers, params=params, verify=self.verify, timeout=15); res.raise_for_status(); return res.json()
    def fetch_all_agents(self):
        all_agents = []; offset = 0
        while True:
            try:
                data = self.get_agents_page(limit=500, offset=offset)
                agents = data.get('data', {}).get('affected_items', []); all_agents.extend(agents)
                if len(agents) < 500: break
                offset += 500
            except Exception as e: raise Exception(f"Ошибка получения агентов: {str(e)}")
        return all_agents

```

### 📄 `routes/__init__.py`

```python
from .main import main_bp, groups_bp
from .scans import scans_bp
from .wazuh import wazuh_bp
from .osquery import osquery_bp
from .utilities import utilities_bp

def register_blueprints(app):
    app.register_blueprint(main_bp)
    app.register_blueprint(scans_bp)
    app.register_blueprint(wazuh_bp)
    app.register_blueprint(osquery_bp)
    app.register_blueprint(utilities_bp)
    app.register_blueprint(groups_bp)

```

### 📄 `routes/main.py`

```python
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app
from extensions import db
from models import Group, Asset, AssetChangeLog, ServiceInventory, ScanResult, ScanJob, WazuhConfig
# Исправленный импорт сканеров из корня проекта (файл scanner.py)
from scanner import run_rustscan_scan, run_nmap_scan, run_nslookup_scan
from utils import build_group_tree, build_complex_query, format_moscow_time, parse_nmap_xml, generate_asset_taxonomy
from sqlalchemy import func, and_, or_
import json
import os
import threading
import ipaddress
from datetime import datetime, timezone, timedelta
from werkzeug.utils import secure_filename

# Локальный часовой пояс
MOSCOW_TZ = timezone(timedelta(hours=3))

main_bp = Blueprint('main', __name__)
groups_bp = Blueprint('groups', __name__)

# ────────────────────────────────────────────────────────────────
# УТИЛИТЫ ДЛЯ CIDR (Локальная реализация)
# ────────────────────────────────────────────────────────────────

def create_cidr_groups_logic(network_str, mask_bits, parent_id=None, group_name_prefix="Subnet"):
    try:
        network = ipaddress.ip_network(network_str, strict=False)
        subnets = list(network.subnets(new_prefix=int(mask_bits)))
        
        created_ids = []
        for subnet in subnets:
            g_name = f"{group_name_prefix} {subnet}"
            new_group = Group(name=g_name, parent_id=parent_id, is_dynamic=False)
            db.session.add(new_group)
            db.session.flush()
            created_ids.append(new_group.id)
            
        db.session.commit()
        return len(created_ids)
    except Exception as e:
        db.session.rollback()
        raise e

# ────────────────────────────────────────────────────────────────
# ОСНОВНЫЕ МАРШРУТЫ
# ────────────────────────────────────────────────────────────────

@main_bp.route('/')
def index():
    all_groups = Group.query.all()
    group_tree = build_group_tree(all_groups)
    assets = Asset.query.all()
    ungrouped_count = Asset.query.filter(Asset.group_id.is_(None)).count()
    
    current_filter = request.args.get('group_id')
    if request.args.get('ungrouped') == 'true': 
        current_filter = 'ungrouped'
    elif not current_filter or current_filter == 'all': 
        current_filter = 'ungrouped'
        
    return render_template('index.html', assets=assets, group_tree=group_tree, all_groups=all_groups, ungrouped_count=ungrouped_count, current_filter=current_filter)

@main_bp.route('/api/assets', methods=['GET'])
def get_assets_api():
    query = Asset.query
    filters_raw = request.args.get('filters')
    ungrouped = request.args.get('ungrouped')
    
    # Обработка фильтра "Без группы"
    if ungrouped and ungrouped.lower() == 'true':
        query = query.filter(Asset.group_id.is_(None))
    else:
        group_id = request.args.get('group_id')
        if group_id and group_id != 'all':
            try:
                group_id_int = int(group_id)
                group = Group.query.get(group_id_int)
                if group and group.is_dynamic and group.filter_rules:
                    try:
                        query = build_complex_query(Asset, json.loads(group.filter_rules), query)
                    except:
                        query = query.filter(Asset.group_id == group_id_int)
                else:
                    query = query.filter(Asset.group_id == group_id_int)
            except ValueError:
                return jsonify({'error': 'Invalid group_id'}), 400
                
    # Обработка сложных фильтров
    if filters_raw:
        try:
            query = build_complex_query(Asset, json.loads(filters_raw), query)
        except:
            pass
            
    assets = query.all()
    data = [{
        'id': a.id, 
        'ip': a.ip_address, 
        'hostname': a.hostname, 
        'os': a.os_info, 
        'ports': a.open_ports, 
        'group': a.group.name if a.group else 'Без группы', 
        'last_scan': format_moscow_time(a.last_scanned if hasattr(a, 'last_scanned') else None, '%Y-%m-%d %H:%M'),
        'dns_names': json.loads(a.dns_names) if a.dns_names else []
    } for a in assets]
    
    return jsonify(data)

@main_bp.route('/api/analytics', methods=['GET'])
def get_analytics():
    filters_raw = request.args.get('filters')
    group_by_field = request.args.get('group_by', 'os_info')
    
    query = Asset.query
    if filters_raw:
        try:
            query = build_complex_query(Asset, json.loads(filters_raw), query)
        except:
            pass
            
    group_col = getattr(Asset, group_by_field, Asset.os_info)
    results = db.session.query(group_col, func.count(Asset.id).label('count')).group_by(group_col).all()
    
    return jsonify([{'label': r[0] or 'Unknown', 'value': r[1]} for r in results])

# ────────────────────────────────────────────────────────────────
# API ГРУПП
# ────────────────────────────────────────────────────────────────

@groups_bp.route('/api/groups', methods=['POST'])
def api_create_group():
    data = request.json
    name = data.get('name')
    parent_id = data.get('parent_id')
    is_dynamic = data.get('is_dynamic', False)
    filter_rules = data.get('filter_rules', [])
    cidr_network = data.get('cidr_network')
    cidr_mask = data.get('cidr_mask')
    
    if parent_id == '':
        parent_id = None
    
    # Обработка CIDR
    if cidr_network:
        try:
            created_count = create_cidr_groups_logic(cidr_network, int(cidr_mask or 24), parent_id)
            return jsonify({'success': True, 'message': f'Создано {created_count} групп', 'count': created_count}), 201
        except Exception as e:
            return jsonify({'error': str(e)}), 400
    
    # Обработка динамической группы
    filter_query = None
    if is_dynamic and filter_rules:
        filter_query = json.dumps(filter_rules)
    
    if not name and not cidr_network:
        return jsonify({'error': 'Имя обязательно'}), 400
    
    # Если это не CIDR (который создает несколько групп), создаем одну
    if not cidr_network:
        new_group = Group(
            name=name,
            parent_id=parent_id,
            filter_rules=filter_query, # Используем поле filter_rules
            is_dynamic=is_dynamic
        )
        db.session.add(new_group)
        db.session.commit()
        return jsonify({'id': new_group.id, 'name': new_group.name, 'is_dynamic': is_dynamic}), 201
        
    return jsonify({'error': 'Неизвестный режим создания'}), 400

@groups_bp.route('/api/groups/<int:group_id>', methods=['GET', 'PUT', 'DELETE'])
def group_actions(group_id):
    group = Group.query.get_or_404(group_id)

    if request.method == 'GET':
        rules = []
        if group.filter_rules:
            try: rules = json.loads(group.filter_rules)
            except: pass
            
        return jsonify({
            'id': group.id,
            'name': group.name,
            'parent_id': group.parent_id,
            'is_dynamic': group.is_dynamic,
            'filter_rules': rules
        })

    if request.method == 'PUT':
        data = request.json
        group.name = data.get('name', group.name)
        
        p_id = data.get('parent_id')
        group.parent_id = p_id if p_id != '' else None
        
        if 'is_dynamic' in data:
            group.is_dynamic = data['is_dynamic']
            
        if 'filter_rules' in data:
            group.filter_rules = json.dumps(data['filter_rules']) if data['filter_rules'] else None
            
        db.session.commit()
        return jsonify({'status': 'success'})

    if request.method == 'DELETE':
        move_to_id = request.args.get('move_to')
        if move_to_id:
            Asset.query.filter_by(group_id=group_id).update({'group_id': move_to_id})
        else:
            Asset.query.filter_by(group_id=group_id).update({'group_id': None})
            
        db.session.delete(group)
        db.session.commit()
        return jsonify({'status': 'success'})

@main_bp.route('/api/groups/<int:id>', methods=['DELETE'])
def api_delete_group(id):
    # Дублирующий маршрут для совместимости, лучше использовать groups_bp
    group = Group.query.get_or_404(id)
    move_to_id = request.args.get('move_to')
    if move_to_id:
        Asset.query.filter_by(group_id=id).update({'group_id': move_to_id})
    db.session.delete(group)
    db.session.commit()
    return jsonify({'success': True})

@main_bp.route('/groups', methods=['POST'])
def manage_groups():
    # Старый маршрут для форм, можно удалить если используется только API
    name = request.form.get('name')
    parent_id = request.form.get('parent_id')
    if parent_id == '': parent_id = None
    db.session.add(Group(name=name, parent_id=parent_id))
    db.session.commit()
    return redirect(url_for('main.index'))

@main_bp.route('/api/groups/tree')
def api_get_tree():
    all_groups = Group.query.all()
    tree = build_group_tree(all_groups)
    
    # Преобразуем дерево в плоский список с сохранением всех полей включая depth
    flat_list = []
    def flatten(nodes):
        for node in nodes:
            flat_list.append({
                'id': node['id'], 
                'name': node['name'],
                'count': node['count'],
                'asset_count': node['asset_count'],
                'parent_id': node.get('parent_id'),
                'is_dynamic': node.get('is_dynamic', False),
                'depth': node.get('depth', 0)
            })
            flatten(node['children'])
    
    flatten(tree)
    
    ungrouped_count = Asset.query.filter(Asset.group_id.is_(None)).count()
    
    return jsonify({'tree': tree, 'flat': flat_list, 'ungrouped_count': ungrouped_count})

# ────────────────────────────────────────────────────────────────
# АКТИВЫ: ДЕТАЛИ, ИСТОРИЯ, ТАКСОНОМИЯ
# ────────────────────────────────────────────────────────────────

@main_bp.route('/asset/<int:id>')
def asset_detail(id):
    asset = Asset.query.get_or_404(id)
    all_groups = Group.query.all()
    services = ServiceInventory.query.filter_by(asset_id=id).all() # Убрал is_active если нет такого поля
    return render_template('asset_detail.html', asset=asset, all_groups=all_groups, services=services)

@main_bp.route('/asset/<int:id>/history')
def asset_history(id):
    asset = Asset.query.get_or_404(id)
    all_groups = Group.query.all()
    group_tree = build_group_tree(all_groups)
    changes = AssetChangeLog.query.filter_by(asset_id=id).order_by(AssetChangeLog.changed_at.desc()).all()
    services = ServiceInventory.query.filter_by(asset_id=id).all()
    return render_template('asset_history.html', asset=asset, changes=changes, services=services, group_tree=group_tree, all_groups=all_groups)

@main_bp.route('/asset/<int:id>/taxonomy')
def asset_taxonomy(id):
    asset = Asset.query.get_or_404(id)
    all_groups = Group.query.all()
    services = ServiceInventory.query.filter_by(asset_id=id).all()
    taxonomy_data = generate_asset_taxonomy(asset, services)
    return render_template('asset_taxonomy.html', asset=asset, taxonomy=taxonomy_data, all_groups=all_groups)

@main_bp.route('/api/assets/<int:asset_id>/scans')
def get_asset_scans(asset_id):
    search = request.args.get('search', '').strip()
    query = db.session.query(ScanResult, ScanJob).join(ScanJob, isouter=True).filter(ScanResult.asset_id == asset_id)
    if search:
        # Проверка наличия полей перед фильтрацией
        filters = []
        if hasattr(ScanJob, 'scan_type'):
            filters.append(ScanJob.scan_type.like(f'%{search}%'))
        if hasattr(ScanJob, 'status'):
            filters.append(ScanJob.status.like(f'%{search}%'))
        if filters:
            query = query.filter(or_(*filters))
            
    results = query.order_by(ScanResult.scanned_at.desc()).limit(100).all()
    
    data = []
    for res, job in results:
        ports = []
        if res.ports:
            try: ports = json.loads(res.ports)
            except: ports = res.ports.split(',') if isinstance(res.ports, str) else []
            
        data.append({
            'id': res.id, 
            'scan_type': job.scan_type if job else 'unknown', 
            'status': job.status if job else 'completed',
            'scanned_at': format_moscow_time(res.scanned_at),
            'ports': ports, 
            'os': res.os_detection if hasattr(res, 'os_detection') else '-'
        })
    return jsonify(data)

# ────────────────────────────────────────────────────────────────
# ОПЕРАЦИИ С АКТИВАМИ (BULK, UPDATE, DELETE)
# ────────────────────────────────────────────────────────────────

@main_bp.route('/api/assets/bulk-delete', methods=['POST'])
def bulk_delete_assets():
    data = request.json
    asset_ids = data.get('ids', [])
    if not asset_ids:
        return jsonify({'error': 'No IDs provided'}), 400
    deleted_count = Asset.query.filter(Asset.id.in_(asset_ids)).delete(synchronize_session=False)
    db.session.commit()
    return jsonify({'success': True, 'deleted': deleted_count})

@main_bp.route('/api/assets/bulk-move', methods=['POST'])
def bulk_move_assets():
    data = request.json
    asset_ids = data.get('ids', [])
    group_id = data.get('group_id')
    
    if group_id == '':
        group_id = None
    elif group_id:
        group_id = int(group_id)
        
    if not asset_ids:
        return jsonify({'error': 'No IDs provided'}), 400
        
    moved_count = Asset.query.filter(Asset.id.in_(asset_ids)).update({'group_id': group_id}, synchronize_session=False)
    db.session.commit()
    return jsonify({'success': True, 'moved': moved_count})

@main_bp.route('/asset/<int:id>/delete')
def delete_asset(id):
    asset = Asset.query.get_or_404(id)
    group_id = asset.group_id
    db.session.delete(asset)
    db.session.commit()
    flash(f'Актив {asset.ip_address} удалён', 'warning')
    if group_id:
        return redirect(url_for('main.index', group_id=group_id))
    else:
        return redirect(url_for('main.index', ungrouped='true'))
    
@main_bp.route('/asset/<int:id>/update-notes', methods=['POST'])
def update_asset_notes(id):
    asset = Asset.query.get_or_404(id)
    notes = request.form.get('notes', '')
    asset.notes = notes
    db.session.commit()
    flash('Заметки обновлены', 'success')
    return redirect(url_for('main.asset_detail', id=id))

@main_bp.route('/asset/<int:id>/update-group', methods=['POST'])
def update_asset_group(id):
    asset = Asset.query.get_or_404(id)
    group_id = request.form.get('group_id')
    asset.group_id = int(group_id) if group_id and group_id.strip() else None
    db.session.commit()
    flash('Группа обновлена', 'success')
    return redirect(url_for('main.asset_detail', id=id))

# ────────────────────────────────────────────────────────────────
# СКАНИРОВАНИЕ И ИМПОРТ
# ────────────────────────────────────────────────────────────────

@main_bp.route('/scan', methods=['POST'])
def import_scan():
    if 'file' not in request.files:
        flash('Файл не найден', 'danger')
        return redirect(url_for('main.index'))
    
    file = request.files['file']
    group_id = request.form.get('group_id')
    if group_id == '': group_id = None
    
    if file and file.filename:
        filename = secure_filename(file.filename)
        # Путь к папке загрузок
        upload_folder = current_app.config.get('UPLOAD_FOLDER', 'uploads')
        if not os.path.exists(upload_folder):
            os.makedirs(upload_folder)
        filepath = os.path.join(upload_folder, filename)
        file.save(filepath)
        
        try:
            parsed_assets = parse_nmap_xml(filepath)
            updated_count = 0
            created_count = 0
            
            for data in parsed_assets:
                existing = Asset.query.filter_by(ip_address=data['ip_address']).first()
                if existing:
                    existing.hostname = data.get('hostname')
                    existing.os_info = data.get('os_info')
                    existing.open_ports = data.get('open_ports')
                    if hasattr(existing, 'last_scanned'):
                        existing.last_scanned = datetime.now(MOSCOW_TZ)
                    if hasattr(existing, 'status'):
                        existing.status = data.get('status')
                    if group_id and not existing.group_id:
                        existing.group_id = group_id
                    updated_count += 1
                else:
                    new_asset = Asset(
                        ip_address=data['ip_address'],
                        hostname=data.get('hostname'),
                        os_info=data.get('os_info'),
                        open_ports=data.get('open_ports'),
                        status=data.get('status', 'up'),
                        group_id=group_id
                    )
                    db.session.add(new_asset)
                    created_count += 1
            
            db.session.commit()
            flash(f'Успех! Создано: {created_count}, Обновлено: {updated_count}', 'success')
        except Exception as e:
            flash(f'Ошибка парсинга: {str(e)}', 'danger')
            print(f"❌ Ошибка импорта: {e}")
        finally:
            if os.path.exists(filepath):
                os.remove(filepath)
    
    return redirect(url_for('main.index'))

@main_bp.route('/asset/<int:id>/scan-nmap', methods=['POST'])
def scan_asset_nmap(id):
    asset = Asset.query.get_or_404(id)
    scan_job = ScanJob(scan_type='nmap', target=asset.ip_address, status='pending')
    db.session.add(scan_job)
    db.session.commit()
    
    # Запуск в фоне
    thread = threading.Thread(target=run_nmap_scan, args=(scan_job.id, asset.ip_address, None, ''))
    thread.daemon = True
    thread.start()
    
    flash(f'Nmap сканирование запущено для {asset.ip_address}', 'info')
    return redirect(url_for('main.asset_detail', id=id))

# ────────────────────────────────────────────────────────────────
# РЕГИСТРАЦИЯ BLUEPRINTS
# ────────────────────────────────────────────────────────────────

def register_blueprints(app):
    app.register_blueprint(main_bp)
    app.register_blueprint(groups_bp)
```

### 📄 `routes/osquery.py`

```python
from flask import Blueprint, render_template, request, jsonify, redirect, url_for
from extensions import db
from models import Asset, OsqueryInventory
from utils.osquery_validator import validate_osquery_config
import os, json
from datetime import datetime

osquery_bp = Blueprint('osquery', __name__)
CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'configs', 'osquery', 'osquery.conf')

@osquery_bp.route('/osquery')
def dashboard(): return render_template('osquery_dashboard.html', assets=Asset.query.filter(Asset.osquery_node_key.isnot(None)).all())

@osquery_bp.route('/osquery/api/register', methods=['POST'])
def register_node():
    data = request.json; ip = request.remote_addr; node_key = data.get('node_key')
    asset = Asset.query.filter_by(ip_address=ip).first()
    if not asset: asset = Asset(ip_address=ip, status='up'); db.session.add(asset); db.session.flush()
    asset.osquery_node_key = node_key; asset.osquery_status = 'pending'; db.session.commit()
    return jsonify({'status': 'registered'}), 200

@osquery_bp.route('/osquery/api/ingest', methods=['POST'])
def ingest_inventory():
    data = request.json; asset = Asset.query.filter_by(osquery_node_key=data.get('node_key')).first()
    if not asset: return jsonify({'error': 'Node key not found'}), 404
    asset.osquery_version = data.get('osquery_version', 'unknown'); asset.osquery_status = 'online'; asset.osquery_last_seen = datetime.utcnow()
    asset.osquery_cpu = data.get('cpu_model'); asset.osquery_ram = f"{int(data.get('memory_total', 0) / (1024**3))} GB" if data.get('memory_total') else None
    asset.osquery_disk = f"{int(data.get('disk_total', 0) / (1024**3))} GB" if data.get('disk_total') else None
    asset.osquery_os = data.get('os_name'); asset.osquery_kernel = data.get('kernel_version'); asset.osquery_uptime = data.get('uptime_seconds')
    db.session.add(OSqueryInventory(asset_id=asset.id, cpu_model=data.get('cpu_model'), memory_total=data.get('memory_total'), disk_total=data.get('disk_total'), os_name=data.get('os_name'), kernel_version=data.get('kernel_version'), uptime_seconds=data.get('uptime_seconds')))
    db.session.commit()
    return jsonify({'status': 'ok'}), 200

@osquery_bp.route('/osquery/deploy')
def deploy_page(): return render_template('osquery_deploy.html')

@osquery_bp.route('/osquery/instructions')
def instructions_page(): return render_template('osquery_instructions.html')

@osquery_bp.route('/osquery/config-editor')
def config_editor(): return render_template('osquery_config_editor.html')

@osquery_bp.route('/osquery/api/config', methods=['GET'])
def get_config():
    try:
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f: return jsonify(json.load(f))
    except Exception as e: return jsonify({'error': str(e)}), 500

@osquery_bp.route('/osquery/api/config/validate', methods=['POST'])
def validate_config():
    data = request.json
    if not data: return jsonify({'valid': False, 'errors': ['Пустой запрос']}), 400
    try:
        config = json.loads(json.dumps(data))
        errors, warnings = validate_osquery_config(config)
        return jsonify({'valid': len(errors) == 0, 'errors': errors, 'warnings': warnings})
    except json.JSONDecodeError as e: return jsonify({'valid': False, 'errors': [f"JSON ошибка: {str(e)}"]}), 400
    except Exception as e: return jsonify({'valid': False, 'errors': [f"Внутренняя ошибка: {str(e)}"]}), 500

@osquery_bp.route('/osquery/api/config', methods=['POST'])
def save_config():
    try:
        config = request.json
        errors, _ = validate_osquery_config(config)
        if errors: return jsonify({'error': 'Конфигурация содержит ошибки', 'errors': errors}), 400
        os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
        with open(CONFIG_PATH, 'w', encoding='utf-8') as f: json.dump(config, f, indent=2, ensure_ascii=False)
        return jsonify({'success': True})
    except Exception as e: return jsonify({'error': str(e)}), 500

```

### 📄 `routes/scans.py`

```python
from flask import Blueprint, request, jsonify, render_template, current_app
from models import db, Asset, Group, ScanJob, ScanResult
from utils import create_asset_if_not_exists, update_asset_dns_names
import json
import os
import threading
import traceback
from datetime import datetime
from scanner import run_rustscan_scan, run_nmap_scan, run_nslookup_scan

scans_bp = Blueprint('scans', __name__)

# ────────────────────────────────────────────────────────────────
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ────────────────────────────────────────────────────────────────

def run_scan_wrapper(app, func, job_id, *args):
    """
    Обертка для безопасного запуска сканирования в потоке.
    app: объект приложения Flask
    func: функция сканирования (например, run_rustscan_scan)
    job_id: ID задачи
    *args: остальные аргументы для функции сканирования
    """
    try:
        with app.app_context():
            # ИСПРАВЛЕНИЕ: Передаем app первым аргументом, так как функции в scanner.py ожидают его там
            func(app, job_id, *args)
    except Exception as e:
        print(f"❌ Ошибка в потоке сканирования {job_id}: {e}")
        traceback.print_exc()
        
        try:
            with app.app_context():
                job = ScanJob.query.get(job_id)
                if job:
                    job.status = 'failed'
                    job.error_message = f"Exception in thread: {str(e)}\n{traceback.format_exc()}"
                    job.progress = 0
                    job.completed_at = datetime.utcnow()
                    db.session.commit()
        except Exception as db_err:
            print(f"❌ Ошибка обновления статуса задачи в БД: {db_err}")

# ────────────────────────────────────────────────────────────────
# СТРАНИЦЫ
# ────────────────────────────────────────────────────────────────

@scans_bp.route('/scans')
def scans_page():
    """Страница управления сканированиями"""
    jobs = ScanJob.query.order_by(ScanJob.created_at.desc()).limit(50).all()
    profiles = [] 
    all_groups = Group.query.all()
    return render_template('scans.html', scan_jobs=jobs, profiles=profiles, all_groups=all_groups)

# ────────────────────────────────────────────────────────────────
# API СКАНИРОВАНИЙ
# ────────────────────────────────────────────────────────────────

@scans_bp.route('/api/scans/status')
def get_active_scans_status():
    active_jobs = ScanJob.query.filter(
        ScanJob.status.in_(['pending', 'running', 'paused'])
    ).order_by(ScanJob.created_at.desc()).all()
    
    jobs_data = []
    for j in active_jobs:
        jobs_data.append({
            'id': j.id,
            'scan_type': j.scan_type,
            'target': j.target,
            'status': j.status,
            'progress': j.progress,
            'current_target': j.current_target,
            'created_at': j.created_at.strftime('%Y-%m-%d %H:%M:%S') if j.created_at else None
        })
    return jsonify({'active': jobs_data})

@scans_bp.route('/api/scans/history')
def get_scan_history():
    jobs = ScanJob.query.order_by(ScanJob.created_at.desc()).limit(50).all()
    history = []
    for j in jobs:
        history.append({
            'id': j.id,
            'scan_type': j.scan_type,
            'target': j.target,
            'status': j.status,
            'progress': j.progress,
            'error_message': j.error_message,
            'started_at': j.started_at.strftime('%Y-%m-%d %H:%M:%S') if j.started_at else None,
            'completed_at': j.completed_at.strftime('%Y-%m-%d %H:%M:%S') if j.completed_at else None
        })
    return jsonify(history)

@scans_bp.route('/api/scans/rustscan', methods=['POST'])
def start_rustscan():
    data = request.json
    target = data.get('target')
    ports = data.get('ports', '-')
    args = data.get('extra_args', '')
    
    if not target:
        return jsonify({'error': 'Не указана цель'}), 400
        
    job = ScanJob(
        scan_type='rustscan',
        target=target,
        status='pending',
        progress=0,
        scan_parameters=json.dumps({'ports': ports, 'args': args})
    )
    db.session.add(job)
    db.session.commit()
    
    # Получаем текущее приложение и передаем в поток
    app = current_app._get_current_object()
    t = threading.Thread(
        target=run_scan_wrapper, 
        args=(app, run_rustscan_scan, job.id, target, ports, args)
    )
    t.daemon = True
    t.start()
    
    return jsonify({'job_id': job.id, 'status': 'started', 'message': 'Сканирование запущено'})

@scans_bp.route('/api/scans/nmap', methods=['POST'])
def start_nmap():
    data = request.json
    target = data.get('target')
    ports = data.get('ports', '-')
    scripts = data.get('scripts', '')
    args = data.get('extra_args', '')
    
    if not target:
        return jsonify({'error': 'Не указана цель'}), 400
        
    job = ScanJob(
        scan_type='nmap',
        target=target,
        status='pending',
        progress=0,
        scan_parameters=json.dumps({'ports': ports, 'scripts': scripts, 'args': args})
    )
    db.session.add(job)
    db.session.commit()
    
    app = current_app._get_current_object()
    t = threading.Thread(
        target=run_scan_wrapper, 
        args=(app, run_nmap_scan, job.id, target, ports, scripts, args)
    )
    t.daemon = True
    t.start()
    
    return jsonify({'job_id': job.id, 'status': 'started', 'message': 'Сканирование запущено'})

@scans_bp.route('/api/scans/nslookup', methods=['POST'])
def start_nslookup():
    data = request.json
    targets = data.get('targets', '') 
    dns_server = data.get('dns_server', '77.88.8.8')
    args = data.get('nslookup_args', '')
    
    if not targets or not targets.strip():
        return jsonify({'error': 'Не указаны домены'}), 400
        
    params = {
        'targets': targets,
        'dns_server': dns_server,
        'args': args
    }
    
    job = ScanJob(
        scan_type='nslookup',
        target=f"NSLookup ({len(targets.splitlines())} domains)",
        status='pending',
        progress=0,
        scan_parameters=json.dumps(params)
    )
    db.session.add(job)
    db.session.commit()
    
    app = current_app._get_current_object()
    t = threading.Thread(
        target=run_scan_wrapper, 
        args=(app, run_nslookup_scan, job.id, targets, dns_server, args)
    )
    t.daemon = True
    t.start()
    
    return jsonify({'job_id': job.id, 'status': 'started', 'message': 'Сканирование запущено'})

@scans_bp.route('/api/scans/<int:job_id>/results')
def get_scan_results(job_id):
    job = ScanJob.query.get_or_404(job_id)
    results = []
    
    if job.scan_type == 'nslookup' and job.nslookup_output:
        lines = job.nslookup_output.split('\n')
        current_ip = None
        current_domain = None
        for line in lines:
            line = line.strip()
            if line.startswith('Name:'):
                current_domain = line.split(':', 1)[1].strip()
            elif line.startswith('Address:') and '#' not in line:
                 current_ip = line.split(':', 1)[1].strip()
                 if current_domain and current_ip:
                     results.append({'domain': current_domain, 'ip': current_ip})
                     try:
                         asset = create_asset_if_not_exists(current_ip, hostname=current_domain)
                         update_asset_dns_names(asset, current_domain)
                     except Exception as e:
                         print(f"Error creating asset: {e}")
                     current_domain = None
    
    return jsonify({
        'job': {
            'id': job.id,
            'scan_type': job.scan_type,
            'target': job.target,
            'status': job.status,
            'progress': job.progress,
            'error_message': job.error_message,
            'started_at': job.started_at.strftime('%Y-%m-%d %H:%M:%S') if job.started_at else None,
            'completed_at': job.completed_at.strftime('%Y-%m-%d %H:%M:%S') if job.completed_at else None,
            'nslookup_output': job.nslookup_output if job.scan_type == 'nslookup' else None
        },
        'results': results
    })

@scans_bp.route('/api/scans/<int:job_id>', methods=['DELETE'])
def delete_scan_job(job_id):
    job = ScanJob.query.get_or_404(job_id)
    if job.status == 'running':
        job.status = 'failed'
        job.error_message = 'Удалено пользователем во время выполнения'
        job.completed_at = datetime.utcnow()
        db.session.commit()
    
    db.session.delete(job)
    db.session.commit()
    return jsonify({'success': True, 'message': 'Задача удалена'})

@scans_bp.route('/api/scans/<int:job_id>/control', methods=['POST'])
def control_scan(job_id):
    job = ScanJob.query.get_or_404(job_id)
    data = request.json
    action = data.get('action')
    
    if action == 'delete':
        db.session.delete(job)
        db.session.commit()
        return jsonify({'success': True})
        
    elif action == 'stop':
        if job.status == 'running':
            job.status = 'failed'
            job.error_message = 'Остановлено пользователем'
            job.completed_at = datetime.utcnow()
            db.session.commit()
            return jsonify({'success': True})
            
    elif action == 'pause':
        if job.status == 'running':
            job.status = 'paused'
            db.session.commit()
            return jsonify({'success': True})
            
    elif action == 'resume':
        if job.status == 'paused':
            job.status = 'running'
            db.session.commit()
            return jsonify({'success': True})
            
    elif action == 'rerun':
        if not job.scan_parameters:
            return jsonify({'error': 'Нет параметров для повтора'}), 400
            
        params = json.loads(job.scan_parameters)
        new_job = ScanJob(
            scan_type=job.scan_type,
            target=job.target,
            status='pending',
            progress=0,
            scan_parameters=job.scan_parameters
        )
        db.session.add(new_job)
        db.session.commit()
        
        app = current_app._get_current_object()
        
        if job.scan_type == 'rustscan':
            t = threading.Thread(target=run_scan_wrapper, args=(app, run_rustscan_scan, new_job.id, job.target, params.get('ports', '-'), params.get('args', '')))
        elif job.scan_type == 'nmap':
            t = threading.Thread(target=run_scan_wrapper, args=(app, run_nmap_scan, new_job.id, job.target, params.get('ports', '-'), params.get('scripts', ''), params.get('args', '')))
        elif job.scan_type == 'nslookup':
            t = threading.Thread(target=run_scan_wrapper, args=(app, run_nslookup_scan, new_job.id, params.get('targets', ''), params.get('dns_server', '77.88.8.8'), params.get('args', '')))
        else:
            return jsonify({'error': 'Неизвестный тип'}), 400
            
        t.daemon = True
        t.start()
        return jsonify({'success': True, 'new_id': new_job.id})
    
    return jsonify({'error': 'Недопустимое действие'}), 400
```

### 📄 `routes/utilities.py`

```python
from flask import Blueprint, request, jsonify, Response
from datetime import datetime
import xml.etree.ElementTree as ET

utilities_bp = Blueprint('utilities', __name__)

@utilities_bp.route('/utilities')
def utilities_page():
    from models import Group; from utils import build_group_tree
    all_groups = Group.query.all()
    return render_template('utilities.html', group_tree=build_group_tree(all_groups), all_groups=all_groups)

@utilities_bp.route('/utilities/nmap-to-rustscan', methods=['POST'])
def nmap_to_rustscan():
    if 'file' not in request.files: return jsonify({'error': 'Файл не найден'}), 400
    file = request.files['file']
    if file.filename == '': return jsonify({'error': 'Файл не выбран'}), 400
    if not file.filename.endswith('.xml'): return jsonify({'error': 'Требуется XML файл'}), 400
    try:
        tree = ET.parse(file.stream); root = tree.getroot()
        ips = [addr.get('addr') for host in root.findall('host') if (status := host.find('status')) is not None and status.get('state') == 'up' and (addr := host.find('address')) is not None and addr.get('addr')]
        if not ips: return jsonify({'error': 'Не найдено активных хостов'}), 400
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        return Response('\n'.join(ips), mimetype='text/plain', headers={'Content-Disposition': f'attachment; filename=rustscan_targets_{timestamp}.txt'})
    except Exception as e: return jsonify({'error': f'Ошибка: {str(e)}'}), 500

@utilities_bp.route('/utilities/extract-ports', methods=['POST'])
def extract_ports():
    if 'file' not in request.files: return jsonify({'error': 'Файл не найден'}), 400
    file = request.files['file']
    if file.filename == '': return jsonify({'error': 'Файл не выбран'}), 400
    try:
        tree = ET.parse(file.stream); root = tree.getroot()
        all_ports, host_ports = set(), {}
        for host in root.findall('host'):
            status = host.find('status')
            if status is not None and status.get('state') == 'up':
                addr = host.find('address'); ip = addr.get('addr') if addr is not None else 'unknown'
                ports = []; ports_elem = host.find('ports')
                if ports_elem is not None:
                    for port in ports_elem.findall('port'):
                        state = port.find('state')
                        if state is not None and state.get('state') == 'open':
                            port_id, protocol = port.get('portid'), port.get('protocol')
                            service = port.find('service'); service_name = service.get('name') if service is not None else ''
                            port_str = f"{port_id}/{protocol}" + (f" ({service_name})" if service_name else '')
                            ports.append(port_str); all_ports.add(port_id)
                if ports: host_ports[ip] = ports
        content = "="*60 + "\nNMAP PORTS EXTRACTION REPORT\n" + f"Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}\n" + "="*60 + "\n\n"
        content += f"Total hosts: {len(host_ports)}\nUnique ports: {len(all_ports)}\n\n"
        content += "-"*60 + "\nUNIQUE PORTS (for rustscan -p):\n" + "-"*60 + "\n" + ','.join(sorted(all_ports, key=int)) + "\n\n"
        content += "-"*60 + "\nHOSTS WITH PORTS:\n" + "-"*60 + "\n"
        for ip, ports in host_ports.items(): content += f"\n{ip}:\n" + "".join(f"  - {p}\n" for p in ports)
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        return Response(content, mimetype='text/plain', headers={'Content-Disposition': f'attachment; filename=nmap_ports_report_{timestamp}.txt'})
    except Exception as e: return jsonify({'error': f'Ошибка: {str(e)}'}), 500

```

### 📄 `routes/wazuh.py`

```python
from flask import Blueprint, request, jsonify
from extensions import db
from models import Asset, WazuhConfig
from utils.wazuh_api import WazuhAPI
from datetime import datetime

wazuh_bp = Blueprint('wazuh', __name__)

@wazuh_bp.route('/api/wazuh/config', methods=['GET'])
def get_wazuh_config():
    cfg = WazuhConfig.query.first() or WazuhConfig()
    if not cfg.id: db.session.add(cfg); db.session.commit()
    return jsonify({'url': cfg.url, 'username': cfg.username, 'password': cfg.password, 'verify_ssl': cfg.verify_ssl, 'is_active': cfg.is_active})

@wazuh_bp.route('/api/wazuh/config', methods=['POST'])
def save_wazuh_config():
    data = request.json; cfg = WazuhConfig.query.first() or WazuhConfig()
    cfg.url = data.get('url', cfg.url); cfg.username = data.get('username', cfg.username)
    cfg.password = data.get('password', cfg.password); cfg.verify_ssl = data.get('verify_ssl', False); cfg.is_active = data.get('is_active', False)
    db.session.add(cfg); db.session.commit()
    return jsonify({'success': True})

@wazuh_bp.route('/api/wazuh/sync', methods=['POST'])
def sync_wazuh():
    cfg = WazuhConfig.query.first()
    if not cfg or not cfg.is_active: return jsonify({'error': 'Wazuh интеграция отключена'}), 400
    try:
        api = WazuhAPI(cfg.url, cfg.username, cfg.password, cfg.verify_ssl)
        agents = api.fetch_all_agents(); synced, updated = 0, 0
        for agent in agents:
            ip = agent.get('ip') or agent.get('registerIP')
            if not ip: continue
            asset = Asset.query.filter_by(wazuh_agent_id=agent['id']).first()
            if not asset: asset = Asset.query.filter_by(ip_address=ip).first()
            if not asset: asset = Asset(ip_address=ip, data_source='wazuh'); db.session.add(asset); db.session.flush(); synced += 1
            else: updated += 1
            asset.wazuh_agent_id = agent['id']; asset.hostname = agent.get('name') or asset.hostname
            os_data = agent.get('os', {})
            if os_data: asset.os_info = f"{os_data.get('name','')} {os_data.get('version','')}".strip() or asset.os_info
            asset.status = 'up' if agent.get('status') == 'active' else 'down'
            if agent.get('lastKeepAlive'):
                try: asset.last_scanned = datetime.fromisoformat(agent['lastKeepAlive'].replace('Z','+00:00'))
                except: pass
            asset.data_source = 'wazuh'
        db.session.commit()
        return jsonify({'success': True, 'new': synced, 'updated': updated, 'total': len(agents)})
    except Exception as e: db.session.rollback(); return jsonify({'error': str(e)}), 500

```

### 📄 `static/js/main.js`

```javascript
// static/js/main.js
import { initTheme, toggleTheme } from './modules/theme.js';
import { populateParentSelect, closeModalById } from './modules/utils.js';
import {
    showCreateGroupModal, toggleGroupMode, addDynamicRule, showRenameModal,
    saveGroup, showDeleteModal, confirmDeleteGroup, showMoveGroupModal, moveGroup, initContextMenu
} from './modules/groups.js';
import {
    initAssetSelection, confirmBulkDelete, executeBulkDelete,
    initFilterFieldDatalist, renderAssets
} from './modules/assets.js';
import { viewScanResults, showScanError, updateScanHistory, pollActiveScans } from './modules/scans.js';
import { initWazuhFilter, saveWazuhConfig, testWazuhConnection } from './modules/wazuh.js';
// ✅ Импорт всей логики дерева из одного источника
import { refreshGroupTree, loadAssets, filterByGroup, initTreeTogglers } from './modules/tree.js';

(function() {
    if (window.__MAIN_JS_LOADED) return;
    window.__MAIN_JS_LOADED = true;

    window.currentGroupId = null;
    window.contextMenu = null;
    window.editModal = null; window.createModal = null;
    window.moveModal = null; window.deleteModal = null;
    window.bulkDeleteModalInstance = null;
    window.lastSelectedIndex = -1;
    window.selectedAssetIds = new Set();

    document.addEventListener('DOMContentLoaded', () => {
        initTheme();
        initFilterFieldDatalist();
        initAssetSelection();
        initWazuhFilter();
        initContextMenu();
        
        window.contextMenu = document.getElementById('group-context-menu');
        setInterval(pollActiveScans, 5000);
        pollActiveScans();

        // ✅ Инициализируем дерево строго один раз после готовности DOM
        refreshGroupTree().then(() => initTreeTogglers());

        document.addEventListener('keydown', e => {
            if(e.ctrlKey && e.key==='a' && !['INPUT','TEXTAREA','SELECT'].includes(e.target.tagName)) {
                e.preventDefault();
                document.querySelectorAll('#assets-body .asset-checkbox').forEach(cb => {
                    cb.checked=true;
                    const row = cb.closest('tr');
                    if(row) row.classList.add('selected');
                    window.selectedAssetIds.add(cb.value);
                });
                const tb = document.getElementById('bulk-toolbar');
                if(tb) {
                    tb.style.display = window.selectedAssetIds.size > 0 ? 'flex' : 'none';
                    const countEl = document.getElementById('selected-count');
                    if(countEl) countEl.textContent = window.selectedAssetIds.size;
                }
            }
        });

        // Глобальные экспорты для onclick в HTML
        window.toggleTheme = toggleTheme;
        window.showCreateGroupModal = showCreateGroupModal;
        window.toggleGroupMode = toggleGroupMode;
        window.addDynamicRule = addDynamicRule;
        window.showRenameModal = showRenameModal;
        window.saveGroup = saveGroup;
        window.showDeleteModal = showDeleteModal;
        window.confirmDeleteGroup = confirmDeleteGroup;
        window.showMoveGroupModal = showMoveGroupModal;
        window.moveGroup = moveGroup;
        window.confirmBulkDelete = confirmBulkDelete;
        window.executeBulkDelete = executeBulkDelete;
        window.refreshGroupTree = refreshGroupTree;
        window.loadAssets = loadAssets;
        window.filterByGroup = filterByGroup;
        window.saveWazuhConfig = saveWazuhConfig;
        window.testWazuhConnection = testWazuhConnection;
    });
})();
```

### 📄 `static/js/modules/assets.js`

```javascript
// static/js/modules/assets.js

export function initAssetSelection() {
    const tbody = document.getElementById('assets-body'); 
    if (!tbody) return;
    
    const selAll = document.getElementById('select-all');
    if(selAll) selAll.addEventListener('change', function() {
        document.querySelectorAll('.asset-checkbox').forEach(cb => {
            cb.checked = this.checked; 
            toggleRowSelection(cb.closest('tr'), this.checked);
            if(this.checked) window.selectedAssetIds.add(cb.value); 
            else window.selectedAssetIds.delete(cb.value);
        });
        window.lastSelectedIndex = this.checked ? getRowIndex(document.querySelectorAll('.asset-checkbox').pop().closest('tr')) : -1;
        updateBulkToolbar(); 
        updateSelectAllCheckbox();
    });
    
    tbody.addEventListener('change', e => { 
        if(e.target.classList.contains('asset-checkbox')) handleCheckboxChange(e.target); 
    });
    
    tbody.addEventListener('click', e => {
        const row = e.target.closest('.asset-row'); 
        if(!row || e.target.closest('a, button, .asset-checkbox')) return;
        const cb = row.querySelector('.asset-checkbox');
        if(cb) { 
            if(e.shiftKey && window.lastSelectedIndex >= 0) { 
                e.preventDefault(); 
                selectRange(window.lastSelectedIndex, getRowIndex(row)); 
            } else { 
                cb.checked = !cb.checked; 
                handleCheckboxChange(cb); 
            } 
        }
    });
}

function handleCheckboxChange(cb) {
    const row = cb.closest('tr'); 
    const id = cb.value; 
    const checked = cb.checked;
    toggleRowSelection(row, checked);
    if(checked) { 
        window.selectedAssetIds.add(id); 
        window.lastSelectedIndex = getRowIndex(row); 
    } else { 
        window.selectedAssetIds.delete(id); 
        if(window.lastSelectedIndex === getRowIndex(row)) window.lastSelectedIndex = -1; 
    }
    updateBulkToolbar(); 
    updateSelectAllCheckbox();
}

function toggleRowSelection(row, isSel) { 
    if(isSel) row.classList.add('selected'); 
    else row.classList.remove('selected'); 
}

function getRowIndex(row) { 
    return Array.from(document.querySelectorAll('#assets-body .asset-row')).indexOf(row); 
}

function selectRange(start, end) {
    const [s, e] = start <= end ? [start, end] : [end, start];
    document.querySelectorAll('#assets-body .asset-row').forEach((row, i) => {
        if(i >= s && i <= e) {
            const cb = row.querySelector('.asset-checkbox');
            if(cb && !cb.checked) { 
                cb.checked = true; 
                toggleRowSelection(row, true); 
                window.selectedAssetIds.add(cb.value); 
            }
        }
    }); 
    updateBulkToolbar(); 
    updateSelectAllCheckbox();
}

function clearSelection() {
    document.querySelectorAll('#assets-body .asset-checkbox:checked').forEach(cb => { 
        cb.checked = false; 
        toggleRowSelection(cb.closest('tr'), false); 
        window.selectedAssetIds.delete(cb.value); 
    });
    window.lastSelectedIndex = -1; 
    updateBulkToolbar(); 
    updateSelectAllCheckbox();
}

function updateSelectAllCheckbox() {
    const selAll = document.getElementById('select-all'); 
    const cbs = document.querySelectorAll('#assets-body .asset-checkbox');
    const checked = document.querySelectorAll('#assets-body .asset-checkbox:checked').length;
    if(selAll && cbs.length > 0) { 
        selAll.checked = checked === cbs.length; 
        selAll.indeterminate = checked > 0 && checked < cbs.length; 
    }
}

function updateBulkToolbar() {
    const tb = document.getElementById('bulk-toolbar'); 
    const c = window.selectedAssetIds.size;
    if(tb) {
        tb.style.display = c > 0 ? 'flex' : 'none'; 
        const countEl = document.getElementById('selected-count');
        if(countEl) countEl.textContent = c;
    }
}

export function confirmBulkDelete() {
    if(window.selectedAssetIds.size === 0) return;
    const countEl = document.getElementById('bulk-delete-count');
    if(countEl) countEl.textContent = window.selectedAssetIds.size;
    const modalInstance = bootstrap.Modal.getInstance(document.getElementById('bulkDeleteModal'));
    if(modalInstance) modalInstance.show();
}

export async function executeBulkDelete() {
    const ids = Array.from(window.selectedAssetIds);
    await fetch('/api/assets/bulk-delete', { 
        method: 'POST', 
        headers: {'Content-Type': 'application/json'}, 
        body: JSON.stringify({ids}) 
    });
    clearSelection(); 
    
    const modalEl = document.getElementById('bulkDeleteModal');
    const modalInstance = bootstrap.Modal.getInstance(modalEl);
    if (modalInstance) {
        modalInstance.hide();
    }
    
    location.reload();
}

const FILTER_FIELDS = [
    { value: 'ip_address', text: 'IP Адрес' }, { value: 'hostname', text: 'Hostname' },
    { value: 'os_info', text: 'ОС (Сканирование)' }, { value: 'device_role', text: 'Роль устройства' },
    { value: 'open_ports', text: 'Открытые порты' }, { value: 'status', text: 'Статус' },
    { value: 'notes', text: 'Заметки' }, { value: 'osquery_status', text: 'Статус OSquery' },
    { value: 'osquery_os', text: 'ОС (OSquery)' }, { value: 'scanners_used', text: 'Сканеры (JSON)' }
];

export function initFilterFieldDatalist() {
    if(!document.getElementById('filter-fields-list')) {
        const dl = document.createElement('datalist'); 
        dl.id = 'filter-fields-list';
        dl.innerHTML = FILTER_FIELDS.map(f => `<option value="${f.value}">${f.text}</option>`).join('');
        document.body.appendChild(dl);
    }
}

export function renderAssets(data) {
    const tb = document.getElementById('assets-body'); 
    if(!tb) return;
    tb.innerHTML = ''; 
    clearSelection();
    if(data.length===0) { 
        tb.innerHTML='<tr><td colspan="7" class="text-center py-4 text-muted"><i class="bi bi-inbox fs-1 d-block mb-2"></i>Ничего не найдено</td></tr>'; 
        return; 
    }
    data.forEach(a => {
        const tr = document.createElement('tr'); 
        tr.className='asset-row'; 
        tr.dataset.assetId=a.id;
        tr.innerHTML=`<td><input type="checkbox" class="form-check-input asset-checkbox" value="${a.id}"></td>
            <td><a href="/asset/${a.id}"><strong>${a.ip}</strong></a></td><td>${a.hostname||'—'}</td>
            <td><span class="text-muted small">${a.os||'—'}</span></td><td><small class="text-muted">${a.ports||'—'}</small></td>
            <td><span class="badge bg-light text-dark border">${a.group}</span></td>
            <td><a href="/asset/${a.id}" class="btn btn-sm btn-outline-info"><i class="bi bi-eye"></i></a></td>`;
        tb.appendChild(tr);
    });
}

// Экспорт для доступа из main.js
window.renderAssets = renderAssets;
```

### 📄 `static/js/modules/groups.js`

```javascript
// static/js/modules/groups.js

import { populateParentSelect, closeModalById } from './utils.js';

const FILTER_FIELDS = [
    { value: 'ip_address', text: 'IP Адрес' }, { value: 'hostname', text: 'Hostname' },
    { value: 'os_info', text: 'ОС (Сканирование)' }, { value: 'device_role', text: 'Роль устройства' },
    { value: 'open_ports', text: 'Открытые порты' }, { value: 'status', text: 'Статус' },
    { value: 'notes', text: 'Заметки' }, { value: 'osquery_status', text: 'Статус OSquery' },
    { value: 'osquery_os', text: 'ОС (OSquery)' }, { value: 'scanners_used', text: 'Сканеры (JSON)' }
];
const FILTER_OPS = [
    { value: 'eq', text: '=' }, { value: 'ne', text: '≠' }, { value: 'like', text: 'содержит' }, { value: 'in', text: 'в списке' }
];

export async function showCreateGroupModal(parentId = null) {
    const modalId = 'groupEditModal';
    const modalEl = document.getElementById(modalId);
    if (!modalEl) return console.error('Modal #' + modalId + ' not found');

    document.getElementById('groupEditForm').reset();
    document.getElementById('edit-group-id').value = '';
    document.getElementById('groupEditTitle').textContent = 'Новая группа';
    document.getElementById('edit-group-name').value = '';
    document.getElementById('group-filter-root').innerHTML = '';
    
    await populateParentSelect([], parentId);
    
    document.getElementById('modeManual').checked = true;
    toggleGroupMode(); 

    const modal = new bootstrap.Modal(modalEl, { backdrop: 'static' });
    modal.show();
}

export function toggleGroupMode() {
    const mode = document.querySelector('input[name="groupMode"]:checked')?.value;
    if(!mode) return;

    const secCommon = document.getElementById('sectionCommon');
    const secCidr = document.getElementById('sectionCidr');
    const secDynamic = document.getElementById('sectionDynamic');
    const nameInput = document.getElementById('edit-group-name');
    const parentSelect = document.getElementById('edit-group-parent');

    if(secCommon) secCommon.style.display = 'block';
    if(secCidr) secCidr.style.display = 'none';
    if(secDynamic) secDynamic.style.display = 'none';
    
    if (mode === 'manual') {
        if(nameInput) nameInput.required = true;
        if(parentSelect) parentSelect.disabled = false;
    } else if (mode === 'cidr') {
        if(secCidr) secCidr.style.display = 'block';
        if(nameInput) nameInput.required = false;
        if(parentSelect) parentSelect.disabled = false;
    } else if (mode === 'dynamic') {
        if(secDynamic) secDynamic.style.display = 'block';
        if(nameInput) nameInput.required = true;
        if(parentSelect) parentSelect.disabled = false;
        
        const root = document.getElementById('group-filter-root');
        if(root && root.children.length === 0) {
            addDynamicRule();
        }
    }
}

export function addDynamicRule(field = '', op = 'eq', value = '') {
    const container = document.getElementById('group-filter-root');
    if(!container) return;
    
    const div = document.createElement('div');
    div.className = 'filter-condition mb-2';
    div.innerHTML = `
        <div class="input-group input-group-sm">
            <select class="form-select rule-field">${FILTER_FIELDS.map(f => `<option value="${f.value}" ${f.value===field?'selected':''}>${f.text}</option>`).join('')}</select>
            <select class="form-select rule-op" style="max-width:100px">${FILTER_OPS.map(o => `<option value="${o.value}" ${o.value===op?'selected':''}>${o.text}</option>`).join('')}</select>
            <input type="text" class="form-control rule-val" value="${value}" placeholder="Значение">
            <button class="btn btn-outline-danger" type="button" onclick="this.parentElement.parentElement.remove()">×</button>
        </div>
    `;
    container.appendChild(div);
}

export async function showRenameModal(id) {
    const modalId = 'groupEditModal';
    const modalEl = document.getElementById(modalId);
    if (!modalEl) return console.warn('⚠️ #' + modalId + ' не найден');

    const idInput = document.getElementById('edit-group-id');
    if (idInput) idInput.value = id;
    document.getElementById('groupEditTitle').textContent = 'Редактировать группу';

    let groupData;
    try {
        const r = await fetch(`/api/groups/${id}`);
        groupData = await r.json();
    } catch (err) {
        console.error('Ошибка загрузки данных группы:', err);
        return;
    }

    await populateParentSelect([String(id)], groupData.parent_id);

    const nameInput = document.getElementById('edit-group-name');
    const parentSelect = document.getElementById('edit-group-parent');
    
    if (nameInput) nameInput.value = groupData.name || '';
    if (parentSelect) parentSelect.value = groupData.parent_id || '';

    const dynCheck = document.getElementById('modeDynamic');
    const manualCheck = document.getElementById('modeManual');
    
    if (groupData.is_dynamic || (groupData.filter_rules && groupData.filter_rules.length > 0)) {
        if(dynCheck) dynCheck.checked = true;
        if(manualCheck) manualCheck.checked = false;
    } else {
        if(manualCheck) manualCheck.checked = true;
        if(dynCheck) dynCheck.checked = false;
    }
    
    toggleGroupMode();

    if (groupData.is_dynamic && groupData.filter_rules) {
        const root = document.getElementById('group-filter-root');
        if(root) root.innerHTML = '';
        groupData.filter_rules.forEach(rule => {
            addDynamicRule(rule.field, rule.op, rule.value);
        });
    }

    const modal = new bootstrap.Modal(modalEl, { backdrop: 'static' });
    modal.show();
}

export async function saveGroup() {
    const id = document.getElementById('edit-group-id').value;
    const name = document.getElementById('edit-group-name').value.trim();
    const parentId = document.getElementById('edit-group-parent').value;
    const mode = document.querySelector('input[name="groupMode"]:checked')?.value;

    let payload = {
        name: name,
        parent_id: parentId === '' ? null : parseInt(parentId),
        mode: mode
    };

    if (mode === 'cidr') {
        const cidr = document.getElementById('edit-group-cidr').value.trim();
        if (!cidr) {
            alert('Укажите CIDR');
            return;
        }
        payload.cidr = cidr;
    } else if (mode === 'dynamic') {
        const rules = [];
        document.querySelectorAll('.filter-condition').forEach(el => {
            const field = el.querySelector('.rule-field').value;
            const op = el.querySelector('.rule-op').value;
            const value = el.querySelector('.rule-val').value.trim();
            if (field && value) rules.push({ field, op, value });
        });
        payload.filter_rules = rules;
    }

    const url = id ? `/api/groups/${id}` : '/api/groups';
    const method = id ? 'PUT' : 'POST';

    try {
        const res = await fetch(url, {
            method,
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(payload)
        });

        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.error || 'Ошибка сохранения');
        }

        closeModalById('groupEditModal');
        
        // Обновляем дерево и список активов
        if (typeof refreshGroupTree === 'function') {
            await refreshGroupTree();
        }
        if (typeof loadAssets === 'function') {
            await loadAssets();
        }
    } catch (e) {
        console.error('Ошибка сохранения группы:', e);
        alert(e.message);
    }
}

export async function showDeleteModal(id) {
    const modalId = 'groupDeleteModal';
    const modalEl = document.getElementById(modalId);
    if (!modalEl) return console.warn('❌ Модальное окно удаления не найдено');

    document.getElementById('delete-group-id').value = id;
    
    await populateParentSelect([String(id)]);
    
    const modal = new bootstrap.Modal(modalEl, { backdrop: 'static' });
    modal.show();
}

export function confirmDeleteGroup() {
    const groupId = document.getElementById('delete-group-id').value;
    const moveToId = document.getElementById('delete-move-assets').value;
    
    closeModalById('groupDeleteModal');

    fetch(`/api/groups/${groupId}`, {
        method: 'DELETE',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ move_to_id: moveToId || null })
    })
    .then(response => {
        if (response.ok) {
            if (typeof refreshGroupTree === 'function') {
                refreshGroupTree();
            }
            if (typeof loadAssets === 'function' && window.currentGroupId == groupId) {
                window.currentGroupId = null;
                loadAssets(); 
            }
        } else {
            alert('Ошибка при удалении группы');
        }
    })
    .catch(error => {
        console.error('Error:', error);
        alert('Ошибка сети');
    });
}

export async function showMoveGroupModal(id) {
    const modalId = 'groupMoveModal';
    const modalEl = document.getElementById(modalId);
    if (!modalEl) return console.warn('❌ Модальное окно перемещения не найдено');

    document.getElementById('move-group-id').value = id;
    
    await populateParentSelect([String(id)]);
    
    const modal = new bootstrap.Modal(modalEl, { backdrop: 'static' });
    modal.show();
}

export async function moveGroup() {
    const groupId = document.getElementById('move-group-id').value;
    const newParentId = document.getElementById('move-group-parent').value;

    try {
        const res = await fetch(`/api/groups/${groupId}/move`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ parent_id: newParentId === '' ? null : parseInt(newParentId) })
        });

        if (!res.ok) throw new Error('Не удалось переместить группу');

        closeModalById('groupMoveModal');
        
        if (typeof refreshGroupTree === 'function') {
            await refreshGroupTree();
        }
    } catch (e) {
        console.error('Ошибка перемещения группы:', e);
        alert(e.message);
    }
}

export function initContextMenu() {
    document.addEventListener('click', function(e) {
        const ctx = document.getElementById('group-context-menu');
        if (!ctx) return;
        ctx.style.display = 'none';
    });

    document.addEventListener('contextmenu', function(e) {
        const treeNode = e.target.closest('.tree-node');
        if (!treeNode) return;

        const ctx = document.getElementById('group-context-menu');
        if (!ctx) return;

        e.preventDefault();
        e.stopPropagation();

        const groupId = treeNode.dataset.id;
        const isUngrouped = groupId === 'ungrouped';

        ctx.style.display = 'block';
        ctx.style.left = e.pageX + 'px';
        ctx.style.top = e.pageY + 'px';

        const createItem = ctx.querySelector('[data-action="create-child"]');
        const renameItem = ctx.querySelector('[data-action="rename"]');
        const moveItem = ctx.querySelector('[data-action="move"]');
        const deleteItem = ctx.querySelector('[data-action="delete"]');

        if(createItem) createItem.style.display = isUngrouped ? 'none' : 'block';
        if(renameItem) renameItem.style.display = isUngrouped ? 'none' : 'block';
        if(moveItem) moveItem.style.display = isUngrouped ? 'none' : 'block';
        if(deleteItem) deleteItem.style.display = isUngrouped ? 'none' : 'block';

        ctx.dataset.groupId = groupId;
    });

    document.getElementById('group-context-menu')?.addEventListener('click', function(e) {
        const actionItem = e.target.closest('[data-action]');
        if (!actionItem) return;

        const groupId = this.dataset.groupId;
        const action = actionItem.dataset.action;

        if (action === 'create-child') {
            showCreateGroupModal(groupId);
        } else if (action === 'rename') {
            showRenameModal(groupId);
        } else if (action === 'move') {
            showMoveGroupModal(groupId);
        } else if (action === 'delete') {
            showDeleteModal(groupId);
        }

        this.style.display = 'none';
    });
}
```

### 📄 `static/js/modules/scans.js`

```javascript
// static/js/modules/scans.js

export async function viewScanResults(id) {
    const modalId = 'scanResultsModal';
    const modalEl = document.getElementById(modalId);
    if(!modalEl) return;

    const m = new bootstrap.Modal(modalEl);
    const c = document.getElementById('scan-results-content');
    const errAlert = document.getElementById('scan-error-alert');
    const errText = document.getElementById('scan-error-text');
    
    if(c) c.innerHTML = '<div class="text-center"><div class="spinner-border"></div><p class="mt-2">Загрузка...</p></div>';
    if(errAlert) errAlert.style.display = 'none';
    
    m.show();
    
    try{
        const r = await fetch(`/api/scans/${id}/results`);
        const d = await r.json();
        
        if(d.job.status === 'failed' && d.job.error_message){
            if(errAlert) errAlert.style.display = 'block';
            if(errText) errText.textContent = d.job.error_message;
        }
        
        let h = `<h6>#${d.job.id} - ${d.job.scan_type.toUpperCase()}</h6>`;
        h += `<p><strong>Цель:</strong> ${d.job.target}</p>`;
        h += `<p><strong>Статус:</strong> <span class="badge bg-${d.job.status==='completed'?'success':d.job.status==='failed'?'danger':'warning'}">${d.job.status}</span></p>`;
        h += `<p><strong>Прогресс:</strong> ${d.job.progress}%</p>`;
        if(d.job.started_at) h += `<p><strong>Начало:</strong> ${d.job.started_at}</p>`;
        if(d.job.completed_at) h += `<p><strong>Завершение:</strong> ${d.job.completed_at}</p>`;
        h += `<hr>`;
        
        if(d.job.status === 'failed'){
            h += '<div class="alert alert-danger"><i class="bi bi-exclamation-triangle"></i> Сканирование завершилось с ошибкой.</div>';
        } else if(!d.results || d.results.length === 0){
            h += '<p class="text-muted">Нет результатов</p>';
        } else {
            h += `<p><strong>Найдено хостов:</strong> ${d.results.length}</p><div class="list-group">`;
            d.results.forEach(x=>{
                h += `<div class="list-group-item"><div class="d-flex justify-content-between"><h6 class="mb-1">${x.ip}</h6><small>${x.scanned_at}</small></div><p class="mb-1"><strong>Порты:</strong> ${x.ports && x.ports.join ? x.ports.join(', ') : 'Нет'}</p>${x.os && x.os !== '-' ? `<p class="mb-0"><strong>ОС:</strong> ${x.os}</p>`:''}</div>`;
            });
            h += '</div>';
        }
        if(c) c.innerHTML = h;
    }catch(err){ 
        if(errAlert) errAlert.style.display = 'block';
        if(errText) errText.textContent = `Ошибка загрузки результатов: ${err.message}`;
    }
}

export function showScanError(jobId, errorMsg){
    const modalId = 'scanErrorModal';
    const modalEl = document.getElementById(modalId);
    if(!modalEl) return alert(errorMsg);

    const m = new bootstrap.Modal(modalEl);
    const c = document.getElementById('scan-error-content');
    const safeMsg = errorMsg ? errorMsg.replace(/\\/g, '\\\\').replace(/`/g, '\\`').replace(/\$/g, '\\$') : 'Неизвестная ошибка';
    
    if(c) {
        c.innerHTML = `
            <div class="alert alert-danger">
                <h6><i class="bi bi-exclamation-triangle"></i> Ошибка сканирования #${jobId}:</h6>
                <pre class="mb-0" style="white-space:pre-wrap;max-height:400px;overflow-y:auto">${safeMsg}</pre>
            </div>
            <div class="mt-3">
                <button class="btn btn-sm btn-outline-secondary" onclick="navigator.clipboard.writeText('${safeMsg}')">
                    <i class="bi bi-clipboard"></i> Копировать ошибку
                </button>
            </div>
        `;
    }
    m.show();
}

export async function updateScanHistory(){
    try{
        const res = await fetch('/api/scans/history');
        if(!res.ok) return;
        const jobs = await res.json();
        const tbody = document.querySelector('#history-table tbody');
        if(!tbody) return;

        jobs.forEach(j=>{
            const row = document.getElementById(`scan-row-${j.id}`);
            if(!row) return;
            
            const badge = row.querySelector('.status-badge');
            if(badge){
                badge.textContent = j.status;
                badge.className = `badge status-badge bg-${j.status==='running'?'warning text-dark':j.status==='completed'?'success':'danger'}`;
                
                if(j.error_message){
                    badge.style.cursor = 'pointer';
                    badge.setAttribute('title', 'Нажмите для просмотра детали ошибки');
                    badge.onclick = () => showScanError(j.id, j.error_message);
                } else {
                    badge.style.cursor = 'default';
                    badge.removeAttribute('onclick');
                }
            }
            const bar = row.querySelector('.progress-bar');
            const txt = row.querySelector('.progress-text');
            if(bar) bar.style.width = `${j.progress}%`;
            if(txt) txt.textContent = `${j.progress}%`;
        });
    }catch(e){console.warn('History poll error:',e);}
}

export async function pollActiveScans() {
    try {
        const res = await fetch('/api/scans/status');
        if (!res.ok) return;
        const data = await res.json();
        
        if (data.active && data.active.length > 0) {
            if (typeof updateScanHistory === 'function') {
                updateScanHistory();
            }
        }
    } catch (e) {
        console.warn('⚠️ Ошибка проверки сканирований:', e);
    }
}

// Экспорт глобальных функций
window.viewScanResults = viewScanResults;
window.showScanError = showScanError;
```

### 📄 `static/js/modules/theme.js`

```javascript
// static/js/modules/theme.js
export function initTheme() {
    const savedTheme = localStorage.getItem('theme') || 'light';
    document.documentElement.setAttribute('data-bs-theme', savedTheme === 'dark' ? 'dark' : 'light');
    updateThemeIcon(savedTheme);
}

export function toggleTheme() {
    const html = document.documentElement;
    const newTheme = html.getAttribute('data-bs-theme') === 'dark' ? 'light' : 'dark';
    document.body.classList.add('theme-transition');
    html.setAttribute('data-bs-theme', newTheme);
    localStorage.setItem('theme', newTheme);
    updateThemeIcon(newTheme);
    setTimeout(() => document.body.classList.remove('theme-transition'), 300);
}

function updateThemeIcon(theme) {
    const toggle = document.querySelector('.theme-toggle');
    if (!toggle) return;
    const moon = toggle.querySelector('.bi-moon');
    const sun = toggle.querySelector('.bi-sun');
    if(moon) moon.style.display = theme === 'dark' ? 'none' : 'block';
    if(sun) sun.style.display = theme === 'dark' ? 'block' : 'none';
}
```

### 📄 `static/js/modules/tree.js`

```javascript
// static/js/modules/tree.js
import { renderAssets } from './assets.js';

let currentFilter = { groupId: null, ungrouped: false };
let treeListenerAttached = false;

// 🔒 Безопасная нормализация ID (приводим всё к строке, null -> 'null')
const normId = (val) => (val === null || val === undefined) ? 'null' : String(val);

export async function refreshGroupTree() {
    try {
        const res = await fetch('/api/groups/tree');
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        
        if (!data.flat || !Array.isArray(data.flat)) {
            console.error('❌ Неверный формат данных дерева:', data);
            return;
        }

        const treeContainer = document.getElementById('group-tree');
        if (!treeContainer) return;

        // Сохраняем активный узел до перерисовки
        const activeNode = treeContainer.querySelector('.tree-node.active');
        const activeId = activeNode ? normId(activeNode.dataset.id) : null;
        const isUngrouped = !!document.querySelector('.tree-node[data-id="ungrouped"].active');

        // 🌳 Рекурсивный рендер дерева
        const buildTreeHtml = (nodes, parentId = null) => {
            const pIdStr = normId(parentId);
            // Ищем прямых детей текущего родителя
            const children = nodes.filter(n => normId(n.parent_id) === pIdStr);
            if (children.length === 0) return '';

            let html = '';
            children.forEach(node => {
                const nIdStr = normId(node.id);
                // ✅ ИСПРАВЛЕНО: Проверяем наличие детей строго по совпадению ID
                const hasChildren = nodes.some(n => normId(n.parent_id) === nIdStr);
                
                const isDynamic = node.is_dynamic;
                const typeIcon = isDynamic ? '<i class="bi bi-funnel ms-1 text-muted" title="Динамическая группа"></i>' : '';

                html += `<li>`;
                html += `
                    <div class="tree-node" data-id="${node.id}">
                        ${hasChildren ? '<span class="caret"></span>' : '<span class="caret-spacer"></span>'}
                        <i class="bi bi-folder folder-icon"></i>
                        <span class="group-name" data-id="${node.id}" data-type="${isDynamic ? 'dynamic' : 'manual'}">
                            ${node.name} ${typeIcon}
                        </span>
                        <span class="badge bg-secondary ms-auto">${node.asset_count ?? node.count ?? 0}</span>
                        <span class="group-actions ms-2">
                            <button type="button" class="btn-action" onclick="window.showRenameModal(${node.id})" title="Редактировать">
                                <i class="bi bi-pencil"></i>
                            </button>
                            <button type="button" class="btn-action text-danger" onclick="window.showDeleteModal(${node.id})" title="Удалить">
                                <i class="bi bi-trash"></i>
                            </button>
                        </span>
                    </div>
                `;

                if (hasChildren) {
                    const childrenHtml = buildTreeHtml(nodes, node.id);
                    if (childrenHtml) html += `<ul class="nested">${childrenHtml}</ul>`;
                }
                html += `</li>`;
            });

            return html;
        };

        const ungroupedHtml = `
            <li>
                <div class="tree-node" data-id="ungrouped">
                    <span class="caret-spacer"></span>
                    <i class="bi bi-inbox folder-icon"></i>
                    <span class="group-name" data-id="ungrouped">Без группы</span>
                    <span class="badge bg-secondary ms-auto">${data.ungrouped_count || 0}</span>
                </div>
            </li>
        `;

        // Рендерим в контейнер
        treeContainer.innerHTML = `<ul>${ungroupedHtml + buildTreeHtml(data.flat)}</ul>`;

        // ♻️ Восстановление состояния (выделение + раскрытие родителей)
        if (isUngrouped) {
            const n = treeContainer.querySelector('.tree-node[data-id="ungrouped"]');
            if (n) n.classList.add('active');
        } else if (activeId) {
            const targetId = activeId === 'null' ? 'ungrouped' : activeId;
            const node = treeContainer.querySelector(`.tree-node[data-id="${targetId}"]`);
            if (node) {
                node.classList.add('active');
                let el = node.closest('li');
                while (el) {
                    const parentUl = el.parentElement;
                    if (parentUl && parentUl.classList.contains('nested')) {
                        parentUl.classList.add('active');
                        const grandLi = parentUl.closest('li');
                        if (grandLi) {
                            const caret = grandLi.querySelector(':scope > .tree-node > .caret');
                            if (caret) caret.classList.add('down');
                        }
                        el = grandLi;
                    } else break;
                }
                node.scrollIntoView({ behavior: 'smooth', block: 'center' });
            }
        }

        // Инициализируем обработчики кликов
        initTreeTogglers();
    } catch (e) {
        console.error('❌ Ошибка обновления дерева групп:', e);
    }
}

export async function loadAssets(groupId = null, ungrouped = false) {
    let url;
    if (ungrouped) url = '/api/assets?ungrouped=true';
    else if (groupId) url = `/api/assets?group_id=${parseInt(groupId)}`;
    else url = '/api/assets';
    try {
        const res = await fetch(url);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        renderAssets(await res.json());
        currentFilter = { groupId, ungrouped };
    } catch (e) { console.error('❌ Ошибка загрузки активов:', e); }
}

export function filterByGroup(groupId) {
    document.querySelectorAll('.tree-node').forEach(el => el.classList.remove('active'));
    const activeNode = document.querySelector(`.tree-node[data-id="${groupId}"]`);
    if (activeNode) activeNode.classList.add('active');
    if (groupId === 'ungrouped') loadAssets(null, true);
    else loadAssets(parseInt(groupId), false);
}

export function initTreeTogglers() {
    if (treeListenerAttached) return; // 🛡️ Защита от дублирования при поллинге/обновлении
    const treeContainer = document.getElementById('group-tree');
    if (!treeContainer) return;

    treeContainer.addEventListener('click', function(e) {
        // ✅ Игнорируем клики по кнопкам действий
        if (e.target.closest('.group-actions') || e.target.closest('.btn-action')) return;

        // 1. Клик по стрелке (раскрытие/сворачивание)
        const caret = e.target.closest('.caret');
        if (caret) {
            e.preventDefault(); e.stopPropagation();
            const parentLi = caret.closest('li');
            if (parentLi) {
                const nestedUl = parentLi.querySelector(':scope > ul.nested');
                if (nestedUl) nestedUl.classList.toggle('active');
            }
            caret.classList.toggle('down');
            return;
        }

        // 2. Клик по названию группы
        const groupSpan = e.target.closest('.group-name');
        if (groupSpan) filterByGroup(groupSpan.dataset.id);
    });

    treeListenerAttached = true;
}

export function getCurrentFilter() { return currentFilter; }
```

### 📄 `static/js/modules/utils.js`

```javascript
// static/js/modules/utils.js

/**
 * Заполняет выпадающие списки родительских групп с визуальной иерархией.
 */
export async function populateParentSelect(excludeIds = [], selectedId = null) {
    try {
        const res = await fetch('/api/groups/tree');
        if (!res.ok) throw new Error('Failed to fetch tree');
        const data = await res.json();
        
        if (!data.flat) return;

        // Построение дерева
        const buildTree = (parentId) => {
            return data.flat
                .filter(g => g.parent_id == parentId)
                .map(g => ({
                    ...g,
                    children: buildTree(g.id)
                }));
        };
        const tree = buildTree(null);

        // Генерация опций
        const generateOptions = (nodes, level = 0) => {
            let options = '';
            nodes.forEach(node => {
                if (excludeIds.includes(String(node.id))) return;

                const indent = '    '; // 4 пробела
                const prefix = level > 0 ? '└─ ' : '';
                const label = (indent.repeat(level)) + prefix + node.name;
                
                const option = document.createElement('option');
                option.value = node.id;
                option.text = label; 
                if (selectedId !== null && String(node.id) === String(selectedId)) {
                    option.selected = true;
                }
                
                options += option.outerHTML;
                
                if (node.children && node.children.length > 0) {
                    options += generateOptions(node.children, level + 1);
                }
            });
            return options;
        };

        const baseOption = '<option value="">-- Корень --</option>';
        const optionsContent = baseOption + generateOptions(tree);

        const selectors = [
            '#edit-group-parent',   
            '#move-group-parent',   
            '#delete-move-assets'   
        ];

        selectors.forEach(sel => {
            const el = document.querySelector(sel);
            if (el) {
                // 1. Сначала очищаем и заполняем контент
                el.innerHTML = optionsContent;
                
                // 2. Явно добавляем класс для стилей (важно для всех страниц)
                el.classList.add('hierarchy-select');
                
                // 3. Принудительно задаем стиль через JS, если CSS по какой-то причине не применился
                el.style.fontFamily = "'Consolas', 'Monaco', 'Courier New', monospace";
                
                // 4. Восстанавливаем выбор
                const currentVal = selectedId !== null ? selectedId : el.getAttribute('data-last-value') || el.value;
                if (currentVal) {
                    el.value = currentVal;
                } else {
                    el.value = ""; // Сброс на "-- Корень --" если ничего не выбрано
                }
                
                // Сохраняем текущее значение для возможного следующего открытия
                el.setAttribute('data-last-value', el.value);
            }
        });

    } catch (e) {
        console.error('Ошибка загрузки дерева групп:', e);
    }
}

export function closeModalById(modalId) {
    const modalEl = document.getElementById(modalId);
    if (!modalEl) return;

    const modalInstance = bootstrap.Modal.getInstance(modalEl);
    
    if (modalInstance) {
        modalInstance.hide();
    } else {
        modalEl.classList.remove('show');
        modalEl.removeAttribute('aria-modal');
        modalEl.removeAttribute('role');
        modalEl.style.display = '';
        
        const backdrop = document.querySelector('.modal-backdrop');
        if (backdrop) backdrop.remove();
        
        document.body.classList.remove('modal-open');
        document.body.style.overflow = '';
        document.body.style.paddingRight = '';
    }

    const form = modalEl.querySelector('form');
    if (form) form.reset();
}

// 🔥 ДОБАВЛЯЕМ СТИЛЬ ДЛЯ СОХРАНЕНИЯ ПРОБЕЛОВ В SELECT
if (!document.getElementById('hierarchy-select-style')) {
    const style = document.createElement('style');
    style.id = 'hierarchy-select-style';
    style.textContent = `
        select.hierarchy-select, 
        select.hierarchy-select option {
            font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
            white-space: pre;
        }
    `;
    document.head.appendChild(style);
}
```

### 📄 `static/js/modules/wazuh.js`

```javascript
// static/js/modules/wazuh.js

export function initWazuhFilter() {
    const dsFilter = document.getElementById('data-source-filter');
    if(dsFilter) {
        dsFilter.addEventListener('change', function() {
            const p = new URLSearchParams(window.location.search); 
            p.set('data_source', this.value); 
            window.location.search = p.toString();
        });
    }
}

export async function saveWazuhConfig() {
    const urlInput = document.getElementById('wazuh-url');
    const userInput = document.getElementById('wazuh-user');
    const passInput = document.getElementById('wazuh-pass');
    
    if(!urlInput || !userInput || !passInput) return;
    
    const config = {
        url: urlInput.value.trim(),
        username: userInput.value.trim(),
        password: passInput.value
    };
    
    try {
        const res = await fetch('/api/wazuh/config', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(config)
        });
        
        if(!res.ok) throw new Error('Ошибка сохранения конфигурации');
        
        alert('Конфигурация Wazuh сохранена');
    } catch(e) {
        console.error('Ошибка сохранения Wazuh:', e);
        alert(e.message);
    }
}

export async function testWazuhConnection() {
    try {
        const res = await fetch('/api/wazuh/test');
        const data = await res.json();
        
        if(data.success) {
            alert('✅ Подключение к Wazuh успешно!');
        } else {
            alert('❌ Ошибка подключения: ' + (data.error || 'Неизвестная ошибка'));
        }
    } catch(e) {
        alert('❌ Ошибка подключения: ' + e.message);
    }
}
```

### 📄 `static/css/style.css`

```css
/* ═══════════════════════════════════════════════════════════════
   BOOTSTRAP 5 THEME - LIGHT & DARK MODE
   ═══════════════════════════════════════════════════════════════ */
:root {
    --bs-primary: #0d6efd; --bs-secondary: #6c757d; --bs-success: #198754; --bs-info: #0dcaf0; --bs-warning: #ffc107; --bs-danger: #dc3545;
    --bg-body: #f8f9fa; --bg-card: #ffffff; --bg-sidebar: #ffffff; --bg-hover: #f1f3f5; --bg-input: #ffffff;
    --text-primary: #212529; --text-secondary: #6c757d; --text-muted: #adb5bd;
    --border-color: #dee2e6; --shadow-sm: 0 0.125rem 0.25rem rgba(0,0,0,0.075); --shadow-md: 0 0.5rem 1rem rgba(0,0,0,0.15);
    --font-primary: system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
}
[data-bs-theme="dark"] {
    --bs-primary: #3d8bfd; --bs-secondary: #6c757d; --bs-success: #20c997; --bs-info: #6edff6; --bs-warning: #ffda6a; --bs-danger: #ea868f;
    --bg-body: #212529; --bg-card: #2b3035; --bg-sidebar: #2b3035; --bg-hover: #343a40; --bg-input: #2b3035;
    --text-primary: #f8f9fa; --text-secondary: #adb5bd; --text-muted: #6c757d;
    --border-color: #495057; --shadow-sm: 0 0.125rem 0.25rem rgba(0,0,0,0.3); --shadow-md: 0 0.5rem 1rem rgba(0,0,0,0.4);
}
body { background-color: var(--bg-body); color: var(--text-primary); font-family: var(--font-primary); transition: background-color 0.3s ease, color 0.3s ease; }
::-webkit-scrollbar { width: 8px; } ::-webkit-scrollbar-track { background: var(--bg-body); } ::-webkit-scrollbar-thumb { background: var(--bs-secondary); border-radius: 4px; }
.sidebar { min-height: 100vh; background: var(--bg-sidebar); border-right: 1px solid var(--border-color); transition: all 0.3s ease; }
.navbar { background: var(--bg-card) !important; border: 1px solid var(--border-color); border-radius: 0.5rem; box-shadow: var(--shadow-sm); }
.card { background: var(--bg-card); border: 1px solid var(--border-color); border-radius: 0.5rem; box-shadow: var(--shadow-sm); transition: all 0.3s ease; }
.table { color: var(--text-primary); } .table thead { background: var(--bg-body); border-bottom: 2px solid var(--border-color); }
.form-control, .form-select { background: var(--bg-input); border: 1px solid var(--border-color); color: var(--text-primary); }
.tree-node { cursor: pointer; padding: 0.5rem 0.75rem; border-radius: 0.375rem; border-left: 3px solid transparent; color: var(--text-secondary); }
.tree-node:hover { background-color: var(--bg-hover); border-left-color: var(--bs-primary); color: var(--text-primary); }
.tree-node.active { background: rgba(13, 110, 253, 0.1); border-left-color: var(--bs-primary); color: var(--bs-primary); }
.context-menu { display: none; position: absolute; z-index: 1050; min-width: 220px; background: var(--bg-card); border: 1px solid var(--border-color); box-shadow: var(--shadow-md); border-radius: 0.5rem; padding: 0.5rem 0; }
.context-menu-item { display: flex; align-items: center; gap: 0.625rem; width: 100%; padding: 0.5rem 0.875rem; color: var(--text-primary); text-decoration: none; background: transparent; border: 0; cursor: pointer; }
.context-menu-item:hover { background: var(--bg-hover); color: var(--bs-primary); }
.filter-group { border: 1px solid var(--border-color); padding: 1rem; border-radius: 0.5rem; margin-bottom: 0.75rem; background: var(--bg-card); position: relative; }
.filter-condition { display: flex; gap: 0.5rem; align-items: center; margin-bottom: 0.5rem; background: var(--bg-body); padding: 0.5rem; border-radius: 0.375rem; }
@media (max-width: 768px) { .sidebar { display: none !important; } }
.group-actions {
    display: flex;
    gap: 4px;
    opacity: 0; /* Скрыты по умолчанию */
    transition: opacity 0.2s;
}

.tree-node:hover .group-actions {
    opacity: 1; /* Показываем при наведении на группу */
}

.btn-action {
    background: transparent;
    border: none;
    padding: 2px 4px;
    cursor: pointer;
    color: inherit;
    border-radius: 4px;
}

.btn-action:hover {
    background-color: var(--bg-hover);
    color: var(--bs-primary);
}

.btn-action.text-danger:hover {
    background-color: rgba(220, 53, 69, 0.1);
    color: var(--bs-danger);
}


/* ═══════════════════════════════════════════════════════════════
   СТИЛИ ДЛЯ ДЕРЕВА ГРУПП
   ═══════════════════════════════════════════════════════════════ */

/* Контейнер дерева групп */
#group-tree {
    padding: 0.25rem 0;
}

#group-tree ul {
    list-style: none;
    padding-left: 0;
    margin: 0;
}

#group-tree ul.nested {
    padding-left: 1.5rem;
    margin-top: 0.25rem;
}

/* Скрытие/отображение вложенных списков */
#group-tree ul.nested {
    display: none;
}

#group-tree ul.nested.active {
    display: block;
}

#group-tree li {
    margin: 0.125rem 0;
    position: relative;
}

/* Элемент дерева (узел) */
.tree-node {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    user-select: none;
    -webkit-user-select: none;
}

/* Индикатор раскрытия/сворачивания (caret) */
.caret {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 1.25rem;
    height: 1.25rem;
    cursor: pointer;
    transition: transform 0.2s ease;
    color: var(--text-secondary);
    flex-shrink: 0;
}

.caret::before {
    content: "▶";
    font-size: 0.625rem;
    display: inline-block;
}

.caret.down {
    transform: rotate(90deg);
}

/* Пустой спейсер вместо caret для листовых узлов */
.caret-spacer {
    display: inline-block;
    width: 1.25rem;
    height: 1.25rem;
    flex-shrink: 0;
}

/* Иконка папки для группы */
.tree-node .folder-icon {
    color: var(--text-secondary);
    flex-shrink: 0;
}

.tree-node:hover .folder-icon {
    color: var(--bs-primary);
}

.tree-node.active .folder-icon {
    color: var(--bs-primary);
}

/* Название группы */
.tree-node .group-name {
    flex-grow: 1;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}

/* Бейдж с количеством активов */
.tree-node .badge {
    flex-shrink: 0;
    font-size: 0.75rem;
    min-width: 1.5rem;
    justify-content: center;
}
```

### 📄 `templates/asset_detail.html`

```html
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ asset.ip_address }} | Asset Manager</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.10.0/font/bootstrap-icons.css" rel="stylesheet">
    <link href="{{ url_for('static', filename='css/style.css') }}" rel="stylesheet">
    <style>
        .status-indicator { width: 12px; height: 12px; border-radius: 50%; display: inline-block; margin-right: 8px; }
        .status-up { background-color: #198754; }
        .status-down { background-color: #dc3545; }
        .port-badge { font-size: 0.875rem; padding: 0.5rem 0.75rem; }
        .script-output { background: var(--bg-body); border: 1px solid var(--border-color); border-radius: 0.375rem; padding: 0.75rem; max-height: 300px; overflow-y: auto; font-size: 0.75rem; }
        .nav-tabs .nav-link { color: var(--text-secondary); }
        .nav-tabs .nav-link.active { color: var(--text-primary); font-weight: 600; }
        .rustscan-header { background: linear-gradient(135deg, #dc3545 0%, #c82333 100%); }
        .nmap-header { background: linear-gradient(135deg, #0dcaf0 0%, #0bb5d8 100%); }
        .combined-header { background: linear-gradient(135deg, #0d6efd 0%, #0b5ed7 100%); }
    </style>
</head>
<body>
    <div class="container-fluid">
        <div class="row">
            <!-- Sidebar -->
            <div class="col-md-3 col-lg-2 sidebar p-3 d-none d-md-block">
                <h5 class="mb-3"><i class="bi bi-folder-tree"></i> Группы</h5>
                {% include 'components/group_tree.html' %}
            </div>

            <!-- Main Content -->
            <div class="col-md-9 col-lg-10 p-4">
                <!-- Navigation -->
                <nav class="navbar navbar-light mb-4 px-3">
                    <div class="d-flex align-items-center">
                        <a href="{{ url_for('main.index') }}" class="btn btn-outline-dark me-3">
                            <i class="bi bi-arrow-left"></i> Назад
                        </a>
                        <span class="navbar-brand mb-0 h1">
                            <i class="bi bi-pc-display"></i> {{ asset.ip_address }}
                            {% if asset.hostname %}<small class="text-muted">({{ asset.hostname }})</small>{% endif %}
                        </span>
                    </div>
                    <div class="d-flex align-items-center">
                        <button class="theme-toggle me-2" onclick="toggleTheme()" aria-label="Переключить тему">
                            <i class="bi bi-moon"></i><i class="bi bi-sun"></i>
                        </button>
                        <a href="{{ url_for('main.asset_history', id=asset.id) }}" class="btn btn-outline-info me-2" title="История изменений">
                            <i class="bi bi-clock-history"></i> История
                        </a>
                        <a href="{{ url_for('main.asset_taxonomy', id=asset.id) }}" class="btn btn-outline-success me-2" title="Таксономия актива">
                            <i class="bi bi-diagram-3"></i> Таксономия
                        </a>
                        <a href="{{ url_for('main.delete_asset', id=asset.id) }}" class="btn btn-outline-danger" onclick="return confirm('Удалить актив {{ asset.ip_address }}?')" title="Удалить актив">
                            <i class="bi bi-trash"></i>
                        </a>
                    </div>
                </nav>

                <!-- Flash Messages -->
                {% with messages = get_flashed_messages(with_categories=true) %}
                    {% if messages %}
                        {% for c, m in messages %}
                        <div class="alert alert-{{ c }} alert-dismissible fade show" role="alert">
                            {{ m }}
                            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
                        </div>
                        {% endfor %}
                    {% endif %}
                {% endwith %}

                <!-- Status Card -->
                <div class="card mb-4 {% if asset.status == 'up' %}border-success{% else %}border-danger{% endif %}">
                    <div class="card-body d-flex align-items-center justify-content-between">
                        <div class="d-flex align-items-center">
                            <span class="status-indicator {% if asset.status == 'up' %}status-up{% else %}status-down{% endif %}"></span>
                            <div>
                                <h4 class="mb-0">
                                    {% if asset.status == 'up' %}
                                        <span class="text-success">Активен</span>
                                    {% else %}
                                        <span class="text-danger">Не доступен</span>
                                    {% endif %}
                                </h4>
                                <small class="text-muted">
                                    Последнее сканирование: {{ asset.last_scanned.strftime('%Y-%m-%d %H:%M') if asset.last_scanned else '—' }}
                                </small>
                            </div>
                        </div>
                        <span class="badge {% if asset.status == 'up' %}bg-success{% else %}bg-danger{% endif %} fs-6">
                            {{ asset.status.upper() }}
                        </span>
                    </div>
                </div>

                <!-- Main Info Tabs -->
                <ul class="nav nav-tabs mb-3" id="assetTabs" role="tablist">
                    <li class="nav-item">
                        <button class="nav-link active" data-bs-toggle="tab" data-bs-target="#tab-info">📊 Информация</button>
                    </li>
                    <li class="nav-item">
                        <button class="nav-link" data-bs-toggle="tab" data-bs-target="#tab-ports">🔌 Порты</button>
                    </li>
                    <li class="nav-item">
                        <button class="nav-link" data-bs-toggle="tab" data-bs-target="#tab-inventory">📦 Инвентаризация</button>
                    </li>
                    <li class="nav-item">
                        <button class="nav-link" data-bs-toggle="tab" data-bs-target="#tab-scans">🔍 Сканирования</button>
                    </li>
                </ul>

                <div class="tab-content" id="assetTabsContent">
                    <!-- Tab: Информация -->
                    <div class="tab-pane fade show active" id="tab-info">
                        <div class="row">
                            <div class="col-lg-8">
                                <div class="card mb-4">
                                    <div class="card-header"><i class="bi bi-info-circle"></i> Основные данные</div>
                                    <div class="card-body">
                                        <div class="row">
                                            <div class="col-md-6 mb-3">
                                                <div class="text-muted small text-uppercase">IP Адрес</div>
                                                <div class="fw-medium"><i class="bi bi-globe"></i> {{ asset.ip_address }}</div>
                                            </div>
                                            <div class="col-md-6 mb-3">
                                                <div class="text-muted small text-uppercase">Hostname</div>
                                                <div class="fw-medium"><i class="bi bi-pc-display"></i> {{ asset.hostname or 'Не определён' }}</div>
                                            </div>
                                            <div class="col-md-6 mb-3">
                                                <div class="text-muted small text-uppercase">ОС</div>
                                                <div class="fw-medium"><i class="bi bi-windows"></i> {{ asset.os_info or 'Не определена' }}</div>
                                            </div>
                                            <div class="col-md-6 mb-3">
                                                <div class="text-muted small text-uppercase">Роль</div>
                                                <div class="fw-medium"><i class="bi bi-tag"></i> {{ asset.device_role or 'Не определена' }}</div>
                                            </div>
                                            <div class="col-md-6 mb-3">
                                                <div class="text-muted small text-uppercase">Группа</div>
                                                <form action="{{ url_for('main.update_asset_group', id=asset.id) }}" method="POST" class="d-inline">
                                                    <select name="group_id" class="form-select form-select-sm" style="width: 200px;" onchange="this.form.submit()">
                                                        <option value="">-- Без группы --</option>
                                                        {% for g in all_groups %}
                                                            <option value="{{ g.id }}" {% if asset.group_id == g.id %}selected{% endif %}>{{ g.name }}</option>
                                                        {% endfor %}
                                                    </select>
                                                </form>
                                            </div>
                                            <div class="col-md-6 mb-3">
                                                <div class="text-muted small text-uppercase">Источник данных</div>
                                                <div class="fw-medium">
                                                    {% if asset.data_source == 'wazuh' %}🛡️ Wazuh
                                                    {% elif asset.data_source == 'osquery' %}📦 OSquery
                                                    {% elif asset.data_source == 'scanning' %}🔍 Сканирование
                                                    {% else %}✏️ Ручной{% endif %}
                                                </div>
                                            </div>
                                            <div class="col-md-6 mb-3">
                                                <div class="text-muted small text-uppercase">Последнее Rustscan</div>
                                                <div class="fw-medium">{{ asset.last_rustscan.strftime('%Y-%m-%d %H:%M') if asset.last_rustscan else '—' }}</div>
                                            </div>
                                            <div class="col-md-6 mb-3">
                                                <div class="text-muted small text-uppercase">Последнее Nmap</div>
                                                <div class="fw-medium">{{ asset.last_nmap.strftime('%Y-%m-%d %H:%M') if asset.last_nmap else '—' }}</div>
                                            </div>
                                        </div>
                                    </div>
                                </div>

                                <div class="card mb-4">
                                    <div class="card-header"><i class="bi bi-journal-text"></i> Заметки</div>
                                    <div class="card-body">
                                        <form action="{{ url_for('main.update_asset_notes', id=asset.id) }}" method="POST">
                                            <textarea name="notes" class="form-control" rows="6" placeholder="Заметки...">{{ asset.notes or '' }}</textarea>
                                            <button type="submit" class="btn btn-primary w-100 mt-2">
                                                <i class="bi bi-save"></i> Сохранить
                                            </button>
                                        </form>
                                    </div>
                                </div>
                            </div>

                            <div class="col-lg-4">
                                <div class="card mb-4">
                                    <div class="card-header"><i class="bi bi-info-circle"></i> Дополнительная информация</div>
                                    <div class="card-body">
                                        <div class="mb-3">
                                            <small class="text-muted">DNS имена</small>
                                            <div class="fw-medium">{{ asset.dns_names or '—' }}</div>
                                        </div>
                                        <div class="mb-3">
                                            <small class="text-muted">Последнее сканирование</small>
                                            <div class="fw-medium">{{ asset.last_scanned.strftime('%Y-%m-%d %H:%M') if asset.last_scanned else '—' }}</div>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>

                    <!-- Tab: Порты -->
                    <div class="tab-pane fade" id="tab-ports">
                        <!-- 🔹 Rustscan Ports -->
                        <div class="card mb-4 border-danger">
                            <div class="card-header d-flex justify-content-between align-items-center rustscan-header text-white">
                                <span><i class="bi bi-lightning-charge"></i> Порты Rustscan</span>
                                <span class="badge bg-light text-dark">
                                    {{ (asset.rustscan_ports.split(', ') | length) if asset.rustscan_ports else 0 }}
                                </span>
                            </div>
                            <div class="card-body">
                                {% if asset.rustscan_ports %}
                                    <div class="row">
                                        {% for p in asset.rustscan_ports.split(', ') | sort %}
                                            <div class="col-md-4 col-sm-6 mb-2">
                                                <span class="badge bg-light text-dark border port-badge">
                                                    <i class="bi bi-lightning-charge text-danger"></i> <strong>{{ p }}</strong>
                                                </span>
                                            </div>
                                        {% endfor %}
                                    </div>
                                    <div class="mt-3 text-muted small">
                                        <i class="bi bi-clock"></i> Последнее сканирование: 
                                        {{ asset.last_rustscan.strftime('%Y-%m-%d %H:%M') if asset.last_rustscan else '—' }}
                                    </div>
                                {% else %}
                                    <div class="text-center py-4">
                                        <i class="bi bi-lightning-charge fs-1 text-muted d-block mb-2"></i>
                                        <p class="text-muted mb-0">Rustscan не запускался для этого актива.</p>
                                        <a href="{{ url_for('scans.scans_page') }}" class="btn btn-outline-danger mt-3">
                                            <i class="bi bi-lightning-charge"></i> Запустить Rustscan
                                        </a>
                                    </div>
                                {% endif %}
                            </div>
                        </div>

                        <!-- 🔹 Nmap Ports -->
                        <div class="card mb-4 border-info">
                            <div class="card-header d-flex justify-content-between align-items-center nmap-header text-dark">
                                <span><i class="bi bi-radar"></i> Порты Nmap</span>
                                <span class="badge bg-light text-dark">
                                    {{ (asset.nmap_ports.split(', ') | length) if asset.nmap_ports else 0 }}
                                </span>
                            </div>
                            <div class="card-body">
                                {% if asset.nmap_ports %}
                                    <div class="row">
                                        {% for p in asset.nmap_ports.split(', ') | sort %}
                                            <div class="col-md-4 col-sm-6 mb-2">
                                                <span class="badge bg-light text-dark border port-badge">
                                                    <i class="bi bi-radar text-info"></i> <strong>{{ p }}</strong>
                                                </span>
                                            </div>
                                        {% endfor %}
                                    </div>
                                    <div class="mt-3 text-muted small">
                                        <i class="bi bi-clock"></i> Последнее сканирование: 
                                        {{ asset.last_nmap.strftime('%Y-%m-%d %H:%M') if asset.last_nmap else '—' }}
                                    </div>
                                {% else %}
                                    <div class="text-center py-4">
                                        <i class="bi bi-radar fs-1 text-muted d-block mb-2"></i>
                                        <p class="text-muted mb-0">Nmap не запускался для этого актива.</p>
                                        <a href="{{ url_for('scans.scans_page') }}" class="btn btn-outline-info mt-3">
                                            <i class="bi bi-radar"></i> Запустить Nmap
                                        </a>
                                    </div>
                                {% endif %}
                            </div>
                        </div>

                        <!-- 🔹 Объединённые порты -->
                        <div class="card">
                            <div class="card-header d-flex justify-content-between align-items-center combined-header text-white">
                                <span><i class="bi bi-hdd-network"></i> Все порты (объединено)</span>
                                <span class="badge bg-light text-dark">
                                    {{ (asset.open_ports.split(', ') | length) if asset.open_ports else 0 }}
                                </span>
                            </div>
                            <div class="card-body">
                                {% if asset.open_ports %}
                                    <div class="row">
                                        {% for p in asset.open_ports.split(', ') | sort %}
                                            <div class="col-md-4 col-sm-6 mb-2">
                                                <span class="badge bg-light text-dark border port-badge">
                                                    <i class="bi bi-hdd-network"></i> <strong>{{ p }}</strong>
                                                </span>
                                            </div>
                                        {% endfor %}
                                    </div>
                                {% else %}
                                    <p class="text-muted mb-0 text-center">Порты не обнаружены.</p>
                                {% endif %}
                            </div>
                        </div>

                        <!-- 🔹 Service Inventory -->
                        {% if asset.service_inventory %}
                        <div class="card mt-4">
                            <div class="card-header"><i class="bi bi-hdd-network"></i> Сервисы</div>
                            <div class="card-body p-0">
                                <div class="list-group list-group-flush">
                                    {% for service in asset.service_inventory | sort(attribute='port') %}
                                        {% if service.is_active %}
                                        <div class="list-group-item">
                                            <div class="d-flex justify-content-between align-items-start">
                                                <div>
                                                    <h6 class="mb-1"><i class="bi bi-door-open"></i> {{ service.port }}</h6>
                                                    <p class="mb-1">
                                                        <strong>{{ service.service_name or 'unknown' }}</strong>
                                                        {% if service.product %}
                                                            <br><small class="text-muted">{{ service.product }} {{ service.version }}</small>
                                                        {% endif %}
                                                    </p>
                                                </div>
                                            </div>
                                            {% if service.script_output %}
                                                <button class="btn btn-sm btn-outline-secondary mt-2" type="button" data-bs-toggle="collapse" data-bs-target="#script-{{ service.id }}">
                                                    <i class="bi bi-terminal"></i> Скрипты
                                                </button>
                                                <div class="collapse" id="script-{{ service.id }}">
                                                    <div class="script-output"><pre class="small mb-0">{{ service.script_output }}</pre></div>
                                                </div>
                                            {% endif %}
                                        </div>
                                        {% endif %}
                                    {% endfor %}
                                </div>
                            </div>
                        </div>
                        {% endif %}
                    </div>

                    <!-- Tab: Инвентаризация -->
                    <div class="tab-pane fade" id="tab-inventory">
                        <div class="card {% if asset.osquery_status == 'online' %}border-success{% else %}border-secondary{% endif %}">
                            <div class="card-header d-flex justify-content-between align-items-center">
                                <span><i class="bi bi-hdd-stack"></i> Инвентаризация OSquery</span>
                                {% if asset.osquery_status == 'online' %}
                                    <span class="badge bg-success">🟢 Онлайн</span>
                                {% else %}
                                    <span class="badge bg-secondary">⚫ Оффлайн</span>
                                {% endif %}
                            </div>
                            <div class="card-body">
                                {% if asset.osquery_last_seen %}
                                    <div class="row g-3 mb-4">
                                        <div class="col-md-4">
                                            <div class="p-3 bg-light rounded">
                                                <small class="text-muted d-block">Процессор</small>
                                                <strong>{{ asset.osquery_cpu or 'Нет данных' }}</strong>
                                            </div>
                                        </div>
                                        <div class="col-md-4">
                                            <div class="p-3 bg-light rounded">
                                                <small class="text-muted d-block">ОЗУ</small>
                                                <strong>{{ asset.osquery_ram or 'Нет данных' }}</strong>
                                            </div>
                                        </div>
                                        <div class="col-md-4">
                                            <div class="p-3 bg-light rounded">
                                                <small class="text-muted d-block">Диск</small>
                                                <strong>{{ asset.osquery_disk or 'Нет данных' }}</strong>
                                            </div>
                                        </div>
                                    </div>
                                    <div class="row g-3">
                                        <div class="col-md-6">
                                            <div class="text-muted small">Операционная система</div>
                                            <div class="fw-medium">{{ asset.osquery_os or asset.os_info or 'Не определена' }}</div>
                                        </div>
                                        <div class="col-md-6">
                                            <div class="text-muted small">Ядро</div>
                                            <div class="fw-medium">{{ asset.osquery_kernel or 'Не определено' }}</div>
                                        </div>
                                        <div class="col-12 mt-2">
                                            <div class="text-muted small">Аптайм</div>
                                            <div class="fw-medium">
                                                {% if asset.osquery_uptime %}
                                                    {{ (asset.osquery_uptime // 86400) }} дн. 
                                                    {{ ((asset.osquery_uptime % 86400) // 3600) }} ч. 
                                                    {{ ((asset.osquery_uptime % 3600) // 60) }} м.
                                                {% else %}
                                                    Нет данных
                                                {% endif %}
                                            </div>
                                        </div>
                                        <div class="col-12 mt-2 text-end">
                                            <small class="text-muted">
                                                Последний отчет: {{ asset.osquery_last_seen.strftime('%Y-%m-%d %H:%M:%S') if asset.osquery_last_seen else '—' }}
                                            </small>
                                        </div>
                                    </div>
                                {% else %}
                                    <div class="text-center py-4">
                                        <i class="bi bi-hdd-network fs-1 text-muted mb-2"></i>
                                        <p class="text-muted">Агент OSquery не зарегистрирован или не отправлял данные.</p>
                                        <a href="{{ url_for('osquery.instructions_page') }}" class="btn btn-outline-success">
                                            <i class="bi bi-book"></i> Инструкция по установке
                                        </a>
                                    </div>
                                {% endif %}
                            </div>
                        </div>
                    </div>

                    <!-- Tab: Сканирования -->
                    <div class="tab-pane fade" id="tab-scans">
                        <div class="card">
                            <div class="card-header"><i class="bi bi-clipboard-data"></i> История сканирований</div>
                            <div class="card-body p-0">
                                <table class="table table-hover mb-0">
                                    <thead class="table-light">
                                        <tr>
                                            <th>Дата</th>
                                            <th>Тип</th>
                                            <th>Статус</th>
                                            <th>Действия</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {% if asset.scan_results %}
                                            {% for result in asset.scan_results | sort(attribute='scanned_at', reverse=true) %}
                                            <tr>
                                                <td>{{ result.scanned_at.strftime('%Y-%m-%d %H:%M') if result.scanned_at else '—' }}</td>
                                                <td>
                                                    {% if result.scan_job %}
                                                        <span class="badge bg-{{ 'danger' if result.scan_job.scan_type == 'rustscan' else 'info text-dark' }}">
                                                            {{ result.scan_job.scan_type.upper() }}
                                                        </span>
                                                    {% else %}
                                                        <span class="badge bg-secondary">—</span>
                                                    {% endif %}
                                                </td>
                                                <td>
                                                    {% if result.scan_job %}
                                                        <span class="badge bg-{{ 'success' if result.scan_job.status == 'completed' else 'warning text-dark' if result.scan_job.status == 'running' else 'danger' }}">
                                                            {{ result.scan_job.status }}
                                                        </span>
                                                    {% else %}
                                                        <span class="badge bg-success">completed</span>
                                                    {% endif %}
                                                </td>
                                                <td>
                                                    <button class="btn btn-sm btn-outline-primary" onclick="alert('Порты: {{ (result.ports | fromjson | join(', ')) if result.ports else 'Нет' }}\nОС: {{ result.os_detection or '—' }}')">
                                                        <i class="bi bi-eye"></i>
                                                    </button>
                                                </td>
                                            </tr>
                                            {% endfor %}
                                        {% else %}
                                            <tr>
                                                <td colspan="4" class="text-center py-4 text-muted">
                                                    <i class="bi bi-inbox fs-1 d-block mb-2"></i>
                                                    Нет результатов сканирований
                                                </td>
                                            </tr>
                                        {% endif %}
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
    <script src="{{ url_for('static', filename='js/main.js') }}" type="module"></script>
    <script>
        document.addEventListener('DOMContentLoaded', function() {
            // Инициализация темы
            if (typeof window.initTheme === 'function') window.initTheme();
            
            // Автопереключение на вкладку с ошибками если есть
            const urlParams = new URLSearchParams(window.location.search);
            if (urlParams.get('tab') === 'scans') {
                const scanTab = document.querySelector('[data-bs-target="#tab-scans"]');
                if (scanTab) new bootstrap.Tab(scanTab).show();
            }
        });
    </script>
</body>
</html>
```

### 📄 `templates/asset_history.html`

```html
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8"> <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>История - {{ asset.ip_address }}</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.10.0/font/bootstrap-icons.css" rel="stylesheet">
    <link href="{{ url_for('static', filename='css/style.css') }}" rel="stylesheet">
</head>
<body>
    <div class="container-fluid">
        <div class="row">
            <div class="col-md-3 col-lg-2 sidebar p-3 d-none d-md-block"><h5 class="mb-3"><i class="bi bi-folder-tree"></i> Группы</h5><div id="group-tree">{% include 'components/group_tree.html' %}</div></div>
            <div class="col-md-9 col-lg-10 p-4">
                <nav class="navbar navbar-light mb-4 px-3"><div class="d-flex align-items-center"><a href="{{ url_for('main.asset_detail', id=asset.id) }}" class="btn btn-outline-dark me-3"><i class="bi bi-arrow-left"></i> Назад</a><span class="navbar-brand mb-0 h1"><i class="bi bi-clock-history"></i> История: {{ asset.ip_address }}</span></div><button class="theme-toggle" onclick="toggleTheme()"><i class="bi bi-moon"></i><i class="bi bi-sun"></i></button></nav>
                <div class="row">
                    <div class="col-lg-8">
                        <div class="card mb-4"><div class="card-header"><i class="bi bi-activity"></i> Таймлайн <span class="badge bg-primary float-end">{{ changes|length }}</span></div>
                            <div class="card-body">{% if changes %}<div class="timeline">{% for c in changes %}<div class="timeline-item"><div class="timeline-marker">{{ c.changed_at.strftime('%Y-%m-%d %H:%M') }}</div><div class="timeline-dot"></div><div class="timeline-content"><div class="d-flex justify-content-between align-items-start mb-2"><h6 class="mb-0">{{ c.change_type }}</h6><span class="badge bg-secondary">{{ c.field_name or '-' }}</span></div>{% if c.old_value %}<div class="mb-1"><small class="text-muted">Было:</small><code>{{ c.old_value }}</code></div>{% endif %}{% if c.new_value %}<div class="mb-1"><small class="text-muted">Стало:</small><code>{{ c.new_value }}</code></div>{% endif %}{% if c.notes %}<div class="mt-2"><small class="text-muted"><i class="bi bi-chat-left-text"></i> {{ c.notes }}</small></div>{% endif %}</div></div>{% endfor %}</div>{% else %}<p class="text-muted text-center py-4">История пуста</p>{% endif %}</div></div>
                    </div>
                </div>
            </div>
        </div>
    </div>
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>

```

### 📄 `templates/asset_taxonomy.html`

```html
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Таксономия - {{ asset.ip_address }} | Asset Manager</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.10.0/font/bootstrap-icons.css" rel="stylesheet">
    <link href="{{ url_for('static', filename='css/style.css') }}" rel="stylesheet">
    <style>
        .taxon-card { transition: transform 0.2s ease, box-shadow 0.2s ease; }
        .taxon-card:hover { transform: translateY(-2px); box-shadow: var(--shadow-md) !important; }
        .taxon-icon { width: 48px; height: 48px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 1.25rem; }
        .taxon-icon.bg-primary-soft { background: rgba(13, 110, 253, 0.1); color: var(--bs-primary); }
        .taxon-icon.bg-info-soft { background: rgba(13, 202, 240, 0.1); color: var(--bs-info); }
        .taxon-icon.bg-success-soft { background: rgba(25, 135, 84, 0.1); color: var(--bs-success); }
        .taxon-icon.bg-warning-soft { background: rgba(255, 193, 7, 0.1); color: var(--bs-warning); }
        .taxon-children { border-left: 2px dashed var(--bs-border-color); padding-left: 1rem; margin-top: 0.5rem; }
        .taxon-child { display: flex; justify-content: space-between; padding: 0.25rem 0; font-size: 0.875rem; }
        .taxon-child-label { color: var(--text-secondary); }
        .taxon-child-value { font-weight: 500; }
        .tree-node { font-family: monospace; font-size: 0.875rem; }
        .tree-node i { width: 1.25rem; text-align: center; }
    </style>
</head>
<body>
    <div class="container-fluid">
        <div class="row">
            <!-- Sidebar -->
            <div class="col-md-3 col-lg-2 sidebar p-3 d-none d-md-block">
                <h5 class="mb-3"><i class="bi bi-folder-tree"></i> Группы</h5>
                {% include 'components/group_tree.html' %}
            </div>

            <!-- Main Content -->
            <div class="col-md-9 col-lg-10 p-4">
                <!-- Navigation -->
                <nav class="navbar navbar-light mb-4 px-3">
                    <div class="d-flex align-items-center">
                        <a href="{{ url_for('main.asset_detail', id=asset.id) }}" class="btn btn-outline-dark me-3">
                            <i class="bi bi-arrow-left"></i> Назад
                        </a>
                        <span class="navbar-brand mb-0 h1">
                            <i class="bi bi-diagram-3"></i> Таксономия: {{ asset.ip_address }}
                        </span>
                    </div>
                    <button class="theme-toggle" onclick="toggleTheme()" aria-label="Переключить тему">
                        <i class="bi bi-moon"></i><i class="bi bi-sun"></i>
                    </button>
                </nav>

                <!-- Info Card -->
                <div class="card mb-4">
                    <div class="card-header d-flex justify-content-between align-items-center">
                        <span><i class="bi bi-info-circle"></i> Актив</span>
                        <span class="text-muted small">{{ asset.ip_address }} {% if asset.hostname %}({{ asset.hostname }}){% endif %}</span>
                    </div>
                    <div class="card-body">
                        <p class="mb-0 text-muted">
                            Автоматическая классификация актива на основе открытых портов, сервисов, ОС и результатов сканирований.
                            Таксономия обновляется при каждом сканировании или получении данных от OSquery.
                        </p>
                    </div>
                </div>

                <!-- Taxonomy Cards -->
                <div class="row">
                    {% for node in taxonomy.nodes %}
                    <div class="col-lg-6 mb-4">
                        <div class="card taxon-card h-100 border-0 shadow-sm">
                            <div class="card-body">
                                <div class="d-flex align-items-center mb-3">
                                    <div class="taxon-icon taxon-icon.bg-{{ 'primary' if node.id == 'device' else 'info' if node.id == 'role' else 'success' if node.id == 'services' else 'warning' }}-soft me-3">
                                        <i class="bi {{ node.icon }}"></i>
                                    </div>
                                    <div>
                                        <small class="text-uppercase text-muted fw-bold">{{ node.title }}</small>
                                        <h5 class="mb-0 fw-semibold">{{ node.value }}</h5>
                                    </div>
                                </div>
                                
                                {% if node.children %}
                                <div class="taxon-children">
                                    {% for child in node.children %}
                                    <div class="taxon-child">
                                        <span class="taxon-child-label">{{ child.title }}</span>
                                        <span class="taxon-child-value">{{ child.value or '—' }}</span>
                                    </div>
                                    {% endfor %}
                                </div>
                                {% endif %}
                            </div>
                        </div>
                    </div>
                    {% endfor %}
                </div>

                <!-- Text Tree View -->
                <div class="card mt-3">
                    <div class="card-header"><i class="bi bi-git"></i> Дерево таксономии</div>
                    <div class="card-body">
                        <ul class="list-unstyled ps-3 mb-0 tree-view">
                            {% for node in taxonomy.nodes %}
                            <li class="{% if not loop.first %}mt-2{% endif %} tree-node">
                                <i class="bi {{ node.icon }} text-{{ 'primary' if node.id == 'device' else 'info' if node.id == 'role' else 'success' if node.id == 'services' else 'warning' }} me-2"></i>
                                <strong>{{ node.title }}:</strong> {{ node.value }}
                                {% if node.children %}
                                <ul class="list-unstyled ps-3 mt-1">
                                    {% for child in node.children %}
                                    <li><i class="bi bi-arrow-right-short me-1"></i>{{ child.title }}: <code>{{ child.value or '—' }}</code></li>
                                    {% endfor %}
                                </ul>
                                {% endif %}
                            </li>
                            {% endfor %}
                        </ul>
                    </div>
                </div>

                <!-- Debug Info (only in debug mode) -->
                {% if config.DEBUG %}
                <div class="card mt-3 border-warning">
                    <div class="card-header bg-warning text-dark"><i class="bi bi-bug"></i> Отладочная информация</div>
                    <div class="card-body small">
                        <pre class="mb-0">{{ taxonomy | tojson(indent=2) }}</pre>
                    </div>
                </div>
                {% endif %}
            </div>
        </div>
    </div>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
    <script src="{{ url_for('static', filename='js/main.js') }}" type="module"></script>
</body>
</html>
```

### 📄 `templates/base.html`

```html
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8"> 
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}Asset Manager{% endblock %}</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.10.0/font/bootstrap-icons.css" rel="stylesheet">
    <link href="{{ url_for('static', filename='css/style.css') }}" rel="stylesheet">
    {% block extra_css %}{% endblock %}
</head>
<body>
    {% block content %}{% endblock %}

    {% include 'components/modals.html' %}

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
    <script type="module" src="{{ url_for('static', filename='js/main.js') }}"></script>
    
    {% block extra_js %}{% endblock %}
    
    <script>
        document.addEventListener('DOMContentLoaded', () => {
            // Ждем загрузки модуля
            setTimeout(() => {
                if (typeof window.initTheme === 'function') window.initTheme();
                
                const activeScansEl = document.getElementById('active-scans');
                if (activeScansEl && typeof window.pollActiveScans === 'function') {
                    window.pollActiveScans();
                    setInterval(window.pollActiveScans, 5000);
                }
            }, 100);
        });
    </script>
</body>
</html>
```

### 📄 `templates/create.html`

```html
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Новый актив</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.10.0/font/bootstrap-icons.css" rel="stylesheet">
    <link href="{{ url_for('static', filename='css/style.css') }}" rel="stylesheet">
</head>
<body>
    <div class="container-fluid">
        <div class="row">
            <div class="col-md-3 col-lg-2 sidebar p-3 d-none d-md-block">
                <h5 class="mb-3"><i class="bi bi-folder-tree"></i> Группы</h5>
                <div id="group-tree">{% include 'components/group_tree.html' %}</div>
                <button class="btn btn-sm btn-outline-secondary w-100 mt-3" onclick="showCreateGroupModal(null)">
                    <i class="bi bi-plus-lg"></i> Корневая группа
                </button>
            </div>

            <div class="col-md-9 col-lg-10 p-4">
                <nav class="navbar navbar-light mb-4 px-3">
                    <div class="d-flex align-items-center">
                        <a href="{{ url_for('main.index') }}" class="btn btn-outline-dark me-3"><i class="bi bi-arrow-left"></i> Назад</a>
                        <span class="navbar-brand mb-0 h1"><i class="bi bi-plus-circle"></i> Новый актив</span>
                    </div>
                    <button class="theme-toggle" onclick="toggleTheme()"><i class="bi bi-moon"></i><i class="bi bi-sun"></i></button>
                </nav>

                <div class="card">
                    <div class="card-body">
                        <form method="POST" action="{{ url_for('main.index') }}">
                            <div class="mb-3">
                                <label class="form-label">IP Адрес *</label>
                                <input type="text" name="ip_address" class="form-control" required placeholder="192.168.1.1">
                            </div>
                            
                            <div class="mb-3">
                                <label class="form-label">Hostname</label>
                                <input type="text" name="hostname" class="form-control" placeholder="server01">
                            </div>
                            
                            <div class="mb-3">
                                <label class="form-label">ОС</label>
                                <input type="text" name="os_info" class="form-control" placeholder="Linux, Windows">
                            </div>
                            
                            <div class="mb-3">
                                <label class="form-label">Открытые порты</label>
                                <input type="text" name="open_ports" class="form-control" placeholder="22/tcp, 80/tcp">
                            </div>
                            
                            <div class="mb-3">
                                <label class="form-label">Группа</label>
                                <select name="group_id" class="form-select">
                                    <option value="">-- Без группы --</option>
                                    {% for g in all_groups %}
                                        <option value="{{ g.id }}">{{ g.name }}</option>
                                    {% endfor %}
                                </select>
                            </div>
                            
                            <div class="mb-3">
                                <label class="form-label">Заметки</label>
                                <textarea name="notes" class="form-control" rows="4" placeholder="Дополнительная информация..."></textarea>
                            </div>
                            
                            <div class="d-flex gap-2">
                                <button type="submit" class="btn btn-primary"><i class="bi bi-save"></i> Сохранить</button>
                                <a href="{{ url_for('main.index') }}" class="btn btn-secondary">Отмена</a>
                            </div>
                        </form>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
    <script src="{{ url_for('static', filename='js/main.js') }}" type="module"></script>
    <script>
        function initTheme() {
            const savedTheme = localStorage.getItem('theme') || 'light';
            document.documentElement.setAttribute('data-bs-theme', savedTheme === 'dark' ? 'dark' : 'light');
        }
        function toggleTheme() {
            const html = document.documentElement;
            const newTheme = html.getAttribute('data-bs-theme') === 'dark' ? 'light' : 'dark';
            html.setAttribute('data-bs-theme', newTheme);
            localStorage.setItem('theme', newTheme);
        }
        document.addEventListener('DOMContentLoaded', initTheme);
    </script>
</body>
</html>
```

### 📄 `templates/edit.html`

```html
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Редактировать актив</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.10.0/font/bootstrap-icons.css" rel="stylesheet">
    <link href="{{ url_for('static', filename='css/style.css') }}" rel="stylesheet">
</head>
<body>
    <div class="container-fluid">
        <div class="row">
            <div class="col-md-3 col-lg-2 sidebar p-3 d-none d-md-block">
                <h5 class="mb-3"><i class="bi bi-folder-tree"></i> Группы</h5>
                <div id="group-tree">{% include 'components/group_tree.html' %}</div>
                <button class="btn btn-sm btn-outline-secondary w-100 mt-3" onclick="showCreateGroupModal(null)">
                    <i class="bi bi-plus-lg"></i> Корневая группа
                </button>
            </div>

            <div class="col-md-9 col-lg-10 p-4">
                <nav class="navbar navbar-light mb-4 px-3">
                    <div class="d-flex align-items-center">
                        <a href="{{ url_for('main.index') }}" class="btn btn-outline-dark me-3"><i class="bi bi-arrow-left"></i> Назад</a>
                        <span class="navbar-brand mb-0 h1"><i class="bi bi-pencil"></i> Редактировать актив</span>
                    </div>
                    <button class="theme-toggle" onclick="toggleTheme()"><i class="bi bi-moon"></i><i class="bi bi-sun"></i></button>
                </nav>

                <div class="card">
                    <div class="card-body">
                        <form method="POST">
                            <div class="mb-3">
                                <label class="form-label">IP Адрес *</label>
                                <input type="text" name="ip_address" class="form-control" value="{{ asset.ip_address }}" required>
                            </div>
                            
                            <div class="mb-3">
                                <label class="form-label">Hostname</label>
                                <input type="text" name="hostname" class="form-control" value="{{ asset.hostname or '' }}">
                            </div>
                            
                            <div class="mb-3">
                                <label class="form-label">ОС</label>
                                <input type="text" name="os_info" class="form-control" value="{{ asset.os_info or '' }}">
                            </div>
                            
                            <div class="mb-3">
                                <label class="form-label">Открытые порты</label>
                                <input type="text" name="open_ports" class="form-control" value="{{ asset.open_ports or '' }}">
                            </div>
                            
                            <div class="mb-3">
                                <label class="form-label">Группа</label>
                                <select name="group_id" class="form-select">
                                    <option value="">-- Без группы --</option>
                                    {% for g in all_groups %}
                                        <option value="{{ g.id }}" {% if asset.group_id == g.id %}selected{% endif %}>
                                            {{ g.name }}
                                        </option>
                                    {% endfor %}
                                </select>
                            </div>
                            
                            <div class="mb-3">
                                <label class="form-label">Заметки</label>
                                <textarea name="notes" class="form-control" rows="4">{{ asset.notes or '' }}</textarea>
                            </div>
                            
                            <div class="d-flex gap-2">
                                <button type="submit" class="btn btn-primary"><i class="bi bi-save"></i> Сохранить</button>
                                <a href="{{ url_for('main.index') }}" class="btn btn-secondary">Отмена</a>
                            </div>
                        </form>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
    <script src="{{ url_for('static', filename='js/main.js') }}" type="module"></script>
    <script>
        function initTheme() {
            const savedTheme = localStorage.getItem('theme') || 'light';
            document.documentElement.setAttribute('data-bs-theme', savedTheme === 'dark' ? 'dark' : 'light');
        }
        function toggleTheme() {
            const html = document.documentElement;
            const newTheme = html.getAttribute('data-bs-theme') === 'dark' ? 'light' : 'dark';
            html.setAttribute('data-bs-theme', newTheme);
            localStorage.setItem('theme', newTheme);
        }
        document.addEventListener('DOMContentLoaded', initTheme);
    </script>
</body>
</html>
```

### 📄 `templates/index.html`

```html
{% extends "base.html" %}

{% block title %}Asset Manager{% endblock %}

{% block content %}
<div class="container-fluid">
    <div class="row">
        <!-- Боковая панель с деревом групп -->
        <div class="col-md-3 col-lg-2 sidebar p-3 d-none d-md-block">
            {% include 'components/group_tree.html' %}
        </div>

        <!-- Основной контент -->
        <div class="col-md-9 col-lg-10 p-4">
            <nav class="navbar navbar-light mb-4 px-3">
                <span class="navbar-brand mb-0 h1"><i class="bi bi-shield-check"></i> Asset Manager</span>
                <div class="d-flex align-items-center flex-wrap gap-2">
                    <button class="theme-toggle me-2" onclick="toggleTheme()" aria-label="Переключить тему">
                        <i class="bi bi-moon"></i><i class="bi bi-sun"></i>
                    </button>
                    <a href="{{ url_for('scans.scans_page') }}" class="btn btn-outline-dark me-2">
                        <i class="bi bi-wifi"></i> Сканирования
                    </a>
                    <button class="btn btn-primary me-2" data-bs-toggle="modal" data-bs-target="#scanModal">
                        <i class="bi bi-upload"></i> Импорт
                    </button>
                    <button class="btn btn-outline-dark me-2" data-bs-toggle="collapse" data-bs-target="#filterPanel">
                        <i class="bi bi-funnel"></i> Фильтры
                    </button>
                    <select id="data-source-filter" class="form-select form-select-sm" style="width: 160px;" aria-label="Фильтр по источнику">
                        <option value="all">Все источники</option>
                        <option value="wazuh">🛡️ Wazuh</option>
                        <option value="osquery">📦 OSquery</option>
                        <option value="scanning">🔍 Сканирование</option>
                        <option value="manual">✏️ Ручной</option>
                    </select>
                </div>
            </nav>

            <!-- Панель фильтров -->
            <div class="collapse mb-4" id="filterPanel">
                <div class="card card-body">
                    <div class="d-flex justify-content-between mb-3">
                        <h6 class="mb-0">Конструктор запросов</h6>
                        <div>
                            <button class="btn btn-sm btn-primary" onclick="applyFilters()">Применить</button>
                            <button class="btn btn-sm btn-secondary" onclick="resetFilters()">Сброс</button>
                        </div>
                    </div>
                    <div id="filter-root" class="filter-group"></div>
                </div>
            </div>

            <!-- Flash-сообщения -->
            {% with messages = get_flashed_messages(with_categories=true) %}
                {% if messages %}
                    {% for c, m in messages %}
                    <div class="alert alert-{{ c }} alert-dismissible fade show" role="alert">
                        {{ m }}
                        <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Закрыть"></button>
                    </div>
                    {% endfor %}
                {% endif %}
            {% endwith %}

            <!-- Таблица активов -->
            <div class="card">
                <div class="card-header d-flex justify-content-between align-items-center" id="bulk-toolbar" style="display: none;">
                    <div class="d-flex align-items-center gap-2">
                        <span class="badge bg-primary" id="selected-count">0</span>
                        <span class="text-muted small">выбрано</span>
                    </div>
                    <div class="d-flex gap-2">
                        <button class="btn btn-sm btn-outline-secondary" onclick="clearSelection()"><i class="bi bi-x-lg"></i> Снять</button>
                        <button class="btn btn-sm btn-danger" onclick="confirmBulkDelete()"><i class="bi bi-trash"></i> Удалить</button>
                    </div>
                </div>
                <div class="card-body p-0">
                    <table class="table table-hover mb-0">
                        <thead class="table-light">
                            <tr>
                                <th style="width:40px"><input type="checkbox" class="form-check-input" id="select-all"></th>
                                <th>IP</th>
                                <th>Hostname</th>
                                <th>OS</th>
                                <th>Порты</th>
                                <th>Группа</th>
                                <th>Действия</th>
                            </tr>
                        </thead>
                        <tbody id="assets-body">
                            {% include 'components/assets_rows.html' %}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    </div>
</div>

<!-- Модальные окна -->
{% include 'components/modals.html' %}
{% endblock %}

{% block extra_js %}
{% endblock %}
```

### 📄 `templates/osquery_config_editor.html`

```html
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8"> <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Редактор osquery</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.10.0/font/bootstrap-icons.css" rel="stylesheet">
    <link href="{{ url_for('static', filename='css/style.css') }}" rel="stylesheet">
</head>
<body>
    <div class="container-fluid p-4">
        <nav class="navbar navbar-light mb-4 px-3"><span class="navbar-brand mb-0 h1"><i class="bi bi-gear"></i> Редактор osquery.conf</span><button class="theme-toggle" onclick="toggleTheme()"><i class="bi bi-moon"></i><i class="bi bi-sun"></i></button></nav>
        <div class="row g-4">
            <div class="col-lg-8"><div class="card"><div class="card-header d-flex justify-content-between align-items-center"><span><i class="bi bi-filetype-json"></i> osquery.conf</span><div><button class="btn btn-sm btn-outline-secondary me-1" onclick="formatJSON()"><i class="bi bi-braces"></i> Формат</button><button class="btn btn-sm btn-warning me-1" onclick="validateConfig()"><i class="bi bi-shield-check"></i> Валидация</button><button class="btn btn-sm btn-success" onclick="saveConfig()"><i class="bi bi-save"></i> Сохранить</button></div></div><div class="card-body p-0"><textarea id="config-editor" class="form-control font-monospace" style="height:500px;border:0" spellcheck="false"></textarea></div></div></div>
            <div class="col-lg-4"><div class="card mb-3"><div class="card-header bg-info text-white">📊 Результат валидации</div><div class="card-body" id="validation-results"><p class="text-muted">Нажмите "Валидация" для проверки.</p></div></div></div>
        </div>
    </div>
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
    <script>
        async function loadConfig(){try{const r=await fetch('/osquery/api/config');if(!r.ok)throw new Error('Ошибка');document.getElementById('config-editor').value=JSON.stringify(await r.json(),null,2);}catch(e){alert('❌ '+e.message);}}
        function formatJSON(){try{document.getElementById('config-editor').value=JSON.stringify(JSON.parse(document.getElementById('config-editor').value),null,2);}catch(e){alert('JSON ошибка');}}
        async function validateConfig(){const d=document.getElementById('validation-results');d.innerHTML='<div class="spinner-border spinner-border-sm"></div> Проверка...';try{const r=await fetch('/osquery/api/config/validate',{method:'POST',headers:{'Content-Type':'application/json'},body:document.getElementById('config-editor').value});const res=await r.json();let h=res.errors.map(e=>`<div class="text-danger">❌ ${e}</div>`).join('')+res.warnings.map(w=>`<div class="text-warning">⚠️ ${w}</div>`).join('');if(!h)h='<div class="text-success">✅ Валидно</div>';d.innerHTML=h;}catch(e){d.innerHTML=`<div class="text-danger">❌ ${e.message}</div>`;}}
        async function saveConfig(){try{const r=await fetch('/osquery/api/config',{method:'POST',headers:{'Content-Type':'application/json'},body:document.getElementById('config-editor').value});const d=await r.json();if(r.ok)alert('✅ '+d.message);else alert('❌ '+d.error);}catch(e){alert('❌ '+e.message);}}
        document.addEventListener('DOMContentLoaded', loadConfig);
    </script>
</body>
</html>

```

### 📄 `templates/osquery_dashboard.html`

```html
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8"> <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>OSquery Управление</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.10.0/font/bootstrap-icons.css" rel="stylesheet">
    <link href="{{ url_for('static', filename='css/style.css') }}" rel="stylesheet">
</head>
<body>
    <div class="container-fluid p-4">
        <nav class="navbar navbar-light mb-4 px-3"><span class="navbar-brand mb-0 h1"><i class="bi bi-hdd-network"></i> OSquery Агенты</span><div class="d-flex align-items-center"><button class="theme-toggle me-2" onclick="toggleTheme()"><i class="bi bi-moon"></i><i class="bi bi-sun"></i></button><a href="{{ url_for('main.index') }}" class="btn btn-outline-dark"><i class="bi bi-arrow-left"></i> На главную</a><a href="{{ url_for('osquery.deploy_page') }}" class="btn btn-outline-primary"><i class="bi bi-rocket-takeoff"></i> Деплой</a><a href="{{ url_for('osquery.config_editor') }}" class="btn btn-outline-secondary"><i class="bi bi-gear"></i> Конфиг</a></div></nav>
        <div class="row">{% for asset in assets %}<div class="col-md-4 mb-3"><div class="card border-{{ 'success' if asset.osquery_status=='online' else 'secondary' }}"><div class="card-body"><h5 class="card-title">{{ asset.ip_address }}</h5><p class="card-text small"><strong>Статус:</strong> {{ asset.osquery_status }}<br><strong>Версия:</strong> {{ asset.osquery_version or '-' }}<br><strong>Последний отчет:</strong> {{ asset.osquery_last_seen.strftime('%Y-%m-%d %H:%M') if asset.osquery_last_seen else '-' }}<br><strong>Node Key:</strong> <code>{{ asset.osquery_node_key }}</code></p><a href="{{ url_for('main.asset_detail', id=asset.id) }}" class="btn btn-sm btn-outline-primary">Перейти к активу</a></div></div></div>{% else %}<div class="col-12 text-center text-muted py-5"><i class="bi bi-hdd-network fs-1 d-block mb-2"></i>Нет зарегистрированных агентов OSquery</div>{% endfor %}</div>
    </div>
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>

```

### 📄 `templates/osquery_deploy.html`

```html
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8"> <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Деплой OSquery</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.10.0/font/bootstrap-icons.css" rel="stylesheet">
    <link href="{{ url_for('static', filename='css/style.css') }}" rel="stylesheet">
</head>
<body>
    <div class="container-fluid p-4">
        <nav class="navbar navbar-light mb-4 px-3"><span class="navbar-brand mb-0 h1"><i class="bi bi-rocket-takeoff"></i> Деплой агентов</span><button class="theme-toggle" onclick="toggleTheme()"><i class="bi bi-moon"></i><i class="bi bi-sun"></i></button></nav>
        <div class="card mb-4"><div class="card-header">📜 Ansible Плейбук</div><div class="card-body"><p>Скачайте плейбук и инвентарь, запустите: <code>ansible-playbook -i inventory.ini ansible/deploy_osquery.yml</code></p><a href="/osquery/instructions" class="btn btn-outline-secondary">📖 Инструкция по установке</a></div></div>
        <div class="card"><div class="card-header">🌐 Генератор inventory.ini</div><div class="card-body"><form id="inventory-form"><div class="mb-3"><label>IP-адреса (через запятую)</label><input type="text" id="ips" class="form-control" placeholder="192.168.1.10, 10.0.0.5"></div><button type="button" class="btn btn-primary" onclick="downloadInventory()">Скачать inventory.ini</button></form></div></div>
    </div>
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
    <script>function downloadInventory(){const i=document.getElementById('ips').value.trim();if(!i)return alert('Введите IP-адреса');const b=new Blob([`[osquery_agents]\n${i.split(',').map(x=>x.trim()).join('\n')}`],{type:'text/plain'});const u=URL.createObjectURL(b);const a=document.createElement('a');a.href=u;a.download='inventory.ini';a.click();}</script>
</body>
</html>

```

### 📄 `templates/osquery_instructions.html`

```html
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8"> <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Инструкции OSquery</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.10.0/font/bootstrap-icons.css" rel="stylesheet">
    <link href="{{ url_for('static', filename='css/style.css') }}" rel="stylesheet">
</head>
<body>
    <div class="container-fluid p-4">
        <nav class="navbar navbar-light mb-4 px-3"><span class="navbar-brand mb-0 h1"><i class="bi bi-book"></i> Установка OSquery</span><button class="theme-toggle" onclick="toggleTheme()"><i class="bi bi-moon"></i><i class="bi bi-sun"></i></button></nav>
        <div class="accordion" id="installAccordion">
            <div class="accordion-item"><h2 class="accordion-header"><button class="accordion-button" type="button" data-bs-toggle="collapse" data-bs-target="#linux-inst">🐧 Linux</button></h2><div id="linux-inst" class="accordion-collapse collapse show" data-bs-parent="#installAccordion"><div class="accordion-body"><pre class="bg-light p-2">sudo apt update && sudo apt install osquery -y</pre><p>Скопируйте <code>osquery.conf</code> в <code>/etc/osquery/</code>. Запустите: <code>sudo systemctl enable --now osqueryd</code></p></div></div></div>
            <div class="accordion-item"><h2 class="accordion-header"><button class="accordion-button collapsed" type="button" data-bs-toggle="collapse" data-bs-target="#win-inst">🪟 Windows</button></h2><div id="win-inst" class="accordion-collapse collapse" data-bs-parent="#installAccordion"><div class="accordion-body"><p>Скачайте MSI: <code>https://pkg.osquery.io/windows/osquery.msi</code><br>Установка: <code>msiexec /i osquery.msi /qn</code>. Конфиг в <code>C:\ProgramData\osquery\osquery.conf</code>. Запуск: <code>sc start osqueryd</code></p></div></div></div>
        </div>
    </div>
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>

```

### 📄 `templates/scans.html`

```html
{% extends "base.html" %}

{% block title %}Сканирования | Asset Manager{% endblock %}

{% block content %}
<div class="container-fluid py-4">
    <div class="row">
        <!-- Sidebar (Группы) -->
        <div class="col-md-3 col-lg-2 d-none d-md-block">
            <div class="sticky-top" style="top: 20px;">
                {% include 'components/group_tree.html' %}
            </div>
        </div>

        <!-- Main Content -->
        <div class="col-md-9 col-lg-10">
            <nav class="navbar navbar-light mb-4 px-0">
                <span class="navbar-brand mb-0 h1"><i class="bi bi-wifi"></i> Сканирования</span>
                <div class="d-flex align-items-center">
                    <button class="theme-toggle me-2" onclick="toggleTheme()" aria-label="Переключить тему">
                        <i class="bi bi-moon"></i><i class="bi bi-sun"></i>
                    </button>
                    <a href="{{ url_for('main.index') }}" class="btn btn-outline-dark btn-sm"><i class="bi bi-arrow-left"></i> На главную</a>
                </div>
            </nav>

            <!-- Flash Messages -->
            {% with messages = get_flashed_messages(with_categories=true) %}
                {% if messages %}
                    {% for c, m in messages %}
                    <div class="alert alert-{{ c }} alert-dismissible fade show" role="alert">
                        {{ m }}
                        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
                    </div>
                    {% endfor %}
                {% endif %}
            {% endwith %}

            <!-- Scan Form -->
            <div class="card mb-4 shadow-sm">
                <div class="card-header bg-primary text-white"><i class="bi bi-plus-circle"></i> Новое сканирование</div>
                <div class="card-body">
                    <form id="scanForm">
                        <div class="row mb-3">
                            <div class="col-md-6">
                                <label class="form-label">Тип сканирования</label>
                                <select id="scan-type" class="form-select" onchange="toggleScanOptions()">
                                    <option value="rustscan">🚀 Rustscan (Быстрый)</option>
                                    <option value="nmap">🔍 Nmap (Глубокий)</option>
                                    <option value="nslookup">🌐 Nslookup (DNS)</option>
                                </select>
                            </div>
                            <div class="col-md-6">
                                <label class="form-label">Метод выбора цели</label>
                                <select id="target-method" class="form-select" onchange="toggleTargetInput()">
                                    <option value="ip">IP / CIDR</option>
                                    <option value="group">Группа активов</option>
                                    <option value="text">Список доменов</option>
                                </select>
                            </div>
                        </div>
                        
                        <!-- Цели -->
                        <div class="mb-3" id="target-ip-section">
                            <label class="form-label">Цель (IP или диапазон)</label>
                            <input type="text" id="scan-target" class="form-control" placeholder="192.168.1.0/24">
                        </div>
                        <div class="mb-3" id="target-group-section" style="display: none;">
                            <label class="form-label">Группа активов</label>
                            <select id="scan-group" class="form-select">
                                <option value="">-- Выберите группу --</option>
                                <option value="ungrouped">📂 Без группы</option>
                                {% for g in all_groups %}<option value="{{ g.id }}">{{ g.name }}</option>{% endfor %}
                            </select>
                        </div>
                        <div class="mb-3" id="target-text-section" style="display: none;">
                            <label class="form-label">Список доменов (каждый с новой строки)</label>
                            <textarea id="scan-target-text" class="form-control" rows="4" placeholder="example.com&#10;google.com"></textarea>
                        </div>
                        
                        <!-- Доп. настройки -->
                        <div class="mb-3" id="dns-server-section" style="display: none;">
                            <label class="form-label">DNS-сервер</label>
                            <input type="text" id="scan-dns-server" class="form-control" value="77.88.8.8">
                        </div>
                        <div class="mb-3" id="ports-section" style="display: none;">
                            <label class="form-label">Порты</label>
                            <input type="text" id="scan-ports" class="form-control" placeholder="22,80,443 или 1-1000">
                        </div>
                        <div class="mb-3" id="nslookup-args-section" style="display: none;">
                            <label class="form-label">Аргументы nslookup</label>
                            <input type="text" id="scan-nslookup-args" class="form-control" placeholder="-querytype=A">
                        </div>
                        <div class="mb-3">
                            <label class="form-label"><i class="bi bi-sliders"></i> Кастомные аргументы</label>
                            <input type="text" id="scan-custom-args" class="form-control" placeholder="--batch-size 500">
                        </div>
                        
                        <div class="d-grid gap-2 d-md-flex justify-content-md-end">
                            <button type="button" class="btn btn-secondary" onclick="resetScanForm()"><i class="bi bi-arrow-counterclockwise"></i> Сброс</button>
                            <button type="submit" class="btn btn-primary"><i class="bi bi-play-fill"></i> Запустить</button>
                        </div>
                    </form>
                </div>
            </div>

            <!-- Активные сканирования (Основной блок) -->
            <div class="card mb-4 shadow-sm border-warning">
                <div class="card-header bg-warning text-dark d-flex justify-content-between align-items-center">
                    <h5 class="mb-0"><i class="bi bi-activity"></i> Активные сканирования</h5>
                    <button class="btn btn-sm btn-light" onclick="pollActiveScans()"><i class="bi bi-arrow-clockwise"></i></button>
                </div>
                <div class="card-body" id="active-scans">
                    <p class="text-muted mb-0 text-center"><i class="bi bi-check-circle"></i> Нет активных сканирований</p>
                </div>
            </div>

            <!-- История -->
            <div class="card shadow-sm">
                <div class="card-header bg-secondary text-white d-flex justify-content-between align-items-center">
                    <h5 class="mb-0"><i class="bi bi-clock-history"></i> История сканирований</h5>
                    <button class="btn btn-sm btn-light" onclick="updateScanHistory()"><i class="bi bi-arrow-clockwise"></i></button>
                </div>
                <div class="card-body p-0">
                    <div class="table-responsive">
                        <table class="table table-hover table-sm mb-0" id="history-table">
                            <thead class="table-light">
                                <tr>
                                    <th>ID</th>
                                    <th>Тип</th>
                                    <th>Цель</th>
                                    <th>Статус</th>
                                    <th>Прогресс</th>
                                    <th>Начало</th>
                                    <th>Действия</th>
                                </tr>
                            </thead>
                            <tbody>
                                {% for job in scan_jobs %}
                                <tr id="scan-row-{{ job.id }}">
                                    <td>{{ job.id }}</td>
                                    <td><span class="badge bg-{{ 'danger' if job.scan_type=='rustscan' else 'info text-dark' }}">{{ job.scan_type.upper() }}</span></td>
                                    <td><code>{{ job.target }}</code></td>
                                    <td>
                                        <span class="badge bg-{{ 'warning text-dark' if job.status=='running' else 'success' if job.status=='completed' else 'danger' }} status-badge"
                                              {% if job.error_message %}data-bs-toggle="tooltip" title="{{ job.error_message | replace('\n', ' ') | replace('"', '&quot;') }}"{% endif %}>
                                            {{ job.status }}
                                        </span>
                                    </td>
                                    <td>
                                        <div class="progress" style="width:80px"><div class="progress-bar" style="width:{{ job.progress }}%"></div></div>
                                        <small>{{ job.progress }}%</small>
                                    </td>
                                    <td>{{ job.started_at.strftime('%H:%M:%S') if job.started_at else '-' }}</td>
                                    <td>
                                        {% if job.status=='pending' %}
                                            <!-- Кнопка удаления для Pending -->
                                            <button class="btn btn-sm btn-outline-danger" onclick="controlScan('{{ job.id }}', 'delete')" title="Удалить"><i class="bi bi-trash"></i></button>
                                        
                                        {% elif job.status=='running' %}
                                            <!-- УДАЛЕНО: Кнопка Pause -->
                                            <button class="btn btn-sm btn-outline-danger" onclick="controlScan('{{ job.id }}', 'stop')" title="Остановить"><i class="bi bi-stop-fill"></i></button>
                                            <button class="btn btn-sm btn-outline-success" onclick="controlScan('{{ job.id }}', 'rerun')" title="Повторить"><i class="bi bi-arrow-clockwise"></i></button>
                                        
                                        {% elif job.status in ['completed','failed','stopped'] %}
                                            <button class="btn btn-sm btn-outline-danger" onclick="controlScan('{{ job.id }}', 'delete')" title="Удалить"><i class="bi bi-trash"></i></button>
                                            <button class="btn btn-sm btn-outline-success" onclick="controlScan('{{ job.id }}', 'rerun')" title="Повторить"><i class="bi bi-arrow-clockwise"></i></button>
                                        {% endif %}
                                        
                                        {% if job.status!='pending' %}
                                            <button class="btn btn-sm btn-outline-info" onclick="viewScanResults('{{ job.id }}')" title="Результаты"><i class="bi bi-eye"></i></button>
                                        {% endif %}
                                    </td>
                                </tr>
                                {% else %}
                                <tr><td colspan="7" class="text-center py-4 text-muted">Нет сканирований</td></tr>
                                {% endfor %}
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>
        </div>
    </div>
</div>

<!-- Modals -->
<div class="modal fade" id="scanResultsModal" tabindex="-1">
    <div class="modal-dialog modal-lg">
        <div class="modal-content">
            <div class="modal-header"><h5 class="modal-title">Результаты</h5><button type="button" class="btn-close" data-bs-dismiss="modal"></button></div>
            <div class="modal-body"><div id="scan-results-content"></div></div>
            <div class="modal-footer"><button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Закрыть</button></div>
        </div>
    </div>
</div>

<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
<script src="{{ url_for('static', filename='js/main.js') }}" type="module"></script>
<script>
    // === УПРАВЛЕНИЕ ФОРМОЙ ===
    function toggleTargetInput(){
        const m = document.getElementById('target-method').value;
        document.getElementById('target-ip-section').style.display = (m === 'text' || m === 'group') ? 'none' : 'block';
        document.getElementById('target-group-section').style.display = (m === 'group') ? 'block' : 'none';
        document.getElementById('target-text-section').style.display = (m === 'text') ? 'block' : 'none';
    }

    function toggleScanOptions(){
        const t = document.getElementById('scan-type').value;
        const portsSec = document.getElementById('ports-section');
        const dnsSec = document.getElementById('dns-server-section');
        const nsArgsSec = document.getElementById('nslookup-args-section');
        const targetMethod = document.getElementById('target-method');

        portsSec.style.display = (t === 'nmap' || t === 'rustscan') ? 'block' : 'none';
        dnsSec.style.display = (t === 'nslookup') ? 'block' : 'none';
        nsArgsSec.style.display = (t === 'nslookup') ? 'block' : 'none';

        // Автоматическое переключение на "Список доменов" для nslookup
        if(t === 'nslookup'){
            targetMethod.value = 'text';
            toggleTargetInput();
        }
    }

    function resetScanForm(){
        document.getElementById('scanForm').reset();
        toggleTargetInput(); 
        toggleScanOptions();
    }

    // === ЗАПУСК СКАНИРОВАНИЯ ===
    document.getElementById('scanForm').addEventListener('submit', async e => {
        e.preventDefault();
        const t = document.getElementById('scan-type').value;
        const m = document.getElementById('target-method').value;
        
        let url = '';
        let payload = {};

        if(t === 'nslookup'){
            const targetText = document.getElementById('scan-target-text').value;
            if(!targetText || !targetText.trim()){
                alert('⚠️ Введите список доменов');
                return;
            }
            url = '/api/scans/nslookup';
            payload = {
                targets: targetText,
                dns_server: document.getElementById('scan-dns-server').value || '77.88.8.8',
                nslookup_args: document.getElementById('scan-nslookup-args').value || ''
            };
        } else {
            // Rustscan или Nmap
            let targetVal = null;
            if(m === 'ip') targetVal = document.getElementById('scan-target').value;
            else if(m === 'group') targetVal = 'group:' + document.getElementById('scan-group').value;
            
            if(!targetVal){
                alert('⚠️ Укажите цель');
                return;
            }

            if(t === 'rustscan') url = '/api/scans/rustscan';
            else if(t === 'nmap') url = '/api/scans/nmap';

            payload = {
                target: targetVal,
                ports: document.getElementById('scan-ports').value || '-',
                extra_args: document.getElementById('scan-custom-args').value || ''
            };
            if(t === 'nmap') payload.scripts = document.getElementById('scan-ports').value; // Упрощено
        }

        try{
            const res = await fetch(url, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(payload)
            });
            const d = await res.json();
            if(res.ok){ 
                alert(`✅ ${d.message || 'Запущено'}`); 
                location.reload(); 
            } else {
                alert(`❌ ${d.error}`);
            }
        } catch(err){ 
            alert(`❌ Ошибка сети: ${err.message}`); 
        }
    });

    // === ПРОСМОТР РЕЗУЛЬТАТОВ ===
    async function viewScanResults(id){
        const m = new bootstrap.Modal(document.getElementById('scanResultsModal'));
        const c = document.getElementById('scan-results-content');
        c.innerHTML = '<div class="text-center"><div class="spinner-border"></div><p class="mt-2">Загрузка...</p></div>';
        m.show();
        
        try{
            const r = await fetch(`/api/scans/${id}/results`);
            const d = await r.json();
            
            let h = `<h6>#${d.job.id} - ${d.job.scan_type.toUpperCase()}</h6>`;
            h += `<p><strong>Цель:</strong> ${d.job.target}</p>`;
            h += `<p><strong>Статус:</strong> <span class="badge bg-${d.job.status==='completed'?'success':'danger'}">${d.job.status}</span></p>`;
            
            if(d.job.error_message){
                h += `<div class="alert alert-danger"><pre class="mb-0">${d.job.error_message}</pre></div>`;
            }

            if(d.job.scan_type === 'nslookup' && d.job.nslookup_output){
                h += `<pre class="bg-light p-3 border rounded" style="max-height:400px;overflow:auto;">${d.job.nslookup_output.replace(/</g,'&lt;').replace(/>/g,'&gt;')}</pre>`;
            } else if(d.results && d.results.length > 0) {
                h += `<p><strong>Найдено хостов:</strong> ${d.results.length}</p>`;
                h += `<ul class="list-group">`;
                d.results.forEach(x => {
                    h += `<li class="list-group-item"><strong>${x.ip}</strong> ${x.domain ? '('+x.domain+')' : ''}</li>`;
                });
                h += `</ul>`;
            } else {
                h += '<p class="text-muted">Нет деталей результатов</p>';
            }
            
            c.innerHTML = h;
        } catch(err){ 
            c.innerHTML = `<div class="alert alert-danger">❌ ${err.message}</div>`; 
        }
    }

    // === УПРАВЛЕНИЕ ЗАДАНИЯМИ (Удаление, Стоп, Реран) ===
    async function controlScan(id, action){
        if(action === 'delete' && !confirm('Удалить запись о сканировании?')) return;
        if(action === 'stop' && !confirm('Остановить сканирование?')) return;
        if(action === 'rerun' && !confirm('Повторить сканирование?')) return;

        try{
            let url, method, body;
            
            if(action === 'delete'){
                url = `/api/scans/${id}`;
                method = 'DELETE';
                body = null;
            } else {
                url = `/api/scans/${id}/control`;
                method = 'POST';
                body = JSON.stringify({action: action});
            }

            const r = await fetch(url, {
                method: method,
                headers: {'Content-Type': 'application/json'},
                body: body
            });
            
            const d = await r.json();
            if(r.ok){
                if(action === 'delete'){
                    const row = document.getElementById(`scan-row-${id}`);
                    if(row) row.remove();
                    if (typeof window.pollActiveScans === 'function') { window.pollActiveScans(); }
                } else {
                    location.reload();
                }
            } else {
                alert(`❌ ${d.error}`);
            }
        } catch(err){ 
            alert(`❌ Ошибка: ${err.message}`); 
        }
    }

    // === ПОЛЛИНГ АКТИВНЫХ (Обновляет и основной блок, и сайдбар) ===
    function pollActiveScans(){
        fetch('/api/scans/status')
        .then(r => r.json())
        .then(d => {
            const mainContainer = document.getElementById('active-scans');
            const sidebarContainer = document.getElementById('sidebar-active-scans');
            
            if(!mainContainer) return;

            if(d.active && d.active.length > 0){
                let html = '<div class="row g-2">';
                d.active.forEach(j => {
                    const badgeClass = j.status === 'running' ? 'bg-warning text-dark' : 'bg-info';
                    const progressClass = j.status === 'running' ? 'progress-bar-striped progress-bar-animated' : '';
                    
                    const cardHtml = `
                        <div class="col-md-6 col-lg-12">
                            <div class="card border-${j.status==='running'?'warning':'info'} h-100">
                                <div class="card-body p-2">
                                    <div class="d-flex justify-content-between align-items-center mb-1">
                                        <small class="fw-bold">${j.scan_type.toUpperCase()}</small>
                                        <span class="badge ${badgeClass}">${j.status}</span>
                                    </div>
                                    <div class="progress mb-1" style="height: 6px;">
                                        <div class="progress-bar ${progressClass}" style="width: ${j.progress}%"></div>
                                    </div>
                                    <small class="text-truncate d-block" title="${j.target}">${j.target}</small>
                                    <small class="text-muted">${j.progress}%</small>
                                </div>
                            </div>
                        </div>
                    `;
                    html += cardHtml;
                });
                html += '</div>';
                
                mainContainer.innerHTML = html;
                if(sidebarContainer) sidebarContainer.innerHTML = html;
            } else {
                const emptyMsg = '<p class="text-muted mb-0 text-center"><i class="bi bi-check-circle"></i> Нет активных сканирований</p>';
                mainContainer.innerHTML = emptyMsg;
                if(sidebarContainer) sidebarContainer.innerHTML = emptyMsg;
            }
        })
        .catch(e => console.warn('Poll error:', e));
    }

    // === ОБНОВЛЕНИЕ ИСТОРИИ (Частичное) ===
    async function updateScanHistory(){
        try{
            const res = await fetch('/api/scans/history');
            if(!res.ok) return;
            const jobs = await res.json();
            
            jobs.forEach(j => {
                const row = document.getElementById(`scan-row-${j.id}`);
                if(row){
                    const badge = row.querySelector('.status-badge');
                    if(badge && badge.textContent !== j.status){
                        badge.textContent = j.status;
                        badge.className = `badge status-badge bg-${j.status==='running'?'warning text-dark':j.status==='completed'?'success':'danger'}`;
                        if(j.error_message){
                            badge.setAttribute('data-bs-toggle', 'tooltip');
                            badge.setAttribute('title', j.error_message);
                        }
                    }
                    const bar = row.querySelector('.progress-bar');
                    const txt = row.querySelector('small'); 
                    if(bar) bar.style.width = `${j.progress}%`;
                    if(txt && txt.textContent.includes('%')) txt.textContent = `${j.progress}%`;
                }
            });
        } catch(e){ console.warn('History update error', e); }
    }

    // === ИНИЦИАЛИЗАЦИЯ ===
    document.addEventListener('DOMContentLoaded', () => {
        toggleTargetInput(); 
        toggleScanOptions();
        
 if (typeof window.pollActiveScans === 'function') { window.pollActiveScans(); }
        setInterval(window.pollActiveScans, 3000);

        if (typeof window.updateScanHistory === 'function') { window.updateScanHistory(); }
        setInterval(window.updateScanHistory, 5000);
    });
</script>
{% endblock %}
```

### 📄 `templates/utilities.html`

```html
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8"> <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Утилиты</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.10.0/font/bootstrap-icons.css" rel="stylesheet">
    <link href="{{ url_for('static', filename='css/style.css') }}" rel="stylesheet">
</head>
<body>
    <div class="container-fluid">
        <div class="row">
            <div class="col-md-3 col-lg-2 sidebar p-3 d-none d-md-block"><h5 class="mb-3"><i class="bi bi-folder-tree"></i> Группы</h5><div id="group-tree">{% include 'components/group_tree.html' %}</div></div>
            <div class="col-md-9 col-lg-10 p-4">
                <nav class="navbar navbar-light mb-4 px-3"><span class="navbar-brand mb-0 h1"><i class="bi bi-tools"></i> Утилиты</span><div class="d-flex align-items-center"><button class="theme-toggle me-2" onclick="toggleTheme()"><i class="bi bi-moon"></i><i class="bi bi-sun"></i></button><a href="{{ url_for('main.index') }}" class="btn btn-outline-dark"><i class="bi bi-arrow-left"></i> На главную</a></div></nav>
                <div class="row">
                    <div class="col-md-6 col-lg-4 mb-4"><div class="card h-100" data-bs-toggle="modal" data-bs-target="#nmapRustscanModal" style="cursor: pointer;"><div class="card-body text-center p-4"><i class="bi bi-lightning-charge display-4 text-primary mb-3"></i><h5>Nmap → Rustscan</h5><p class="text-muted">Конвертация XML в список IP</p></div></div></div>
                    <div class="col-md-6 col-lg-4 mb-4"><div class="card h-100" data-bs-toggle="modal" data-bs-target="#extractPortsModal" style="cursor: pointer;"><div class="card-body text-center p-4"><i class="bi bi-door-open display-4 text-info mb-3"></i><h5>Извлечь порты</h5><p class="text-muted">Извлечение портов из Nmap XML</p></div></div></div>
                </div>
            </div>
        </div>
    </div>
    <div class="modal fade" id="nmapRustscanModal" tabindex="-1"><div class="modal-dialog"><div class="modal-content"><form id="nmapRustscanForm" enctype="multipart/form-data"><div class="modal-header"><h5>Nmap → Rustscan</h5><button type="button" class="btn-close" data-bs-dismiss="modal"></button></div><div class="modal-body"><div class="mb-3"><label>XML файл</label><input type="file" name="file" class="form-control" accept=".xml" required></div><div id="nmapRustscanResult" class="mt-3"></div></div><div class="modal-footer"><button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Отмена</button><button type="submit" class="btn btn-primary"><i class="bi bi-download"></i> Скачать</button></div></form></div></div></div>
    <div class="modal fade" id="extractPortsModal" tabindex="-1"><div class="modal-dialog"><div class="modal-content"><form id="extractPortsForm" enctype="multipart/form-data"><div class="modal-header"><h5>Извлечь порты</h5><button type="button" class="btn-close" data-bs-dismiss="modal"></button></div><div class="modal-body"><div class="mb-3"><label>XML файл</label><input type="file" name="file" class="form-control" accept=".xml" required></div><div id="extractPortsResult" class="mt-3"></div></div><div class="modal-footer"><button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Отмена</button><button type="submit" class="btn btn-primary"><i class="bi bi-download"></i> Скачать</button></div></form></div></div></div>
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
    <script>
        function handleUpload(formId, resId, url){document.getElementById(formId).addEventListener('submit', async e=>{e.preventDefault();const f=e.target;const fd=new FormData(f);const r=document.getElementById(resId);r.innerHTML='<div class="text-center"><div class="spinner-border"></div></div>';try{const res=await fetch(url,{method:'POST',body:fd});if(res.ok){const blob=await res.blob();const u=window.URL.createObjectURL(blob);const a=document.createElement('a');a.href=u;a.download=res.headers.get('Content-Disposition').split('filename=')[1];document.body.appendChild(a);a.click();r.innerHTML='<div class="alert alert-success">Готово!</div>';setTimeout(()=>{bootstrap.Modal.getInstance(document.getElementById(formId.replace('Form','Modal'))).hide();r.innerHTML='';f.reset();},2000);}else{const err=await res.json();r.innerHTML=`<div class="alert alert-danger">${err.error}</div>`;}}catch(err){r.innerHTML=`<div class="alert alert-danger">${err.message}</div>`;}});}
        handleUpload('nmapRustscanForm','nmapRustscanResult','/utilities/nmap-to-rustscan');
        handleUpload('extractPortsForm','extractPortsResult','/utilities/extract-ports');
    </script>
</body>
</html>

```

### 📄 `templates/components/assets_rows.html`

```html
{% for asset in assets %}
<tr data-asset-id="{{ asset.id }}" class="asset-row">
    <td><input type="checkbox" class="form-check-input asset-checkbox" value="{{ asset.id }}"></td>
    <td><a href="/asset/{{ asset.id }}" class="text-decoration-none"><strong>{{ asset.ip_address }}</strong></a></td>
    <td>{{ asset.hostname or '—' }}</td>
    <td><span class="text-muted small">{{ asset.os_info or '—' }}</span></td>
    <td><small class="text-muted">{{ asset.open_ports or '—' }}</small></td>
    <td><span class="badge bg-light text-dark border">{{ asset.group.name if asset.group else '—' }}</span></td>
    <td><a href="/asset/{{ asset.id }}" class="btn btn-sm btn-outline-info"><i class="bi bi-eye"></i></a></td>
</tr>
{% else %}
<tr><td colspan="7" class="text-center py-4 text-muted">Нет данных</td></tr>
{% endfor %}

```

### 📄 `templates/components/group_tree.html`

```html
<div class="group-tree-container">
    <!-- Заголовок секции -->
    <div class="d-flex justify-content-between align-items-center mb-3">
        <h6 class="mb-0 text-uppercase text-muted small fw-bold">
            <i class="bi bi-folder-tree me-2"></i>Группы активов
        </h6>
        <button class="btn btn-sm btn-outline-primary" onclick="showCreateGroupModal(null)" title="Новая группа">
            <i class="bi bi-plus-lg"></i>
        </button>
    </div>
    
    <!-- Дерево групп (будет заполнено через JS) -->
    <div id="group-tree" class="group-tree">
        <div class="text-muted small"><i class="bi bi-hourglass-split"></i> Загрузка...</div>
    </div>

    <!-- 🔹 Кнопка создания корневой группы -->
    <div class="mt-3 pt-3 border-top">
        <button class="btn btn-sm btn-outline-secondary w-100" onclick="showCreateGroupModal(null)">
            <i class="bi bi-plus-lg me-1"></i>Новая группа
        </button>
    </div>
    <div class="mt-4 pt-3 border-top">
    <h6 class="text-uppercase text-muted small fw-bold mb-3">
        <i class="bi bi-activity me-2"></i>Активные сканирования
    </h6>
    <div id="active-scans">
        <div class="text-center text-muted small py-2">
            <i class="bi bi-check-circle"></i> Нет активных задач
        </div>
    </div>
</div>
</div>
```

### 📄 `templates/components/modals.html`

```html
<!-- Универсальное окно создания/редактирования группы -->
<div class="modal fade" id="groupEditModal" tabindex="-1">
    <div class="modal-dialog modal-lg">
        <div class="modal-content">
            <form id="groupEditForm">
                <div class="modal-header">
                    <h5 id="groupEditTitle">Группа</h5>
                    <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                </div>
                <div class="modal-body">
                    <input type="hidden" id="edit-group-id">

                    <!-- 🔥 Переключатель режимов -->
                    <div class="btn-group w-100 mb-3" role="group">
                        <input type="radio" class="btn-check" name="groupMode" id="modeManual" value="manual" checked
                            onchange="toggleGroupMode()">
                        <label class="btn btn-outline-primary" for="modeManual">📝 Ручная</label>

                        <input type="radio" class="btn-check" name="groupMode" id="modeCidr" value="cidr"
                            onchange="toggleGroupMode()">
                        <label class="btn btn-outline-primary" for="modeCidr">🌐 По CIDR</label>

                        <input type="radio" class="btn-check" name="groupMode" id="modeDynamic" value="dynamic"
                            onchange="toggleGroupMode()">
                        <label class="btn btn-outline-primary" for="modeDynamic">⚡ Динамическая</label>
                    </div>

                    <!-- Секция: Общие поля (Имя + Родитель) -->
                    <div id="sectionCommon">
                        <div class="mb-3">
                            <label class="form-label">Название группы</label>
                            <input type="text" id="edit-group-name" class="form-control" required>
                        </div>
                        <div class="mb-3">
                            <label class="form-label">Родительская группа</label>
                            <!-- ✅ ИСПРАВЛЕНО: Убран цикл Jinja. Список будет заполнен через JS (populateParentSelect) -->
                            <select id="edit-group-parent" class="form-select hierarchy-select">
                                <option value="">-- Корень --</option>
                            </select>
                            <div class="form-text small text-muted">
                                Выберите родительскую группу для вложенности.
                            </div>
                        </div>
                    </div>

                    <!-- Секция: CIDR -->
                    <div id="sectionCidr" style="display:none;">
                        <div class="alert alert-info small">
                            Будут созданы подгруппы для каждой подсети указанного диапазона.
                        </div>
                        <div class="mb-3">
                            <label class="form-label">Сеть (CIDR)</label>
                            <input type="text" id="cidr-network" class="form-control" placeholder="192.168.0.0/16">
                        </div>
                        <div class="mb-3">
                            <label class="form-label">Маска подгрупп</label>
                            <select id="cidr-mask" class="form-select">
                                <option value="8">/8 (Класс A, ~16 млн хостов)</option>
                                <option value="12">/12 (Класс B частный, ~1 млн хостов)</option>
                                <option value="16">/16 (Класс B, 65 тыс. хостов)</option>
                                <option value="20">/20 (4096 хостов)</option>
                                <option value="22">/22 (1024 хоста)</option>
                                <option value="23">/23 (512 хостов)</option>
                                <option value="24" selected>/24 (256 хостов, стандарт)</option>
                                <option value="25">/25 (128 хостов)</option>
                                <option value="26">/26 (64 хоста)</option>
                                <option value="27">/27 (32 хоста)</option>
                                <option value="28">/28 (16 хостов)</option>
                                <option value="29">/29 (8 хостов)</option>
                                <option value="30">/30 (4 хоста, point-to-point)</option>
                            </select>
                            <div class="form-text small text-muted">
                                Выберите размер создаваемых подгрупп. Чем меньше число, тем больше хостов в группе.
                            </div>
                        </div>
                    </div>

                    <!-- Секция: Динамическая -->
                    <div id="sectionDynamic" style="display:none;">
                        <div class="alert alert-warning small">
                            Активы будут добавляться автоматически при совпадении с правилами.
                        </div>
                        <div class="mb-2">
                            <label class="form-label fw-bold">Правила фильтрации:</label>
                            <div id="group-filter-root" class="border rounded p-2 bg-light" style="min-height: 60px;">
                                <!-- Правила добавляются через JS -->
                            </div>
                            <button type="button" class="btn btn-sm btn-outline-success mt-2"
                                onclick="addDynamicRule()">
                                <i class="bi bi-plus-circle"></i> Добавить правило
                            </button>
                        </div>
                    </div>
                </div>
                <div class="modal-footer">
                    <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Отмена</button>
                    <button type="submit" class="btn btn-primary">Сохранить</button>
                </div>
            </form>
        </div>
    </div>
</div>

<!-- Заглушка для старого ID создания (перенаправляет на groupEditModal) -->
<div class="modal fade" id="groupCreateModal" tabindex="-1">
    <div class="modal-dialog modal-sm">
        <div class="modal-content">
            <div class="modal-body text-center p-4">
                <div class="spinner-border text-primary" role="status"></div>
                <p class="mt-2 small text-muted">Открытие мастера...</p>
            </div>
        </div>
    </div>
</div>

<!-- Перемещение группы -->
<div class="modal fade" id="groupMoveModal" tabindex="-1">
    <div class="modal-dialog">
        <div class="modal-content">
            <form id="groupMoveForm">
                <div class="modal-header">
                    <h5>Переместить группу</h5>
                    <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                </div>
                <div class="modal-body">
                    <input type="hidden" id="move-group-id">
                    <div class="mb-3">
                        <label class="form-label">Новый родитель</label>
                        <select id="move-group-parent" class="form-select"></select>
                    </div>
                </div>
                <div class="modal-footer">
                    <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Отмена</button>
                    <button type="submit" class="btn btn-primary">Переместить</button>
                </div>
            </form>
        </div>
    </div>
</div>

<!-- Удаление группы -->
<div class="modal fade" id="groupDeleteModal" tabindex="-1">
    <div class="modal-dialog">
        <div class="modal-content">
            <div class="modal-header">
                <h5 class="text-danger">Удаление группы</h5>
                <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
            </div>
            <div class="modal-body">
                <input type="hidden" id="delete-group-id">
                <p class="text-warning"><i class="bi bi-exclamation-triangle"></i> Вы уверены?</p>
                <div class="mb-3">
                    <label class="form-label">Перенести активы в:</label>
                    <select id="delete-move-assets" class="form-select">
                        <option value="">-- Удалить активы вместе с группой --</option>
                    </select>
                </div>
            </div>
            <div class="modal-footer">
                <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Отмена</button>
                <button type="button" class="btn btn-danger" onclick="confirmDeleteGroup()">Удалить</button>
            </div>
        </div>
    </div>
</div>

<!-- ═══════════════════════════════════════════════════════════════
     МОДАЛЬНЫЕ ОКНА АКТИВОВ (МАССОВОЕ УДАЛЕНИЕ)
     ═══════════════════════════════════════════════════════════════ -->
<div class="modal fade" id="bulkDeleteModal" tabindex="-1">
    <div class="modal-dialog">
        <div class="modal-content">
            <div class="modal-header">
                <h5 class="text-danger">Удаление активов</h5>
                <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
            </div>
            <div class="modal-body">
                <p>Удалить <strong id="bulk-delete-count">0</strong> выбранных активов?</p>
                <p class="text-muted small">Это действие нельзя отменить.</p>
            </div>
            <div class="modal-footer">
                <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Отмена</button>
                <button type="button" class="btn btn-danger" onclick="executeBulkDelete()">Удалить</button>
            </div>
        </div>
    </div>
</div>

<!-- ═══════════════════════════════════════════════════════════════
     МОДАЛЬНЫЕ ОКНА WAZUH
     ═══════════════════════════════════════════════════════════════ -->
<div class="modal fade" id="wazuhModal" tabindex="-1">
    <div class="modal-dialog">
        <div class="modal-content">
            <div class="modal-header">
                <h6 class="modal-title">⚙️ Настройка Wazuh API</h6>
                <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
            </div>
            <div class="modal-body">
                <div class="mb-2">
                    <label class="form-label small">URL API</label>
                    <input type="text" id="waz-url" class="form-control form-control-sm"
                        placeholder="https://manager:55000">
                </div>
                <div class="mb-2">
                    <label class="form-label small">Логин</label>
                    <input type="text" id="waz-user" class="form-control form-control-sm" placeholder="wazuh">
                </div>
                <div class="mb-2">
                    <label class="form-label small">Пароль</label>
                    <input type="password" id="waz-pass" class="form-control form-control-sm" placeholder="••••••">
                </div>
                <div class="form-check form-switch mb-2">
                    <input class="form-check-input" type="checkbox" id="waz-ssl">
                    <label class="form-check-label small">Проверять SSL сертификат</label>
                </div>
                <div class="form-check form-switch mb-3">
                    <input class="form-check-input" type="checkbox" id="waz-active" checked>
                    <label class="form-check-label small">Включить интеграцию</label>
                </div>
                <button class="btn btn-sm btn-success w-100" onclick="saveWazuhConfig()">
                    💾 Сохранить и синхронизировать
                </button>
                <div id="waz-status" class="mt-2 small text-center text-muted"></div>
            </div>
        </div>
    </div>
</div>

<!-- ═══════════════════════════════════════════════════════════════
     МОДАЛЬНЫЕ ОКНА СКАНИРОВАНИЯ (РЕЗУЛЬТАТЫ И ОШИБКИ)
     ═══════════════════════════════════════════════════════════════ -->
<div class="modal fade" id="scanErrorModal" tabindex="-1">
    <div class="modal-dialog modal-lg">
        <div class="modal-content">
            <div class="modal-header bg-danger text-white">
                <h5 class="modal-title"><i class="bi bi-exclamation-triangle"></i> Ошибка сканирования</h5>
                <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>
            </div>
            <div class="modal-body">
                <div id="scan-error-content"></div>
            </div>
            <div class="modal-footer">
                <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Закрыть</button>
            </div>
        </div>
    </div>
</div>

<div class="modal fade" id="scanResultsModal" tabindex="-1">
    <div class="modal-dialog modal-lg">
        <div class="modal-content">
            <div class="modal-header">
                <h5 class="modal-title">Результаты сканирования</h5>
                <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
            </div>
            <div class="modal-body">
                <div id="scan-results-content"></div>
                <!-- Блок для отображения ошибок внутри результатов -->
                <div id="scan-error-alert" class="alert alert-danger mt-3" style="display:none">
                    <h6><i class="bi bi-exclamation-triangle"></i> Ошибка выполнения:</h6>
                    <pre id="scan-error-text" class="mb-0"
                        style="white-space:pre-wrap;max-height:300px;overflow-y:auto"></pre>
                </div>
            </div>
            <div class="modal-footer">
                <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Закрыть</button>
            </div>
        </div>
    </div>
</div>

<!-- Импорт сканирования (Nmap XML) -->
<div class="modal fade" id="scanModal" tabindex="-1">
    <div class="modal-dialog">
        <div class="modal-content">
            <form action="{{ url_for('main.import_scan') }}" method="post" enctype="multipart/form-data">
                <div class="modal-header">
                    <h5 class="modal-title">Импорт Nmap XML</h5>
                    <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                </div>
                <div class="modal-body">
                    <div class="mb-3">
                        <label class="form-label">XML файл</label>
                        <input type="file" name="file" class="form-control" accept=".xml" required>
                    </div>
                    <div class="mb-3">
                        <label class="form-label">Группа назначения</label>
                        <select name="group_id" class="form-select">
                            <option value="">Без группы</option>
                            {% for g in all_groups %}<option value="{{ g.id }}">{{ g.name }}</option>{% endfor %}
                        </select>
                    </div>
                </div>
                <div class="modal-footer">
                    <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Отмена</button>
                    <button type="submit" class="btn btn-primary">Загрузить</button>
                </div>
            </form>
        </div>
    </div>
</div>
```

---

✅ **Экспорт завершён.** Файл содержит 44 файлов общим размером 423.1 KB.
💡 **Совет:** Скопируйте содержимое этого файла целиком в новое окно чата для сохранения контекста разработки.
