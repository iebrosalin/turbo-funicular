# 📁 PROJECT CODEBASE: Nmap Asset Manager v2.0

**Дата экспорта:** 2026-04-07 11:14:57
**Файлов включено:** 15
**Общий размер:** 219.3 KB
**Инструкция для ИИ:** Используй этот файл как полный контекст проекта. Ссылайся на файлы по путям из заголовков.
---

## 🌳 Структура проекта

```text
📁 ./
    📄 app.py
    📄 export_project_state.py
    📁 instance/
    📁 static/
        📁 css/
            📄 style.css
        📁 js/
            📄 main.js
    📁 templates/
        📄 asset_detail.html
        📄 asset_history.html
        📄 base.html
        📄 create.html
        📄 edit.html
        📄 index.html
        📄 scans.html
        📄 utilities.html
        📁 components/
            📄 assets_rows.html
            📄 group_tree.html
            📄 modals.html
    📁 uploads/
```

---

## 📂 Исходный код

### 📄 `app.py`

```python
# ═══════════════════════════════════════════════════════════════
# ИМПОРТЫ
# ═══════════════════════════════════════════════════════════════

import os
import json
import subprocess
import threading
import shutil
import xml.etree.ElementTree as ET
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, Response, send_file
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import or_, and_, func
from werkzeug.utils import secure_filename

# ═══════════════════════════════════════════════════════════════
# КОНФИГУРАЦИЯ ПРИЛОЖЕНИЯ
# ═══════════════════════════════════════════════════════════════

app = Flask(__name__)
app.config['SECRET_KEY'] = 'super-secret-key-change-me'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///assets.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['SCAN_RESULTS_FOLDER'] = 'scan_results'
app.config['MAX_SCAN_THREADS'] = 5

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['SCAN_RESULTS_FOLDER'], exist_ok=True)

db = SQLAlchemy(app)

# ═══════════════════════════════════════════════════════════════
# МОДЕЛИ БД
# ═══════════════════════════════════════════════════════════════

class Group(db.Model):
    __tablename__ = 'group'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    parent_id = db.Column(db.Integer, db.ForeignKey('group.id'), nullable=True)
    filter_query = db.Column(db.Text, nullable=True)
    is_dynamic = db.Column(db.Boolean, default=False)
    children = db.relationship('Group', backref=db.backref('parent', remote_side=[id]))
    assets = db.relationship('Asset', backref='group', lazy=True)

    def __repr__(self):
        return f'<Group {self.name}>'


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

    def __repr__(self):
        return f'<Asset {self.ip_address}>'


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
    
    def to_dict(self):
        return {
            'id': self.id,
            'scan_type': self.scan_type,
            'target': self.target,
            'status': self.status,
            'progress': self.progress,
            'started_at': self.started_at.strftime('%Y-%m-%d %H:%M:%S') if self.started_at else None,
            'completed_at': self.completed_at.strftime('%Y-%m-%d %H:%M:%S') if self.completed_at else None,
            'error_message': self.error_message,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S')
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
            'id': self.id,
            'asset_id': self.asset_id,
            'changed_at': self.changed_at.strftime('%Y-%m-%d %H:%M:%S'),
            'change_type': self.change_type,
            'field_name': self.field_name,
            'old_value': json.loads(self.old_value) if self.old_value else None,
            'new_value': json.loads(self.new_value) if self.new_value else None,
            'scan_job_id': self.scan_job_id,
            'notes': self.notes
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
            'id': self.id,
            'port': self.port,
            'protocol': self.protocol,
            'service_name': self.service_name,
            'product': self.product,
            'version': self.version,
            'extrainfo': self.extrainfo,
            'cpe': self.cpe,
            'script_output': self.script_output,
            'first_seen': self.first_seen.strftime('%Y-%m-%d %H:%M:%S'),
            'last_seen': self.last_seen.strftime('%Y-%m-%d %H:%M:%S'),
            'is_active': self.is_active
        }


# ═══════════════════════════════════════════════════════════════
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ═══════════════════════════════════════════════════════════════

def parse_nmap_xml(filepath):
    tree = ET.parse(filepath)
    root = tree.getroot()
    assets = []
    
    for host in root.findall('host'):
        status = host.find('status')
        if status is None or status.get('state') != 'up':
            continue
        
        addr = host.find('address')
        ip = addr.get('addr') if addr is not None else 'Unknown'
        
        hostnames = host.find('hostnames')
        hostname = 'Unknown'
        if hostnames is not None:
            name_elem = hostnames.find('hostname')
            if name_elem is not None:
                hostname = name_elem.get('name')
        
        os_info = 'Unknown'
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
                    service_name = service.get('name') if service is not None else ''
                    ports.append(f"{port_id}/{service_name}")
        
        assets.append({
            'ip_address': ip,
            'hostname': hostname,
            'os_info': os_info,
            'status': 'up',
            'open_ports': ', '.join(ports)
        })
    
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
                except:
                    count = 0
            else:
                count = len(group.assets)
            
            tree.append({
                'id': group.id,
                'name': group.name,
                'children': children,
                'count': count,
                'is_dynamic': group.is_dynamic
            })
    return tree


def build_complex_query(model, filters_structure, base_query=None):
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
            else:
                if logic == 'AND':
                    sqlalchemy_filters.append(model.id == -1)
        else:
            field = item.get('field')
            op = item.get('op')
            val = item.get('value')
            col = getattr(model, field, None)
            if col is None:
                continue

            if op == 'eq':
                sqlalchemy_filters.append(col == val)
            elif op == 'ne':
                sqlalchemy_filters.append(col != val)
            elif op == 'like':
                sqlalchemy_filters.append(col.like(f'%{val}%'))
            elif op == 'gt':
                sqlalchemy_filters.append(col > val)
            elif op == 'lt':
                sqlalchemy_filters.append(col < val)
            elif op == 'in':
                sqlalchemy_filters.append(col.in_(val.split(',')))

    if sqlalchemy_filters:
        if logic == 'AND':
            base_query = base_query.filter(and_(*sqlalchemy_filters))
        else:
            base_query = base_query.filter(or_(*sqlalchemy_filters))
            
    return base_query


def log_asset_change(asset_id, change_type, field_name, old_value, new_value, scan_job_id=None, notes=None):
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


# ═══════════════════════════════════════════════════════════════
# ФУНКЦИИ СКАНИРОВАНИЯ (ОБНОВЛЁННЫЕ)
# ═══════════════════════════════════════════════════════════════

def run_rustscan_scan(scan_job_id, target, custom_args=''):
    """Фоновое выполнение rustscan с кастомными аргументами"""
    scan_job = ScanJob.query.get(scan_job_id)
    if not scan_job:
        return
    
    try:
        scan_job.status = 'running'
        scan_job.started_at = datetime.utcnow()
        scan_job.progress = 10
        db.session.commit()
        
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        result_dir = os.path.join(app.config['SCAN_RESULTS_FOLDER'], f'rustscan_{timestamp}')
        os.makedirs(result_dir, exist_ok=True)
        
        output_file = os.path.join(result_dir, 'output.txt')
        
        # Базовая команда
        cmd = ['rustscan', '-a', target, '--greppable', '-o', output_file]
        
        # 🔥 Добавляем кастомные аргументы 🔥
        if custom_args:
            custom_args_list = custom_args.split()
            cmd.extend(custom_args_list)
            print(f"🔧 Custom rustscan args: {custom_args}")
        
        # Аргументы по умолчанию (если не переопределены)
        if '--batch-size' not in custom_args:
            cmd.extend(['--batch-size', '1000'])
        if '--timeout' not in custom_args:
            cmd.extend(['--timeout', '1500'])
        
        print(f"🔍 Запуск rustscan: {' '.join(cmd)}")
        
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        scan_job.progress = 50
        db.session.commit()
        
        stdout, stderr = process.communicate()
        
        if process.returncode == 0:
            scan_job.progress = 90
            if os.path.exists(output_file):
                with open(output_file, 'r') as f:
                    scan_job.rustscan_output = f.read()
            
            parse_rustscan_results(scan_job_id, scan_job.rustscan_output, target)
            scan_job.status = 'completed'
            scan_job.progress = 100
        else:
            scan_job.status = 'failed'
            scan_job.error_message = stderr or f"Exit code: {process.returncode}"
        
        scan_job.completed_at = datetime.utcnow()
        db.session.commit()
        
    except Exception as e:
        scan_job.status = 'failed'
        scan_job.error_message = str(e)
        scan_job.completed_at = datetime.utcnow()
        db.session.commit()


def run_nmap_scan(scan_job_id, target, ports=None, custom_args=''):
    """Фоновое выполнение nmap с кастомными аргументами"""
    scan_job = ScanJob.query.get(scan_job_id)
    if not scan_job:
        return
    
    try:
        scan_job.status = 'running'
        scan_job.started_at = datetime.utcnow()
        scan_job.progress = 10
        db.session.commit()
        
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        result_dir = os.path.join(app.config['SCAN_RESULTS_FOLDER'], f'nmap_{timestamp}')
        os.makedirs(result_dir, exist_ok=True)
        
        base_filename = os.path.join(result_dir, 'scan')
        
        # Базовая команда
        cmd = ['nmap', target, '-oA', base_filename]
        
        # 🔥 Добавляем кастомные аргументы 🔥
        if custom_args:
            custom_args_list = custom_args.split()
            # Вставляем кастомные аргументы после nmap и перед target
            cmd = ['nmap'] + custom_args_list + [target, '-oA', base_filename]
            print(f"🔧 Custom nmap args: {custom_args}")
        
        # Порты (если не переопределены в custom_args)
        if ports and '-p' not in custom_args:
            cmd.extend(['-p', ports])
        
        # Аргументы по умолчанию (если не переопределены)
        if '-sV' not in custom_args:
            cmd.extend(['-sV'])
        if '-sC' not in custom_args:
            cmd.extend(['-sC'])
        if '-O' not in custom_args:
            cmd.extend(['-O'])
        
        print(f"🔍 Запуск nmap: {' '.join(cmd)}")
        
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        scan_job.progress = 50
        db.session.commit()
        
        stdout, stderr = process.communicate()
        
        if process.returncode == 0:
            scan_job.progress = 90
            scan_job.nmap_xml_path = f'{base_filename}.xml'
            scan_job.nmap_grep_path = f'{base_filename}.gnmap'
            scan_job.nmap_normal_path = f'{base_filename}.nmap'
            
            if os.path.exists(scan_job.nmap_xml_path):
                parse_nmap_results(scan_job_id, scan_job.nmap_xml_path)
            
            scan_job.status = 'completed'
            scan_job.progress = 100
        else:
            scan_job.status = 'failed'
            scan_job.error_message = stderr or f"Exit code: {process.returncode}"
        
        scan_job.completed_at = datetime.utcnow()
        db.session.commit()
        
    except Exception as e:
        scan_job.status = 'failed'
        scan_job.error_message = str(e)
        scan_job.completed_at = datetime.utcnow()
        db.session.commit()


def parse_rustscan_results(scan_job_id, output, target):
    if not output:
        return
    
    lines = output.strip().split('\n')
    scan_job = ScanJob.query.get(scan_job_id)
    
    for line in lines:
        if '->' in line:
            try:
                parts = line.split('->')
                ip = parts[0].strip()
                ports_str = parts[1].strip() if len(parts) > 1 else ''
                new_ports = [p.strip() for p in ports_str.split(',') if p.strip()]
                
                asset = Asset.query.filter_by(ip_address=ip).first()
                if not asset:
                    asset = Asset(ip_address=ip, status='up')
                    db.session.add(asset)
                    db.session.flush()
                    log_asset_change(asset.id, 'asset_created', 'ip_address', None, ip, scan_job_id, 'Создан через rustscan')
                else:
                    existing_ports = set(asset.open_ports.split(', ')) if asset.open_ports else set()
                    new_ports_set = set(new_ports)
                    
                    added_ports = new_ports_set - existing_ports
                    removed_ports = existing_ports - new_ports_set
                    
                    for port in added_ports:
                        log_asset_change(asset.id, 'port_added', 'open_ports', None, port, scan_job_id)
                    
                    for port in removed_ports:
                        log_asset_change(asset.id, 'port_removed', 'open_ports', port, None, scan_job_id)
                
                if new_ports:
                    all_ports = existing_ports.union(new_ports_set) if asset.open_ports else new_ports_set
                    asset.open_ports = ', '.join(sorted(all_ports, key=lambda x: int(x.split('/')[0]) if '/' in x else int(x)))
                
                asset.last_scanned = datetime.utcnow()
                
                scan_result = ScanResult(
                    asset_id=asset.id,
                    ip_address=ip,
                    scan_job_id=scan_job_id,
                    ports=json.dumps(new_ports),
                    scanned_at=datetime.utcnow()
                )
                db.session.add(scan_result)
                
            except Exception as e:
                print(f"⚠️ Ошибка парсинга строки: {line} - {e}")
    
    db.session.commit()


def parse_nmap_results(scan_job_id, xml_path):
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
        scan_job = ScanJob.query.get(scan_job_id)
        
        for host in root.findall('host'):
            status = host.find('status')
            if status is None or status.get('state') != 'up':
                continue
            
            addr = host.find('address')
            ip = addr.get('addr') if addr is not None else None
            if not ip:
                continue
            
            hostname = 'Unknown'
            hostnames = host.find('hostnames')
            if hostnames is not None:
                name_elem = hostnames.find('hostname')
                if name_elem is not None:
                    hostname = name_elem.get('name')
            
            os_info = 'Unknown'
            os_elem = host.find('os')
            if os_elem is not None:
                os_match = os_elem.find('osmatch')
                if os_match is not None:
                    os_info = os_match.get('name')
            
            ports = []
            services = []
            ports_elem = host.find('ports')
            
            if ports_elem is not None:
                for port in ports_elem.findall('port'):
                    state = port.find('state')
                    if state is not None and state.get('state') == 'open':
                        port_id = port.get('portid')
                        protocol = port.get('protocol')
                        service = port.find('service')
                        
                        service_name = service.get('name') if service is not None else ''
                        service_product = service.get('product') if service is not None else ''
                        service_version = service.get('version') if service is not None else ''
                        service_extrainfo = service.get('extrainfo') if service is not None else ''
                        service_cpe = service.get('cpe') if service is not None else ''
                        
                        port_str = f"{port_id}/{protocol}"
                        ports.append(port_str)
                        
                        script_output = []
                        for script in port.findall('script'):
                            script_output.append({
                                'id': script.get('id'),
                                'output': script.get('output')
                            })
                        
                        service_info = {
                            'port': port_str,
                            'name': service_name,
                            'product': service_product,
                            'version': service_version,
                            'extrainfo': service_extrainfo,
                            'cpe': service_cpe,
                            'scripts': script_output
                        }
                        services.append(service_info)
                        
                        asset = Asset.query.filter_by(ip_address=ip).first()
                        if asset:
                            existing_service = ServiceInventory.query.filter_by(
                                asset_id=asset.id,
                                port=port_str
                            ).first()
                            
                            if existing_service:
                                changes = []
                                if existing_service.service_name != service_name:
                                    changes.append(('service_name', existing_service.service_name, service_name))
                                if existing_service.product != service_product:
                                    changes.append(('product', existing_service.product, service_product))
                                if existing_service.version != service_version:
                                    changes.append(('version', existing_service.version, service_version))
                                
                                for field, old, new in changes:
                                    log_asset_change(asset.id, 'service_updated', field, old, new, scan_job_id, f'Порт {port_str}')
                                
                                existing_service.service_name = service_name
                                existing_service.product = service_product
                                existing_service.version = service_version
                                existing_service.extrainfo = service_extrainfo
                                existing_service.cpe = service_cpe
                                existing_service.script_output = json.dumps(script_output)
                                existing_service.last_seen = datetime.utcnow()
                                existing_service.is_active = True
                            else:
                                new_service = ServiceInventory(
                                    asset_id=asset.id,
                                    port=port_str,
                                    protocol=protocol,
                                    service_name=service_name,
                                    product=service_product,
                                    version=service_version,
                                    extrainfo=service_extrainfo,
                                    cpe=service_cpe,
                                    script_output=json.dumps(script_output)
                                )
                                db.session.add(new_service)
                                log_asset_change(asset.id, 'service_detected', 'service_inventory', None, service_name, scan_job_id, f'Новый сервис на порту {port_str}')
            
            asset = Asset.query.filter_by(ip_address=ip).first()
            if not asset:
                asset = Asset(ip_address=ip, status='up')
                db.session.add(asset)
                db.session.flush()
                log_asset_change(asset.id, 'asset_created', 'ip_address', None, ip, scan_job_id, 'Создан через nmap')
            
            if asset.os_info != os_info and os_info != 'Unknown':
                log_asset_change(asset.id, 'os_changed', 'os_info', asset.os_info, os_info, scan_job_id)
            
            asset.hostname = hostname if hostname != 'Unknown' else asset.hostname
            asset.os_info = os_info if os_info != 'Unknown' else asset.os_info
            if ports:
                asset.open_ports = ', '.join(ports)
            asset.last_scanned = datetime.utcnow()
            
            scan_result = ScanResult(
                asset_id=asset.id,
                ip_address=ip,
                scan_job_id=scan_job_id,
                ports=json.dumps(ports),
                services=json.dumps(services),
                os_detection=os_info,
                scanned_at=datetime.utcnow()
            )
            db.session.add(scan_result)
        
        db.session.commit()
        
    except Exception as e:
        print(f"❌ Ошибка парсинга nmap XML: {e}")


# ═══════════════════════════════════════════════════════════════
# МАРШРУТЫ
# ═══════════════════════════════════════════════════════════════

@app.route('/')
def index():
    all_groups = Group.query.all()
    group_tree = build_group_tree(all_groups)
    assets = Asset.query.all()
    
    # Подсчёт активов без группы
    ungrouped_count = Asset.query.filter(Asset.group_id.is_(None)).count()
    
    # 🔥 Определяем текущий фильтр для подсветки 🔥
    current_filter = request.args.get('group_id')
    if request.args.get('ungrouped') == 'true':
        current_filter = 'ungrouped'
    elif not current_filter or current_filter == 'all':
        current_filter = 'ungrouped'  # По умолчанию
    
    return render_template('index.html', 
                         assets=assets, 
                         group_tree=group_tree, 
                         all_groups=all_groups,
                         ungrouped_count=ungrouped_count,
                         current_filter=current_filter)


@app.route('/api/assets', methods=['GET'])
def get_assets_api():
    """API для получения активов с фильтрацией"""
    query = Asset.query
    
    # 🔥 Логирование всех параметров 🔥
    print(f"🔍 API /api/assets called")
    print(f"   - ungrouped: {request.args.get('ungrouped')}")
    print(f"   - group_id: {request.args.get('group_id')}")
    print(f"   - filters: {request.args.get('filters')}")
    
    filters_raw = request.args.get('filters')
    
    # 🔥 Фильтр для активов без группы 🔥
    ungrouped = request.args.get('ungrouped')
    if ungrouped and ungrouped.lower() == 'true':
        print(f"   ✅ Filtering UNGROUPED assets (group_id IS NULL)")
        query = query.filter(Asset.group_id.is_(None))
    else:
        # Обычная фильтрация по группе
        group_id = request.args.get('group_id')
        if group_id and group_id != 'all':
            print(f"   ✅ Filtering by group_id: {group_id}")
            # 🔥 Проверяем, что group_id - валидное число 🔥
            try:
                group_id_int = int(group_id)
                group = Group.query.get(group_id_int)
                if group and group.is_dynamic and group.filter_query:
                    try:
                        filter_struct = json.loads(group.filter_query)
                        query = build_complex_query(Asset, filter_struct, query)
                    except Exception as e:
                        print(f"   ⚠️ Dynamic group filter error: {e}")
                        query = query.filter(Asset.group_id == group_id_int)
                else:
                    query = query.filter(Asset.group_id == group_id_int)
            except ValueError:
                print(f"   ❌ Invalid group_id: {group_id}")
                return jsonify({'error': 'Invalid group_id'}), 400
    
    # Остальные фильтры
    if filters_raw:
        try:
            filters_structure = json.loads(filters_raw)
            query = build_complex_query(Asset, filters_structure, query)
        except Exception as e:
            print(f"   ⚠️ Filter error: {e}")

    assets = query.all()
    print(f"   ✅ Found {len(assets)} assets")
    
    data = [{
        'id': a.id,
        'ip': a.ip_address,
        'hostname': a.hostname,
        'os': a.os_info,
        'ports': a.open_ports,
        'group': a.group.name if a.group else 'Без группы',
        'last_scan': a.last_scanned.strftime('%Y-%m-%d %H:%M')
    } for a in assets]
    
    return jsonify(data)


@app.route('/api/analytics', methods=['GET'])
def get_analytics():
    filters_raw = request.args.get('filters')
    group_by_field = request.args.get('group_by', 'os_info')
    
    query = Asset.query
    if filters_raw:
        try:
            filters_structure = json.loads(filters_raw)
            query = build_complex_query(Asset, filters_structure, query)
        except:
            pass

    group_col = getattr(Asset, group_by_field, Asset.os_info)
    results = db.session.query(group_col, func.count(Asset.id).label('count')).group_by(group_col).all()
    data = [{'label': r[0] or 'Unknown', 'value': r[1]} for r in results]
    return jsonify(data)


@app.route('/api/groups', methods=['POST'])
def api_create_group():
    data = request.json
    name = data.get('name')
    parent_id = data.get('parent_id')
    filter_query = data.get('filter_query')
    is_dynamic = True if filter_query else False
    
    if parent_id == '':
        parent_id = None
    if not name:
        return jsonify({'error': 'Имя обязательно'}), 400
        
    new_group = Group(name=name, parent_id=parent_id, filter_query=filter_query, is_dynamic=is_dynamic)
    db.session.add(new_group)
    db.session.commit()
    return jsonify({'id': new_group.id, 'name': new_group.name, 'is_dynamic': is_dynamic}), 201


@app.route('/api/groups/<int:id>', methods=['PUT'])
def api_update_group(id):
    group = Group.query.get_or_404(id)
    data = request.json
    
    if 'name' in data:
        group.name = data['name']
    if 'parent_id' in data:
        new_parent_id = data['parent_id']
        if new_parent_id == '':
            new_parent_id = None
        if new_parent_id and int(new_parent_id) == group.id:
            return jsonify({'error': 'Группа не может быть родителем самой себя'}), 400
        group.parent_id = new_parent_id
    if 'filter_query' in data:
        group.filter_query = data['filter_query'] if data['filter_query'] else None
        group.is_dynamic = bool(data['filter_query'])
        
    db.session.commit()
    return jsonify({'success': True})


@app.route('/api/groups/<int:id>', methods=['DELETE'])
def api_delete_group(id):
    group = Group.query.get_or_404(id)
    move_to_id = request.args.get('move_to')
    
    if move_to_id:
        Asset.query.filter_by(group_id=id).update({'group_id': move_to_id})
    
    db.session.delete(group)
    db.session.commit()
    return jsonify({'success': True})


@app.route('/api/groups/tree')
def api_get_tree():
    all_groups = Group.query.all()
    tree = build_group_tree(all_groups)
    
    flat_list = []
    def flatten(nodes, level=0):
        for node in nodes:
            flat_list.append({
                'id': node['id'],
                'name': '  ' * level + node['name'],
                'is_dynamic': node.get('is_dynamic', False)
            })
            flatten(node['children'], level + 1)
    flatten(tree)
    
    return jsonify({'tree': tree, 'flat': flat_list})


@app.route('/groups', methods=['POST'])
def manage_groups():
    name = request.form.get('name')
    parent_id = request.form.get('parent_id')
    if parent_id == '':
        parent_id = None
    db.session.add(Group(name=name, parent_id=parent_id))
    db.session.commit()
    return redirect(url_for('index'))


@app.route('/asset/<int:id>')
def asset_detail(id):
    asset = Asset.query.get_or_404(id)
    all_groups = Group.query.all()
    
    ports_detail = []
    if asset.open_ports:
        for port_str in asset.open_ports.split(', '):
            if '/' in port_str:
                port_id, service = port_str.split('/', 1)
                ports_detail.append({
                    'port': port_id,
                    'service': service if service else 'unknown'
                })
    
    scan_history = [{
        'date': asset.last_scanned,
        'status': asset.status,
        'ports_count': len(asset.open_ports.split(', ')) if asset.open_ports else 0
    }]
    
    return render_template('asset_detail.html', 
                         asset=asset, 
                         ports_detail=ports_detail,
                         scan_history=scan_history,
                         all_groups=all_groups)


@app.route('/asset/<int:id>/history')
def asset_history(id):
    asset = Asset.query.get_or_404(id)
    all_groups = Group.query.all()
    group_tree = build_group_tree(all_groups)
    
    changes = AssetChangeLog.query.filter_by(asset_id=id).order_by(AssetChangeLog.changed_at.desc()).all()
    services = ServiceInventory.query.filter_by(asset_id=id, is_active=True).all()
    
    return render_template('asset_history.html', 
                         asset=asset, 
                         changes=changes, 
                         services=services,
                         group_tree=group_tree,
                         all_groups=all_groups)


@app.route('/api/asset/<int:id>/history')
def api_asset_history(id):
    changes = AssetChangeLog.query.filter_by(asset_id=id).order_by(AssetChangeLog.changed_at.desc()).limit(100).all()
    
    return jsonify({
        'asset_id': id,
        'total_changes': len(changes),
        'changes': [change.to_dict() for change in changes]
    })


@app.route('/api/asset/<int:id>/services')
def api_asset_services(id):
    services = ServiceInventory.query.filter_by(asset_id=id).all()
    
    return jsonify({
        'asset_id': id,
        'total_services': len(services),
        'active_services': len([s for s in services if s.is_active]),
        'services': [s.to_dict() for s in services]
    })


@app.route('/asset/<int:id>/service/<int:service_id>/toggle', methods=['POST'])
def toggle_service_status(id, service_id):
    service = ServiceInventory.query.get_or_404(service_id)
    
    if service.asset_id != id:
        return jsonify({'error': 'Service does not belong to this asset'}), 400
    
    service.is_active = not service.is_active
    db.session.commit()
    
    return jsonify({
        'success': True,
        'is_active': service.is_active
    })


@app.route('/asset/<int:id>/update-notes', methods=['POST'])
def update_asset_notes(id):
    asset = Asset.query.get_or_404(id)
    notes = request.form.get('notes', '')
    asset.notes = notes
    db.session.commit()
    flash('Заметки обновлены', 'success')
    return redirect(url_for('asset_detail', id=id))


@app.route('/asset/<int:id>/update-group', methods=['POST'])
def update_asset_group(id):
    asset = Asset.query.get_or_404(id)
    group_id = request.form.get('group_id')
    asset.group_id = group_id if group_id else None
    db.session.commit()
    flash('Группа обновлена', 'success')
    return redirect(url_for('asset_detail', id=id))


@app.route('/asset/<int:id>/delete')
def delete_asset(id):
    asset = Asset.query.get_or_404(id)
    db.session.delete(asset)
    db.session.commit()
    flash('Актив удалён', 'warning')
    return redirect(url_for('index'))


@app.route('/asset/<int:id>/scan-nmap', methods=['POST'])
def scan_asset_nmap(id):
    asset = Asset.query.get_or_404(id)
    
    scan_job = ScanJob(
        scan_type='nmap',
        target=asset.ip_address,
        status='pending'
    )
    db.session.add(scan_job)
    db.session.commit()
    
    thread = threading.Thread(target=run_nmap_scan, args=(scan_job.id, asset.ip_address, None))
    thread.daemon = True
    thread.start()
    
    flash(f'Nmap сканирование запущено для {asset.ip_address}', 'info')
    return redirect(url_for('asset_detail', id=id))


@app.route('/api/assets/bulk-delete', methods=['POST'])
def bulk_delete_assets():
    data = request.json
    asset_ids = data.get('ids', [])
    
    if not asset_ids:
        return jsonify({'error': 'No IDs provided'}), 400
    
    deleted_count = Asset.query.filter(Asset.id.in_(asset_ids)).delete(synchronize_session=False)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'deleted': deleted_count,
        'message': f'Удалено активов: {deleted_count}'
    })


# ═══════════════════════════════════════════════════════════════
# МАРШРУТЫ - СКАНИРОВАНИЕ (ОБНОВЛЁННЫЕ)
# ═══════════════════════════════════════════════════════════════

@app.route('/scans')
def scans_page():
    """Страница управления сканированиями"""
    all_groups = Group.query.all()
    group_tree = build_group_tree(all_groups)
    scan_jobs = ScanJob.query.order_by(ScanJob.created_at.desc()).limit(50).all()
    
    return render_template('scans.html', 
                         scan_jobs=scan_jobs, 
                         group_tree=group_tree, 
                         all_groups=all_groups)


@app.route('/api/scans/rustscan', methods=['POST'])
def start_rustscan():
    """Запуск rustscan с поддержкой групп и кастомных аргументов"""
    data = request.json
    target = data.get('target', '')
    group_id = data.get('group_id')
    custom_args = data.get('custom_args', '')
    
    # 🔥 Определяем цель сканирования 🔥
    if group_id:
        if group_id == 'ungrouped':
            # Активы без группы
            assets = Asset.query.filter(Asset.group_id.is_(None)).all()
        else:
            # Активы из группы (включая вложенные)
            group = Group.query.get(group_id)
            if not group:
                return jsonify({'error': 'Группа не найдена'}), 404
            
            # Собираем все ID групп (родитель + дочерние)
            def get_child_group_ids(parent_id, all_groups, result=[]):
                children = [g for g in all_groups if g.parent_id == parent_id]
                for child in children:
                    result.append(child.id)
                    get_child_group_ids(child.id, all_groups, result)
                return result
            
            all_groups = Group.query.all()
            group_ids = [group_id] + get_child_group_ids(group_id, all_groups)
            assets = Asset.query.filter(Asset.group_id.in_(group_ids)).all()
        
        if not assets:
            return jsonify({'error': 'В группе нет активов'}), 400
        
        # Создаём список IP для сканирования
        target = ' '.join([a.ip_address for a in assets])
        target_description = f"Группа: {group.name if group_id != 'ungrouped' else 'Без группы'} ({len(assets)} активов)"
    else:
        if not target:
            return jsonify({'error': 'Цель сканирования не указана'}), 400
        target_description = target
    
    # Создаём задание
    scan_job = ScanJob(
        scan_type='rustscan',
        target=target_description,
        status='pending',
        rustscan_output=custom_args if custom_args else None
    )
    db.session.add(scan_job)
    db.session.commit()
    
    # Запускаем в фоне с кастомными аргументами
    thread = threading.Thread(
        target=run_rustscan_scan, 
        args=(scan_job.id, target, custom_args)
    )
    thread.daemon = True
    thread.start()
    
    return jsonify({
        'success': True,
        'job_id': scan_job.id,
        'message': f'Rustscan запущен для {target_description}'
    })


@app.route('/api/scans/nmap', methods=['POST'])
def start_nmap():
    """Запуск nmap с поддержкой групп и кастомных аргументов"""
    data = request.json
    target = data.get('target', '')
    group_id = data.get('group_id')
    ports = data.get('ports', '')
    custom_args = data.get('custom_args', '')
    
    # 🔥 Определяем цель сканирования 🔥
    if group_id:
        if group_id == 'ungrouped':
            assets = Asset.query.filter(Asset.group_id.is_(None)).all()
        else:
            group = Group.query.get(group_id)
            if not group:
                return jsonify({'error': 'Группа не найдена'}), 404
            
            def get_child_group_ids(parent_id, all_groups, result=[]):
                children = [g for g in all_groups if g.parent_id == parent_id]
                for child in children:
                    result.append(child.id)
                    get_child_group_ids(child.id, all_groups, result)
                return result
            
            all_groups = Group.query.all()
            group_ids = [group_id] + get_child_group_ids(group_id, all_groups)
            assets = Asset.query.filter(Asset.group_id.in_(group_ids)).all()
        
        if not assets:
            return jsonify({'error': 'В группе нет активов'}), 400
        
        target = ' '.join([a.ip_address for a in assets])
        target_description = f"Группа: {group.name if group_id != 'ungrouped' else 'Без группы'} ({len(assets)} активов)"
    else:
        if not target:
            return jsonify({'error': 'Цель сканирования не указана'}), 400
        target_description = target
    
    # Создаём задание
    scan_job = ScanJob(
        scan_type='nmap',
        target=target_description,
        status='pending',
        rustscan_output=f'Ports: {ports}' if ports else None
    )
    if custom_args:
        scan_job.error_message = f'Custom args: {custom_args}'  # Используем поле для кастомных аргументов
    
    db.session.add(scan_job)
    db.session.commit()
    
    # Запускаем в фоне с кастомными аргументами
    thread = threading.Thread(
        target=run_nmap_scan, 
        args=(scan_job.id, target, ports, custom_args)
    )
    thread.daemon = True
    thread.start()
    
    return jsonify({
        'success': True,
        'job_id': scan_job.id,
        'message': f'Nmap запущен для {target_description}'
    })


@app.route('/api/scans/<int:job_id>')
def get_scan_status(job_id):
    scan_job = ScanJob.query.get_or_404(job_id)
    return jsonify(scan_job.to_dict())


@app.route('/api/scans/<int:job_id>/results')
def get_scan_results(job_id):
    scan_job = ScanJob.query.get_or_404(job_id)
    
    results = []
    for result in scan_job.results:
        results.append({
            'ip': result.ip_address,
            'ports': json.loads(result.ports) if result.ports else [],
            'services': json.loads(result.services) if result.services else [],
            'os': result.os_detection,
            'scanned_at': result.scanned_at.strftime('%Y-%m-%d %H:%M:%S')
        })
    
    return jsonify({
        'job': scan_job.to_dict(),
        'results': results
    })


@app.route('/scans/<int:job_id>/download/<format_type>')
def download_scan_results(job_id, format_type):
    scan_job = ScanJob.query.get_or_404(job_id)
    
    if scan_job.scan_type == 'rustscan':
        if format_type == 'greppable':
            if not scan_job.rustscan_output:
                flash('Результаты недоступны', 'danger')
                return redirect(url_for('scans_page'))
            
            timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
            filename = f'rustscan_{timestamp}.txt'
            
            return Response(
                scan_job.rustscan_output,
                mimetype='text/plain',
                headers={
                    'Content-Disposition': f'attachment; filename={filename}'
                }
            )
    
    elif scan_job.scan_type == 'nmap':
        file_path = None
        mimetype = 'text/plain'
        filename = ''
        
        if format_type == 'xml':
            file_path = scan_job.nmap_xml_path
            mimetype = 'application/xml'
            filename = 'nmap_results.xml'
        elif format_type == 'greppable':
            file_path = scan_job.nmap_grep_path
            mimetype = 'text/plain'
            filename = 'nmap_results.gnmap'
        elif format_type == 'normal':
            file_path = scan_job.nmap_normal_path
            mimetype = 'text/plain'
            filename = 'nmap_results.txt'
        
        if file_path and os.path.exists(file_path):
            return send_file(
                file_path,
                mimetype=mimetype,
                as_attachment=True,
                download_name=filename
            )
        else:
            flash('Файл результатов не найден', 'danger')
            return redirect(url_for('scans_page'))
    
    flash('Неподдерживаемый формат', 'danger')
    return redirect(url_for('scans_page'))


@app.route('/utilities')
def utilities():
    all_groups = Group.query.all()
    group_tree = build_group_tree(all_groups)
    return render_template('utilities.html', group_tree=group_tree, all_groups=all_groups)


@app.route('/utilities/nmap-to-rustscan', methods=['POST'])
def nmap_to_rustscan():
    if 'file' not in request.files:
        return jsonify({'error': 'Файл не найден'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'Файл не выбран'}), 400
    
    if not file.filename.endswith('.xml'):
        return jsonify({'error': 'Требуется XML файл'}), 400
    
    try:
        tree = ET.parse(file.stream)
        root = tree.getroot()
        
        ips = []
        for host in root.findall('host'):
            status = host.find('status')
            if status is not None and status.get('state') == 'up':
                addr = host.find('address')
                if addr is not None:
                    ip = addr.get('addr')
                    if ip:
                        ips.append(ip)
        
        if not ips:
            return jsonify({'error': 'Не найдено активных хостов'}), 400
        
        content = '\n'.join(ips)
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        filename = f'rustscan_targets_{timestamp}.txt'
        
        return Response(
            content,
            mimetype='text/plain',
            headers={
                'Content-Disposition': f'attachment; filename={filename}'
            }
        )
        
    except Exception as e:
        return jsonify({'error': f'Ошибка обработки: {str(e)}'}), 500


@app.route('/utilities/extract-ports', methods=['POST'])
def extract_ports():
    if 'file' not in request.files:
        return jsonify({'error': 'Файл не найден'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'Файл не выбран'}), 400
    
    try:
        tree = ET.parse(file.stream)
        root = tree.getroot()
        
        all_ports = set()
        host_ports = {}
        
        for host in root.findall('host'):
            status = host.find('status')
            if status is not None and status.get('state') == 'up':
                addr = host.find('address')
                ip = addr.get('addr') if addr is not None else 'unknown'
                
                ports = []
                ports_elem = host.find('ports')
                if ports_elem is not None:
                    for port in ports_elem.findall('port'):
                        state = port.find('state')
                        if state is not None and state.get('state') == 'open':
                            port_id = port.get('portid')
                            protocol = port.get('protocol')
                            service = port.find('service')
                            service_name = service.get('name') if service is not None else ''
                            
                            port_str = f"{port_id}/{protocol}"
                            if service_name:
                                port_str += f" ({service_name})"
                            
                            ports.append(port_str)
                            all_ports.add(port_id)
                
                if ports:
                    host_ports[ip] = ports
        
        content = "=" * 60 + "\n"
        content += "NMAP PORTS EXTRACTION REPORT\n"
        content += f"Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}\n"
        content += "=" * 60 + "\n\n"
        
        content += f"Total hosts: {len(host_ports)}\n"
        content += f"Unique ports: {len(all_ports)}\n\n"
        
        content += "-" * 60 + "\n"
        content += "UNIQUE PORTS (for rustscan -p):\n"
        content += "-" * 60 + "\n"
        content += ','.join(sorted(all_ports, key=int)) + "\n\n"
        
        content += "-" * 60 + "\n"
        content += "HOSTS WITH PORTS:\n"
        content += "-" * 60 + "\n"
        for ip, ports in host_ports.items():
            content += f"\n{ip}:\n"
            for port in ports:
                content += f"  - {port}\n"
        
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        filename = f'nmap_ports_report_{timestamp}.txt'
        
        return Response(
            content,
            mimetype='text/plain',
            headers={
                'Content-Disposition': f'attachment; filename={filename}'
            }
        )
        
    except Exception as e:
        return jsonify({'error': f'Ошибка обработки: {str(e)}'}), 500


@app.route('/scan', methods=['POST'])
def import_scan():
    if 'file' not in request.files:
        flash('Файл не найден', 'danger')
        return redirect(url_for('index'))
    
    file = request.files['file']
    group_id = request.form.get('group_id')
    if group_id == '':
        group_id = None
    
    if file and file.filename:
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        try:
            parsed_assets = parse_nmap_xml(filepath)
            updated_count = 0
            created_count = 0
            
            for data in parsed_assets:
                existing = Asset.query.filter_by(ip_address=data['ip_address']).first()
                if existing:
                    existing.hostname = data['hostname']
                    existing.os_info = data['os_info']
                    existing.open_ports = data['open_ports']
                    existing.last_scanned = datetime.utcnow()
                    existing.status = data['status']
                    if group_id and not existing.group_id:
                        existing.group_id = group_id
                    updated_count += 1
                else:
                    new_asset = Asset(**data, group_id=group_id)
                    db.session.add(new_asset)
                    created_count += 1
            
            db.session.commit()
            flash(f'Успех! Создано: {created_count}, Обновлено: {updated_count}', 'success')
        except Exception as e:
            flash(f'Ошибка парсинга: {str(e)}', 'danger')
        finally:
            os.remove(filepath)
    
    return redirect(url_for('index'))

# ═══════════════════════════════════════════════════════════════
# API СТАТУС АКТИВНЫХ СКАНИРОВАНИЙ
# ═══════════════════════════════════════════════════════════════

@app.route('/api/scans/status')
def get_active_scans_status():
    """Получение статуса активных сканирований для polling"""
    # Получаем только активные задания (running или pending)
    active_jobs = ScanJob.query.filter(
        ScanJob.status.in_(['pending', 'running'])
    ).order_by(ScanJob.created_at.desc()).limit(10).all()
    
    return jsonify({
        'active': [job.to_dict() for job in active_jobs],
        'total_active': len(active_jobs)
    })


if __name__ == '__main__':
    with app.app_context():
        print("📁 Текущая директория:", os.getcwd())
        print("🔍 Путь к БД:", app.config['SQLALCHEMY_DATABASE_URI'])
        
        try:
            print("🔄 Инициализация базы данных...")
            db.create_all()
            print("✅ База данных создана/проверена")
            
            if not Group.query.first():
                print("📦 Создаём тестовую группу...")
                db.session.add(Group(name="Сеть"))
                db.session.commit()
                print("✅ Тестовая группа создана")
        except Exception as e:
            print(f"⚠️ Предупреждение при инициализации БД: {e}")
    
    print("🚀 Запуск сервера...")
    app.run(debug=True, host='127.0.0.1', port=5000)
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

### 📄 `static/css/style.css`

```css
/* ═══════════════════════════════════════════════════════════════
   BOOTSTRAP 5 THEME - LIGHT & DARK MODE
   Clean, Modern, Professional Design
   ═══════════════════════════════════════════════════════════════ */

:root {
    /* Bootstrap 5 Color Palette - Light Theme */
    --bs-primary: #0d6efd;
    --bs-secondary: #6c757d;
    --bs-success: #198754;
    --bs-info: #0dcaf0;
    --bs-warning: #ffc107;
    --bs-danger: #dc3545;
    --bs-light: #f8f9fa;
    --bs-dark: #212529;
    
    /* Custom Variables - Light */
    --bg-body: #f8f9fa;
    --bg-card: #ffffff;
    --bg-sidebar: #ffffff;
    --bg-hover: #f1f3f5;
    --bg-input: #ffffff;
    
    --text-primary: #212529;
    --text-secondary: #6c757d;
    --text-muted: #adb5bd;
    
    --border-color: #dee2e6;
    --shadow-sm: 0 0.125rem 0.25rem rgba(0, 0, 0, 0.075);
    --shadow-md: 0 0.5rem 1rem rgba(0, 0, 0, 0.15);
    --shadow-lg: 0 1rem 3rem rgba(0, 0, 0, 0.175);
    
    --font-primary: system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
    --font-mono: SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
}

[data-bs-theme="dark"] {
    /* Bootstrap 5 Color Palette - Dark Theme */
    --bs-primary: #3d8bfd;
    --bs-secondary: #6c757d;
    --bs-success: #20c997;
    --bs-info: #6edff6;
    --bs-warning: #ffda6a;
    --bs-danger: #ea868f;
    --bs-light: #212529;
    --bs-dark: #f8f9fa;
    
    /* Custom Variables - Dark */
    --bg-body: #212529;
    --bg-card: #2b3035;
    --bg-sidebar: #2b3035;
    --bg-hover: #343a40;
    --bg-input: #2b3035;
    
    --text-primary: #f8f9fa;
    --text-secondary: #adb5bd;
    --text-muted: #6c757d;
    
    --border-color: #495057;
    --shadow-sm: 0 0.125rem 0.25rem rgba(0, 0, 0, 0.3);
    --shadow-md: 0 0.5rem 1rem rgba(0, 0, 0, 0.4);
    --shadow-lg: 0 1rem 3rem rgba(0, 0, 0, 0.5);
}

/* ═══════════════════════════════════════════════════════════════
   BASE STYLES
   ═══════════════════════════════════════════════════════════════ */

body {
    background-color: var(--bg-body);
    color: var(--text-primary);
    font-family: var(--font-primary);
    font-size: 0.9375rem;
    line-height: 1.5;
    transition: background-color 0.3s ease, color 0.3s ease;
}

/* Scrollbar */
::-webkit-scrollbar {
    width: 8px;
    height: 8px;
}

::-webkit-scrollbar-track {
    background: var(--bg-body);
}

::-webkit-scrollbar-thumb {
    background: var(--bs-secondary);
    border-radius: 4px;
}

::-webkit-scrollbar-thumb:hover {
    background: var(--bs-primary);
}

/* ═══════════════════════════════════════════════════════════════
   LAYOUT
   ═══════════════════════════════════════════════════════════════ */

.sidebar {
    min-height: 100vh;
    background: var(--bg-sidebar);
    border-right: 1px solid var(--border-color);
    transition: all 0.3s ease;
}

.main-content {
    padding: 1.5rem;
}

/* ═══════════════════════════════════════════════════════════════
   NAVBAR
   ═══════════════════════════════════════════════════════════════ */

.navbar {
    background: var(--bg-card) !important;
    border: 1px solid var(--border-color);
    border-radius: 0.5rem;
    box-shadow: var(--shadow-sm);
}

.navbar-brand {
    font-weight: 600;
    color: var(--bs-primary) !important;
}

/* ═══════════════════════════════════════════════════════════════
   CARDS
   ═══════════════════════════════════════════════════════════════ */

.card {
    background: var(--bg-card);
    border: 1px solid var(--border-color);
    border-radius: 0.5rem;
    box-shadow: var(--shadow-sm);
    transition: all 0.3s ease;
}

.card:hover {
    box-shadow: var(--shadow-md);
}

.card-header {
    background: var(--bg-body);
    border-bottom: 1px solid var(--border-color);
    font-weight: 600;
    padding: 0.75rem 1rem;
}

.card-body {
    padding: 1rem;
}

/* ═══════════════════════════════════════════════════════════════
   BUTTONS
   ═══════════════════════════════════════════════════════════════ */

.btn {
    font-weight: 500;
    border-radius: 0.375rem;
    padding: 0.5rem 1rem;
    transition: all 0.2s ease;
}

.btn-primary {
    background: var(--bs-primary);
    border-color: var(--bs-primary);
}

.btn-primary:hover {
    background: var(--bs-primary);
    opacity: 0.9;
    transform: translateY(-1px);
}

.btn-outline-primary {
    color: var(--bs-primary);
    border-color: var(--bs-primary);
}

.btn-outline-primary:hover {
    background: var(--bs-primary);
    color: #fff;
}

.btn-sm {
    padding: 0.25rem 0.5rem;
    font-size: 0.8125rem;
}

/* ═══════════════════════════════════════════════════════════════
   TABLES
   ═══════════════════════════════════════════════════════════════ */

.table {
    color: var(--text-primary);
    margin-bottom: 0;
}

.table thead {
    background: var(--bg-body);
    border-bottom: 2px solid var(--border-color);
}

.table thead th {
    color: var(--text-secondary);
    font-weight: 600;
    font-size: 0.8125rem;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    padding: 0.75rem 1rem;
    border: none;
}

.table tbody tr {
    border-bottom: 1px solid var(--border-color);
    transition: background-color 0.15s ease;
}

.table tbody tr:hover {
    background-color: var(--bg-hover);
}

/* ═══════════════════════════════════════════════════════════════
   BADGES
   ═══════════════════════════════════════════════════════════════ */

.badge {
    font-weight: 500;
    font-size: 0.75rem;
    padding: 0.35em 0.65em;
    border-radius: 0.375rem;
}

/* ═══════════════════════════════════════════════════════════════
   FORMS
   ═══════════════════════════════════════════════════════════════ */

.form-control,
.form-select {
    background: var(--bg-input);
    border: 1px solid var(--border-color);
    color: var(--text-primary);
    border-radius: 0.375rem;
    padding: 0.5rem 0.75rem;
    transition: all 0.2s ease;
}

.form-control:focus,
.form-select:focus {
    background: var(--bg-input);
    border-color: var(--bs-primary);
    color: var(--text-primary);
    box-shadow: 0 0 0 0.25rem rgba(13, 110, 253, 0.25);
}

.form-control::placeholder {
    color: var(--text-muted);
}

/* ═══════════════════════════════════════════════════════════════
   TREE GROUPS
   ═══════════════════════════════════════════════════════════════ */

.tree-node {
    cursor: pointer;
    padding: 0.5rem 0.75rem;
    border-radius: 0.375rem;
    user-select: none;
    display: flex;
    align-items: center;
    gap: 0.5rem;
    width: 100%;
    transition: all 0.2s ease;
    border-left: 3px solid transparent;
    font-size: 0.875rem;
    color: var(--text-secondary);
}

.tree-node:hover {
    background-color: var(--bg-hover);
    border-left-color: var(--bs-primary);
    color: var(--text-primary);
}

.tree-node.active {
    background: rgba(13, 110, 253, 0.1);
    border-left-color: var(--bs-primary);
    color: var(--bs-primary);
}

.nested {
    display: none;
    margin-left: 1.5rem;
    border-left: 1px dashed var(--border-color);
    padding-left: 0.5rem;
}

.nested.active {
    display: block;
}

.caret {
    cursor: pointer;
    user-select: none;
    display: inline-flex;
    align-items: center;
}

.caret::before {
    content: "▶";
    display: inline-block;
    margin-right: 0.375rem;
    transform: rotate(0deg);
    transition: transform 0.2s;
    font-size: 0.625rem;
    color: var(--text-muted);
}

.caret-down::before {
    transform: rotate(90deg);
}

/* ═══════════════════════════════════════════════════════════════
   THEME TOGGLE
   ═══════════════════════════════════════════════════════════════ */

.theme-toggle {
    background: var(--bg-body);
    border: 1px solid var(--border-color);
    color: var(--text-primary);
    width: 40px;
    height: 40px;
    border-radius: 0.375rem;
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    transition: all 0.2s ease;
}

.theme-toggle:hover {
    background: var(--bg-hover);
    border-color: var(--bs-primary);
    color: var(--bs-primary);
    transform: scale(1.05);
}

/* ═══════════════════════════════════════════════════════════════
   CONTEXT MENU
   ═══════════════════════════════════════════════════════════════ */

.context-menu {
    display: none;
    position: absolute;
    z-index: 1050;
    min-width: 220px;
    background: var(--bg-card);
    border: 1px solid var(--border-color);
    box-shadow: var(--shadow-lg);
    border-radius: 0.5rem;
    padding: 0.5rem 0;
    animation: fadeIn 0.15s ease-out;
}

@keyframes fadeIn {
    from {
        opacity: 0;
        transform: translateY(-8px);
    }
    to {
        opacity: 1;
        transform: translateY(0);
    }
}

.context-menu-item {
    display: flex;
    align-items: center;
    gap: 0.625rem;
    width: 100%;
    padding: 0.5rem 0.875rem;
    color: var(--text-primary);
    text-decoration: none;
    background: transparent;
    border: 0;
    cursor: pointer;
    font-size: 0.875rem;
    transition: all 0.15s ease;
}

.context-menu-item:hover {
    background: var(--bg-hover);
    color: var(--bs-primary);
}

.context-menu-item i {
    width: 1.125rem;
    text-align: center;
    color: var(--text-muted);
}

.context-menu-item:hover i {
    color: var(--bs-primary);
}

.context-menu-divider {
    height: 0;
    margin: 0.375rem 0;
    border-top: 1px solid var(--border-color);
}

/* ═══════════════════════════════════════════════════════════════
   FILTER BUILDER
   ═══════════════════════════════════════════════════════════════ */

.filter-group {
    border: 1px solid var(--border-color);
    padding: 1rem;
    border-radius: 0.5rem;
    margin-bottom: 0.75rem;
    background: var(--bg-card);
    position: relative;
    box-shadow: var(--shadow-sm);
}

.filter-group::before {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    width: 3px;
    height: 100%;
    background: var(--bs-primary);
    border-radius: 0.5rem 0 0 0.5rem;
}

.filter-condition {
    display: flex;
    gap: 0.5rem;
    align-items: center;
    margin-bottom: 0.5rem;
    background: var(--bg-body);
    padding: 0.5rem 0.625rem;
    border-radius: 0.375rem;
    flex-wrap: wrap;
    border: 1px solid transparent;
    transition: border-color 0.2s ease;
}

.filter-condition:hover {
    border-color: var(--bs-primary);
}

/* ═══════════════════════════════════════════════════════════════
   TIMELINE (Asset History)
   ═══════════════════════════════════════════════════════════════ */

.timeline {
    position: relative;
    padding: 1.25rem 0;
}

.timeline::before {
    content: '';
    position: absolute;
    left: 1.875rem;
    top: 0;
    bottom: 0;
    width: 2px;
    background: var(--border-color);
}

.timeline-item {
    position: relative;
    padding-left: 4.375rem;
    margin-bottom: 1.875rem;
}

.timeline-marker {
    position: absolute;
    left: 0;
    width: 3.75rem;
    text-align: right;
    padding-right: 0.9375rem;
    font-size: 0.8125rem;
    color: var(--text-muted);
}

.timeline-dot {
    position: absolute;
    left: 1.5rem;
    top: 0.3125rem;
    width: 0.875rem;
    height: 0.875rem;
    border-radius: 50%;
    background: var(--bs-primary);
    border: 3px solid var(--bg-card);
    box-shadow: 0 0 0 3px var(--bs-primary);
}

.timeline-dot.port-added { background: var(--bs-success); box-shadow: 0 0 0 3px var(--bs-success); }
.timeline-dot.port-removed { background: var(--bs-danger); box-shadow: 0 0 0 3px var(--bs-danger); }
.timeline-dot.service-detected { background: var(--bs-info); box-shadow: 0 0 0 3px var(--bs-info); }
.timeline-dot.os-changed { background: var(--bs-warning); box-shadow: 0 0 0 3px var(--bs-warning); }
.timeline-dot.asset-created { background: #9b59b6; box-shadow: 0 0 0 3px #9b59b6; }

.timeline-content {
    background: var(--bg-card);
    border: 1px solid var(--border-color);
    border-radius: 0.5rem;
    padding: 0.9375rem;
    transition: all 0.3s ease;
}

.timeline-content:hover {
    box-shadow: var(--shadow-md);
}

/* ═══════════════════════════════════════════════════════════════
   SERVICE INVENTORY
   ═══════════════════════════════════════════════════════════════ */

.service-card {
    transition: all 0.3s ease;
    border: 1px solid var(--border-color) !important;
}

.service-card:hover {
    transform: translateY(-2px);
    box-shadow: var(--shadow-md);
}

.cpe-badge {
    font-family: var(--font-mono);
    font-size: 0.75rem;
    background: var(--bg-body);
    padding: 0.125rem 0.375rem;
    border-radius: 0.25rem;
}

.script-output {
    background: var(--bg-body);
    border: 1px solid var(--border-color);
    border-radius: 0.375rem;
    padding: 0.625rem;
    font-family: var(--font-mono);
    font-size: 0.8125rem;
    max-height: 12.5rem;
    overflow-y: auto;
    margin-top: 0.625rem;
}

/* ═══════════════════════════════════════════════════════════════
   ALERTS
   ═══════════════════════════════════════════════════════════════ */

.alert {
    border-radius: 0.5rem;
    border: 1px solid;
    font-size: 0.875rem;
    padding: 0.75rem 1rem;
}

.alert-fixed {
    position: fixed;
    top: 1.25rem;
    right: 1.25rem;
    z-index: 9999;
    min-width: 21.875rem;
    animation: slideInRight 0.3s ease-out;
    box-shadow: var(--shadow-lg);
}

@keyframes slideInRight {
    from {
        opacity: 0;
        transform: translateX(6.25rem);
    }
    to {
        opacity: 1;
        transform: translateX(0);
    }
}

/* ═══════════════════════════════════════════════════════════════
   PROGRESS BARS
   ═══════════════════════════════════════════════════════════════ */

.progress {
    height: 0.5rem;
    background: var(--bg-body);
    border-radius: 0.5rem;
    overflow: hidden;
}

.progress-bar {
    background: var(--bs-primary);
    transition: width 0.3s ease;
}

/* ═══════════════════════════════════════════════════════════════
   MODALS
   ═══════════════════════════════════════════════════════════════ */

.modal-content {
    background: var(--bg-card);
    border: none;
    box-shadow: var(--shadow-lg);
    border-radius: 0.5rem;
}

.modal-header {
    border-bottom: 1px solid var(--border-color);
    background: var(--bg-body);
    padding: 0.875rem 1.25rem;
    border-radius: 0.5rem 0.5rem 0 0;
}

.modal-title {
    color: var(--text-primary);
    font-weight: 600;
    font-size: 1rem;
}

.modal-body {
    color: var(--text-primary);
    padding: 1.25rem;
}

.modal-footer {
    border-top: 1px solid var(--border-color);
    background: var(--bg-body);
    padding: 0.875rem 1.25rem;
    border-radius: 0 0 0.5rem 0.5rem;
}

/* ═══════════════════════════════════════════════════════════════
   RESPONSIVE
   ═══════════════════════════════════════════════════════════════ */

@media (max-width: 768px) {
    .sidebar {
        display: none !important;
    }
    
    .main-content {
        padding: 1rem;
    }
    
    .navbar {
        border-radius: 0;
    }
    
    .alert-fixed {
        min-width: 17.5rem;
        left: 0.625rem;
        right: 0.625rem;
    }
}

/* ═══════════════════════════════════════════════════════════════
   ACCESSIBILITY
   ═══════════════════════════════════════════════════════════════ */

@media (prefers-reduced-motion: reduce) {
    *,
    *::before,
    *::after {
        animation-duration: 0.01ms !important;
        transition-duration: 0.01ms !important;
    }
}

a:focus,
button:focus,
input:focus,
select:focus {
    outline: 2px solid var(--bs-primary);
    outline-offset: 2px;
}

/* ═══════════════════════════════════════════════════════════════
   UTILITIES
   ═══════════════════════════════════════════════════════════════ */

.theme-transition * {
    transition: background-color 0.3s ease, 
                color 0.3s ease, 
                border-color 0.3s ease, 
                box-shadow 0.3s ease !important;
}

.cursor-pointer {
    cursor: pointer;
}

.text-truncate-ellipsis {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}
```

### 📄 `static/js/main.js`

```javascript
// ═══════════════════════════════════════════════════════════════
// ГЛОБАЛЬНЫЕ ПЕРЕМЕННЫЕ
// ═══════════════════════════════════════════════════════════════

let currentGroupId = null;
let contextMenu = null;
let editModal, moveModal, deleteModal, bulkDeleteModalInstance;
let lastSelectedIndex = -1;
let selectedAssetIds = new Set();

const FILTER_FIELDS = [
    { value: 'ip_address', text: 'IP Адрес' },
    { value: 'hostname', text: 'Hostname' },
    { value: 'os_info', text: 'ОС' },
    { value: 'open_ports', text: 'Порты' },
    { value: 'status', text: 'Статус' },
    { value: 'notes', text: 'Заметки' }
];

const FILTER_OPS = [
    { value: 'eq', text: '=' },
    { value: 'ne', text: '≠' },
    { value: 'like', text: 'содержит' },
    { value: 'in', text: 'в списке' }
];

// ═══════════════════════════════════════════════════════════════
// ТЕМА
// ═══════════════════════════════════════════════════════════════

function initTheme() {
    const savedTheme = localStorage.getItem('theme') || 'light';
    const html = document.documentElement;
    html.setAttribute('data-bs-theme', savedTheme === 'dark' ? 'dark' : 'light');
    updateThemeIcon(savedTheme);
}

function toggleTheme() {
    const html = document.documentElement;
    const currentTheme = html.getAttribute('data-bs-theme');
    const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
    
    document.body.classList.add('theme-transition');
    html.setAttribute('data-bs-theme', newTheme);
    localStorage.setItem('theme', newTheme);
    updateThemeIcon(newTheme);
    
    setTimeout(() => {
        document.body.classList.remove('theme-transition');
    }, 300);
}

function updateThemeIcon(theme) {
    const toggle = document.querySelector('.theme-toggle');
    if (!toggle) return;
    const moonIcon = toggle.querySelector('.bi-moon');
    const sunIcon = toggle.querySelector('.bi-sun');
    if (theme === 'dark') {
        moonIcon.style.display = 'none';
        sunIcon.style.display = 'block';
    } else {
        moonIcon.style.display = 'block';
        sunIcon.style.display = 'none';
    }
}

// ═══════════════════════════════════════════════════════════════
// ДЕРЕВО ГРУПП
// ═══════════════════════════════════════════════════════════════

function initTreeTogglers() {
    const groupTree = document.getElementById('group-tree');
    if (!groupTree) return;
    
    const newGroupTree = groupTree.cloneNode(true);
    groupTree.parentNode.replaceChild(newGroupTree, groupTree);
    
    newGroupTree.addEventListener('click', function(e) {
        const treeNode = e.target.closest('.tree-node');
        if (!treeNode) return;
        
        const groupId = treeNode.dataset.id;
        
        if (e.target.classList.contains('caret') || e.target.closest('.caret')) {
            e.preventDefault();
            e.stopPropagation();
            const nested = treeNode.querySelector(".nested");
            if (nested) {
                nested.classList.toggle("active");
                const caret = treeNode.querySelector('.caret');
                if (caret) caret.classList.toggle("caret-down");
            }
            return;
        }
        
        filterByGroup(groupId);
    });
}

function filterByGroup(groupId) {
    document.querySelectorAll('.tree-node').forEach(el => el.classList.remove('active'));
    const activeNode = document.querySelector(`.tree-node[data-id="${groupId}"]`);
    if (activeNode) activeNode.classList.add('active');
    
    function getAllChildGroupIds(parentId, flatGroups) {
        const result = [];
        const children = flatGroups.filter(g => g.parent_id === parentId);
        children.forEach(child => {
            result.push(child.id);
            const grandchildren = getAllChildGroupIds(child.id, flatGroups);
            result.push(...grandchildren);
        });
        return result;
    }
    
    fetch('/api/groups/tree')
        .then(r => r.json())
        .then(data => {
            const currentGroupId = parseInt(groupId);
            const allGroupIds = [currentGroupId];
            const childIds = getAllChildGroupIds(currentGroupId, data.flat);
            allGroupIds.push(...childIds);
            
            const promises = allGroupIds.map(id => 
                fetch(`/api/assets?group_id=${id}`).then(r => r.json())
            );
            
            Promise.all(promises)
                .then(results => {
                    const allAssets = [].concat(...results);
                    const uniqueAssets = Array.from(
                        new Map(allAssets.map(item => [item.id, item])).values()
                    );
                    renderAssets(uniqueAssets);
                })
                .catch(error => console.error("Error:", error));
        });
}

// ═══════════════════════════════════════════════════════════════
// КОНТЕКСТНОЕ МЕНЮ
// ═══════════════════════════════════════════════════════════════

function attachContextMenuListeners() {
    if (!contextMenu) return;
    
    document.addEventListener('contextmenu', (e) => {
        const node = e.target.closest('.tree-node');
        if (node) {
            e.preventDefault();
            currentGroupId = node.dataset.id;
            contextMenu.style.display = 'block';
            contextMenu.style.left = `${e.pageX}px`;
            contextMenu.style.top = `${e.pageY}px`;
            
            const rect = contextMenu.getBoundingClientRect();
            if (rect.right > window.innerWidth) contextMenu.style.left = `${e.pageX - rect.width}px`;
            if (rect.bottom > window.innerHeight) contextMenu.style.top = `${e.pageY - rect.height}px`;
        } else {
            contextMenu.style.display = 'none';
        }
    });
}

document.addEventListener('click', () => {
    if (contextMenu) contextMenu.style.display = 'none';
});

// ═══════════════════════════════════════════════════════════════
// API ЗАПРОСЫ
// ═══════════════════════════════════════════════════════════════

async function apiCreateGroup(name, parentId, filterQuery) {
    const res = await fetch('/api/groups', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({name, parent_id: parentId, filter_query: filterQuery})
    });
    if (!res.ok) {
        const err = await res.json();
        throw new Error(err.error || 'Failed');
    }
    return await res.json();
}

async function apiUpdateGroup(id, data) {
    const res = await fetch(`/api/groups/${id}`, {
        method: 'PUT',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(data)
    });
    if (!res.ok) {
        const err = await res.json();
        throw new Error(err.error || 'Failed');
    }
    return await res.json();
}

async function apiDeleteGroup(id, moveToId) {
    const url = moveToId ? `/api/groups/${id}?move_to=${moveToId}` : `/api/groups/${id}`;
    const res = await fetch(url, { method: 'DELETE' });
    if (!res.ok) throw new Error('Failed');
    return await res.json();
}

async function loadGroupsTree() {
    try {
        const res = await fetch('/api/groups/tree');
        if (!res.ok) throw new Error('Failed');
        return await res.json();
    } catch (error) {
        alert('Ошибка загрузки дерева групп');
        return { tree: [], flat: [] };
    }
}

// ═══════════════════════════════════════════════════════════════
// МОДАЛЬНЫЕ ОКНА
// ═══════════════════════════════════════════════════════════════

function showCreateGroupModal(parentId) {
    document.getElementById('edit-group-id').value = '';
    document.getElementById('edit-group-name').value = '';
    document.getElementById('edit-group-parent').value = parentId || '';
    document.getElementById('groupEditTitle').textContent = parentId ? 'Новая подгруппа' : 'Новая группа';
    document.getElementById('edit-group-dynamic').checked = false;
    document.getElementById('dynamic-filter-section').style.display = 'none';
    initGroupFilterRoot();
    if (editModal) editModal.show();
}

function showRenameModal(id) {
    const node = document.querySelector(`.tree-node[data-id="${id}"]`);
    if (!node) return;
    
    document.getElementById('edit-group-id').value = id;
    document.getElementById('edit-group-name').value = node.textContent.split('(')[0].trim();
    document.getElementById('groupEditTitle').textContent = 'Редактировать группу';
    document.getElementById('edit-group-dynamic').checked = false;
    document.getElementById('dynamic-filter-section').style.display = 'none';
    initGroupFilterRoot();
    if (editModal) editModal.show();
}

const groupEditForm = document.getElementById('groupEditForm');
if (groupEditForm) {
    groupEditForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        try {
            const id = document.getElementById('edit-group-id').value;
            const name = document.getElementById('edit-group-name').value;
            const parentId = document.getElementById('edit-group-parent').value;
            const isDynamic = document.getElementById('edit-group-dynamic').checked;
            
            let filterQuery = null;
            if (isDynamic) {
                const filterStruct = buildGroupFilterJSON();
                if (filterStruct.conditions && filterStruct.conditions.length > 0) {
                    filterQuery = JSON.stringify(filterStruct);
                }
            }
            
            if (id) {
                await apiUpdateGroup(id, { name, parent_id: parentId || null, filter_query: filterQuery });
            } else {
                await apiCreateGroup(name, parentId || null, filterQuery);
            }
            
            if (editModal) editModal.hide();
            location.reload();
        } catch (error) {
            alert(`Ошибка: ${error.message}`);
        }
    });
}

async function showMoveModal(id) {
    const data = await loadGroupsTree();
    const select = document.getElementById('move-group-parent');
    select.innerHTML = '<option value="">-- Корень --</option>';
    
    data.flat.forEach(g => {
        if (g.id != id) {
            const opt = document.createElement('option');
            opt.value = g.id;
            opt.textContent = g.name;
            select.appendChild(opt);
        }
    });
    
    document.getElementById('move-group-id').value = id;
    if (moveModal) moveModal.show();
}

const groupMoveForm = document.getElementById('groupMoveForm');
if (groupMoveForm) {
    groupMoveForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        try {
            const id = document.getElementById('move-group-id').value;
            const parentId = document.getElementById('move-group-parent').value;
            await apiUpdateGroup(id, {parent_id: parentId});
            if (moveModal) moveModal.hide();
            location.reload();
        } catch (error) {
            alert('Ошибка: ' + error.message);
        }
    });
}

async function showDeleteModal(id) {
    document.getElementById('delete-group-id').value = id;
    const data = await loadGroupsTree();
    const select = document.getElementById('delete-move-assets');
    select.innerHTML = '<option value="">-- Не переносить --</option>';
    
    data.flat.forEach(g => {
        if (g.id != id) {
            const opt = document.createElement('option');
            opt.value = g.id;
            opt.textContent = g.name;
            select.appendChild(opt);
        }
    });
    
    if (deleteModal) deleteModal.show();
}

async function confirmDeleteGroup() {
    try {
        const id = document.getElementById('delete-group-id').value;
        const moveTo = document.getElementById('delete-move-assets').value;
        await apiDeleteGroup(id, moveTo || null);
        if (deleteModal) deleteModal.hide();
        location.reload();
    } catch (error) {
        alert('Ошибка: ' + error.message);
    }
}

// ═══════════════════════════════════════════════════════════════
// ВЫДЕЛЕНИЕ АКТИВОВ
// ═══════════════════════════════════════════════════════════════

function initAssetSelection() {
    const tbody = document.getElementById('assets-body');
    if (!tbody) return;
    
    const selectAllCheckbox = document.getElementById('select-all');
    if (selectAllCheckbox) {
        selectAllCheckbox.addEventListener('change', function() {
            const checkboxes = tbody.querySelectorAll('.asset-checkbox');
            const isChecked = this.checked;
            
            checkboxes.forEach(cb => {
                cb.checked = isChecked;
                toggleRowSelection(cb.closest('tr'), isChecked);
                if (isChecked) selectedAssetIds.add(cb.value);
                else selectedAssetIds.delete(cb.value);
            });
            
            if (isChecked && checkboxes.length > 0) {
                lastSelectedIndex = getRowIndex(checkboxes[checkboxes.length - 1].closest('tr'));
            } else {
                lastSelectedIndex = -1;
            }
            
            updateBulkToolbar();
            updateSelectAllCheckbox();
        });
    }
    
    tbody.addEventListener('change', (e) => {
        if (e.target.classList.contains('asset-checkbox')) {
            handleCheckboxChange(e.target);
        }
    });
    
    tbody.addEventListener('mousedown', (e) => {
        const row = e.target.closest('.asset-row');
        if (!row) return;
        if (e.shiftKey && !e.target.closest('a, button, .asset-checkbox, input, select, textarea')) {
            e.preventDefault();
            e.stopPropagation();
            return false;
        }
    });
    
    tbody.addEventListener('click', (e) => {
        const row = e.target.closest('.asset-row');
        if (!row) return;
        if (e.target.closest('a, button, .asset-checkbox')) return;
        const checkbox = row.querySelector('.asset-checkbox');
        if (checkbox) {
            if (e.shiftKey && lastSelectedIndex >= 0) {
                e.preventDefault();
                selectRange(lastSelectedIndex, getRowIndex(row));
            } else {
                checkbox.checked = !checkbox.checked;
                handleCheckboxChange(checkbox);
            }
        }
    });
}

function handleCheckboxChange(checkbox) {
    const row = checkbox.closest('tr');
    const assetId = checkbox.value;
    const isChecked = checkbox.checked;
    
    toggleRowSelection(row, isChecked);
    
    if (isChecked) {
        selectedAssetIds.add(assetId);
        lastSelectedIndex = getRowIndex(row);
    } else {
        selectedAssetIds.delete(assetId);
        if (lastSelectedIndex === getRowIndex(row)) lastSelectedIndex = -1;
    }
    
    updateBulkToolbar();
    updateSelectAllCheckbox();
}

function toggleRowSelection(row, isSelected) {
    if (isSelected) row.classList.add('selected');
    else row.classList.remove('selected');
}

function getRowIndex(row) {
    const rows = Array.from(document.querySelectorAll('#assets-body .asset-row'));
    return rows.indexOf(row);
}

function selectRange(startIndex, endIndex) {
    const [start, end] = startIndex <= endIndex ? [startIndex, endIndex] : [endIndex, startIndex];
    const rows = document.querySelectorAll('#assets-body .asset-row');
    for (let i = start; i <= end; i++) {
        if (rows[i]) {
            const checkbox = rows[i].querySelector('.asset-checkbox');
            if (checkbox && !checkbox.checked) {
                checkbox.checked = true;
                toggleRowSelection(rows[i], true);
                selectedAssetIds.add(checkbox.value);
            }
        }
    }
    updateBulkToolbar();
    updateSelectAllCheckbox();
}

function selectAllVisibleAssets() {
    const checkboxes = document.querySelectorAll('#assets-body .asset-checkbox');
    checkboxes.forEach(cb => {
        if (!cb.checked) {
            cb.checked = true;
            toggleRowSelection(cb.closest('tr'), true);
            selectedAssetIds.add(cb.value);
        }
    });
    updateBulkToolbar();
    updateSelectAllCheckbox();
}

function clearSelection() {
    const checkboxes = document.querySelectorAll('#assets-body .asset-checkbox:checked');
    checkboxes.forEach(cb => {
        cb.checked = false;
        toggleRowSelection(cb.closest('tr'), false);
        selectedAssetIds.delete(cb.value);
    });
    selectedAssetIds.clear();
    lastSelectedIndex = -1;
    updateBulkToolbar();
    updateSelectAllCheckbox();
}

function updateSelectAllCheckbox() {
    const selectAll = document.getElementById('select-all');
    const checkboxes = document.querySelectorAll('#assets-body .asset-checkbox');
    const checkedCount = document.querySelectorAll('#assets-body .asset-checkbox:checked').length;
    if (selectAll && checkboxes.length > 0) {
        selectAll.checked = checkedCount === checkboxes.length;
        selectAll.indeterminate = checkedCount > 0 && checkedCount < checkboxes.length;
    }
}

function updateBulkToolbar() {
    const toolbar = document.getElementById('bulk-toolbar');
    const countBadge = document.getElementById('selected-count');
    const count = selectedAssetIds.size;
    if (count > 0) {
        toolbar.style.display = 'flex';
        countBadge.textContent = count;
    } else {
        toolbar.style.display = 'none';
        countBadge.textContent = '0';
    }
}

// ═══════════════════════════════════════════════════════════════
// МАССОВОЕ УДАЛЕНИЕ
// ═══════════════════════════════════════════════════════════════

function confirmBulkDelete() {
    if (selectedAssetIds.size === 0) return;
    const preview = document.getElementById('bulk-delete-preview');
    const countEl = document.getElementById('bulk-delete-count');
    countEl.textContent = selectedAssetIds.size;
    
    const ids = Array.from(selectedAssetIds).slice(0, 5);
    let previewHtml = '<ul class="list-unstyled mb-0">';
    ids.forEach(id => {
        const row = document.querySelector(`.asset-row[data-asset-id="${id}"]`);
        if (row) {
            const ip = row.querySelector('td:nth-child(2)')?.textContent || `ID: ${id}`;
            previewHtml += `<li>• ${ip}</li>`;
        }
    });
    if (selectedAssetIds.size > 5) {
        previewHtml += `<li class="text-muted">... и ещё ${selectedAssetIds.size - 5}</li>`;
    }
    previewHtml += '</ul>';
    preview.innerHTML = previewHtml;
    
    if (bulkDeleteModalInstance) bulkDeleteModalInstance.show();
}

async function executeBulkDelete() {
    const ids = Array.from(selectedAssetIds);
    try {
        ids.forEach(id => {
            const row = document.querySelector(`.asset-row[data-asset-id="${id}"]`);
            if (row) row.classList.add('deleting');
        });
        
        const res = await fetch('/api/assets/bulk-delete', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ids})
        });
        
        if (!res.ok) throw new Error('Failed');
        const result = await res.json();
        
        ids.forEach(id => {
            const row = document.querySelector(`.asset-row[data-asset-id="${id}"]`);
            if (row) row.remove();
        });
        
        clearSelection();
        if (bulkDeleteModalInstance) bulkDeleteModalInstance.hide();
        showFlashMessage(`Удалено активов: ${result.deleted}`, 'success');
        checkEmptyState();
    } catch (error) {
        showFlashMessage('Ошибка при удалении', 'danger');
        document.querySelectorAll('.asset-row.deleting').forEach(row => row.classList.remove('deleting'));
    }
}

function showFlashMessage(text, category) {
    const alert = document.createElement('div');
    alert.className = `alert alert-${category} alert-dismissible fade show alert-fixed`;
    alert.innerHTML = `${text}<button type="button" class="btn-close" data-bs-dismiss="alert"></button>`;
    document.body.appendChild(alert);
    setTimeout(() => { if (alert.parentNode) alert.remove(); }, 3000);
}

function checkEmptyState() {
    const tbody = document.getElementById('assets-body');
    const emptyState = document.getElementById('empty-state');
    const rows = tbody?.querySelectorAll('.asset-row');
    if (emptyState && rows && rows.length === 0) {
        emptyState.style.display = 'block';
    } else if (emptyState) {
        emptyState.style.display = 'none';
    }
}

// === ВЫДЕЛЕНИЕ ГРУППЫ ПО УМОЛЧАНИЮ ===
function setDefaultGroupSelection() {
    // Снимаем все выделения
    document.querySelectorAll('.group-item').forEach(item => {
        item.classList.remove('active');
    });
    
    // 🔥 Выделяем "Без группы" по умолчанию 🔥
    const ungroupedItem = document.querySelector('[data-group-id="ungrouped"]');
    if (ungroupedItem) {
        ungroupedItem.classList.add('active');
        console.log('✅ Default selection: "Без группы"');
    }
}

// === ОТРИСОВКА АКТИВОВ (ГЛОБАЛЬНАЯ ФУНКЦИЯ) ===
window.renderAssets = function(data) {
    const tbody = document.getElementById('assets-body');
    if (!tbody) {
        console.error('❌ assets-body element not found!');
        return;
    }
    
    console.log('🎨 Rendering', data.length, 'assets');
    
    clearSelection();
    lastSelectedIndex = -1;
    
    tbody.innerHTML = '';
    if (data.length === 0) {
        tbody.innerHTML = '<tr><td colspan="7" class="text-center py-4 text-muted"><i class="bi bi-inbox fs-1 d-block mb-2"></i>Ничего не найдено</td></tr>';
        return;
    }
    
    data.forEach(a => {
        const tr = document.createElement('tr');
        tr.className = 'asset-row';
        tr.setAttribute('data-asset-id', a.id);
        tr.innerHTML = `
            <td><input type="checkbox" class="form-check-input asset-checkbox" value="${a.id}"></td>
            <td><a href="/asset/${a.id}" class="text-decoration-none"><strong>${a.ip}</strong></a></td>
            <td>${a.hostname}</td>
            <td><span class="badge bg-info text-dark">${a.os}</span></td>
            <td><small class="text-muted">${a.ports}</small></td>
            <td><span class="badge bg-secondary">${a.group}</span></td>
            <td>
                <a href="/asset/${a.id}" class="btn btn-sm btn-outline-info" title="Подробно"><i class="bi bi-eye"></i></a>
                <a href="/asset/${a.id}/delete" class="btn btn-sm btn-outline-danger" onclick="return confirm('Удалить?')"><i class="bi bi-trash"></i></a>
            </td>
        `;
        tbody.appendChild(tr);
    });
    
    checkEmptyState();
    console.log('✅ Assets rendered successfully');
};

// ═══════════════════════════════════════════════════════════════
// ОСНОВНЫЕ ФУНКЦИИ
// ═══════════════════════════════════════════════════════════════

function applyFilters() {
    const structure = buildFilterJSON();
    const jsonStr = JSON.stringify(structure);
    fetch(`/api/assets?filters=${encodeURIComponent(jsonStr)}`)
        .then(r => r.json())
        .then(data => renderAssets(data));
}

function resetFilters() {
    const root = document.getElementById('filter-root');
    if (root) {
        root.dataset.logic = 'AND';
        const content = root.querySelector('.filter-group-content');
        if (content) content.innerHTML = '';
    }
    loadAssets();
}

function loadAssets() {
    fetch('/api/assets').then(r => r.json()).then(data => renderAssets(data));
}

function loadAnalytics() {
    const groupBy = document.getElementById('analytics-group-by').value;
    const filterRoot = document.getElementById('filter-root');
    const filters = filterRoot && filterRoot.querySelector('.filter-group-content').children.length > 0 
                    ? JSON.stringify(buildFilterJSON()) : '';
    const url = `/api/analytics?group_by=${groupBy}${filters ? '&filters='+encodeURIComponent(filters) : ''}`;
    fetch(url).then(r => r.json()).then(data => {
        const container = document.getElementById('analytics-results');
        if (data.length === 0) {
            container.innerHTML = '<p class="text-muted">Нет данных</p>';
            return;
        }
        let html = '<div class="row">';
        data.forEach(item => {
            html += `<div class="col-md-4 mb-3"><div class="card h-100 border-0 shadow-sm"><div class="card-body text-center">
                <h6 class="card-title text-truncate text-muted">${item.label}</h6>
                <h2 class="display-4 text-primary fw-bold">${item.value}</h2>
                <span class="text-muted small">активов</span></div></div></div>`;
        });
        html += '</div>';
        container.innerHTML = html;
    });
}

// ═══════════════════════════════════════════════════════════════
// КОНСТРУКТОР ФИЛЬТРОВ
// ═══════════════════════════════════════════════════════════════

function buildFilterJSON() {
    return buildNodeJSON(document.getElementById('filter-root'));
}

function buildNodeJSON(node) {
    if (!node) return { logic: 'AND', conditions: [] };
    const logic = node.dataset.logic || 'AND';
    const content = node.querySelector('.filter-group-content');
    const conditions = [];
    if (content) {
        content.children.forEach(child => {
            if (child.dataset.type === 'condition') {
                conditions.push({
                    type: 'condition',
                    field: child.querySelector('.f-field').value,
                    op: child.querySelector('.f-op').value,
                    value: child.querySelector('.f-val').value
                });
            } else if (child.dataset.type === 'group') {
                conditions.push(buildNodeJSON(child));
            }
        });
    }
    return { logic, conditions };
}

function toggleLogic(badge) {
    badge.textContent = badge.textContent === 'AND' ? 'OR' : 'AND';
    badge.className = badge.textContent === 'AND' ? 'badge bg-primary' : 'badge bg-warning text-dark';
    badge.parentElement.parentElement.dataset.logic = badge.textContent;
}

function createConditionElement() {
    const div = document.createElement('div');
    div.className = 'filter-condition';
    div.dataset.type = 'condition';
    const fieldOpts = FILTER_FIELDS.map(f => `<option value="${f.value}">${f.text}</option>`).join('');
    const opOpts = FILTER_OPS.map(o => `<option value="${o.value}">${o.text}</option>`).join('');
    div.innerHTML = `<select class="form-select form-select-sm f-field" style="width:160px">${fieldOpts}</select>
        <select class="form-select form-select-sm f-op" style="width:140px">${opOpts}</select>
        <input type="text" class="form-control form-control-sm f-val" placeholder="Значение" style="flex:1;min-width:120px">
        <button class="btn btn-sm btn-outline-danger" onclick="this.parentElement.remove()">×</button>`;
    return div;
}

function createGroupElement() {
    const group = document.createElement('div');
    group.className = 'filter-group';
    group.dataset.type = 'group';
    group.innerHTML = `<div class="filter-group-header">
        <span class="badge bg-primary" onclick="toggleLogic(this)">AND</span>
        <small class="text-muted ms-2">Вложенная группа</small>
        <button class="btn btn-sm btn-close" onclick="this.parentElement.parentElement.remove()"></button>
    </div><div class="filter-group-content"></div>
    <div class="mt-2">
        <button class="btn btn-xs btn-outline-primary" onclick="addCondition(this)">+ Условие</button>
        <button class="btn btn-xs btn-outline-success" onclick="addGroup(this)">+ Группа</button>
    </div>`;
    return group;
}

function addConditionToRoot() {
    const root = document.getElementById('filter-root');
    if (root?.querySelector('.filter-group-content')) {
        root.querySelector('.filter-group-content').appendChild(createConditionElement());
    }
}

function addGroupToRoot() {
    const root = document.getElementById('filter-root');
    if (root?.querySelector('.filter-group-content')) {
        root.querySelector('.filter-group-content').appendChild(createGroupElement());
    }
}

function addCondition(btn) {
    btn.closest('.filter-group').querySelector('.filter-group-content').appendChild(createConditionElement());
}

function addGroup(btn) {
    btn.closest('.filter-group').querySelector('.filter-group-content').appendChild(createGroupElement());
}

function clearGroup(btn) {
    btn.closest('.filter-group').querySelector('.filter-group-content').innerHTML = '';
}

function initFilterRoot() {
    const root = document.getElementById('filter-root');
    if (root && !root.querySelector('.filter-group-header')) {
        root.dataset.logic = 'AND';
        root.innerHTML = `<div class="filter-group-header">
            <span class="badge bg-primary" onclick="toggleLogic(this)">AND</span>
            <button class="btn btn-sm btn-close" onclick="clearGroup(this)"></button>
        </div><div class="filter-group-content"></div>`;
    }
}

function initGroupFilterRoot() {
    const root = document.getElementById('group-filter-root');
    if (root && !root.querySelector('.filter-group-header')) {
        root.dataset.logic = 'AND';
        root.innerHTML = `<div class="filter-group-header">
            <span class="badge bg-primary" onclick="toggleGroupFilterLogic(this)">AND</span>
            <button class="btn btn-sm btn-close" onclick="clearGroupFilter(this)"></button>
        </div><div class="filter-group-content"></div>`;
    }
}

function buildGroupFilterJSON() {
    return buildGroupFilterNodeJSON(document.getElementById('group-filter-root'));
}

function buildGroupFilterNodeJSON(node) {
    if (!node) return { logic: 'AND', conditions: [] };
    const logic = node.dataset.logic || 'AND';
    const content = node.querySelector('.filter-group-content');
    const conditions = [];
    if (content) {
        content.children.forEach(child => {
            if (child.dataset.type === 'condition') {
                conditions.push({
                    type: 'condition',
                    field: child.querySelector('.f-field').value,
                    op: child.querySelector('.f-op').value,
                    value: child.querySelector('.f-val').value
                });
            } else if (child.dataset.type === 'group') {
                conditions.push(buildGroupFilterNodeJSON(child));
            }
        });
    }
    return { logic, conditions };
}

function toggleGroupFilterLogic(badge) {
    toggleLogic(badge);
}

function addGroupFilterCondition() {
    const root = document.getElementById('group-filter-root');
    if (root?.querySelector('.filter-group-content')) {
        root.querySelector('.filter-group-content').appendChild(createConditionElement());
    }
}

function addGroupFilterGroup() {
    const root = document.getElementById('group-filter-root');
    if (root?.querySelector('.filter-group-content')) {
        root.querySelector('.filter-group-content').appendChild(createGroupElement());
    }
}

function clearGroupFilter(btn) {
    btn.closest('.filter-group').querySelector('.filter-group-content').innerHTML = '';
}

async function previewGroupFilter() {
    const filterStruct = buildGroupFilterJSON();
    if (!filterStruct.conditions || filterStruct.conditions.length === 0) {
        alert('Добавьте хотя бы одно условие');
        return;
    }
    const previewSection = document.getElementById('filter-preview-section');
    const previewContent = document.getElementById('filter-preview-content');
    previewSection.style.display = 'block';
    previewContent.innerHTML = '<p class="text-muted">Загрузка...</p>';
    try {
        const jsonStr = JSON.stringify(filterStruct);
        const res = await fetch(`/api/assets?filters=${encodeURIComponent(jsonStr)}`);
        const data = await res.json();
        if (data.length === 0) {
            previewContent.innerHTML = '<p class="text-warning">Нет активов</p>';
            return;
        }
        let html = `<p class="text-success">Найдено: <strong>${data.length}</strong></p>`;
        html += '<ul class="list-group list-group-flush small">';
        data.slice(0, 10).forEach(a => {
            html += `<li class="list-group-item">${a.ip} — ${a.hostname || 'No hostname'} <span class="badge bg-secondary">${a.os}</span></li>`;
        });
        if (data.length > 10) html += `<li class="list-group-item text-muted">... и ещё ${data.length - 10}</li>`;
        html += '</ul>';
        previewContent.innerHTML = html;
    } catch (error) {
        previewContent.innerHTML = `<p class="text-danger">Ошибка: ${error.message}</p>`;
    }
}

// ═══════════════════════════════════════════════════════════════
// ИНИЦИАЛИЗАЦИЯ
// ═══════════════════════════════════════════════════════════════

document.addEventListener('DOMContentLoaded', () => {
    initTheme();
    contextMenu = document.getElementById('group-context-menu');
    
    const editModalEl = document.getElementById('groupEditModal');
    const moveModalEl = document.getElementById('groupMoveModal');
    const deleteModalEl = document.getElementById('groupDeleteModal');
    const bulkDeleteModalEl = document.getElementById('bulkDeleteModal');
    
    if (editModalEl) editModal = new bootstrap.Modal(editModalEl);
    if (moveModalEl) moveModal = new bootstrap.Modal(moveModalEl);
    if (deleteModalEl) deleteModal = new bootstrap.Modal(deleteModalEl);
    if (bulkDeleteModalEl) bulkDeleteModalInstance = new bootstrap.Modal(bulkDeleteModalEl);
    
    initTreeTogglers();
    attachContextMenuListeners();
    initFilterRoot();
    initGroupFilterRoot();
    initAssetSelection();
    
    const dynamicCheckbox = document.getElementById('edit-group-dynamic');
    if (dynamicCheckbox) {
        dynamicCheckbox.addEventListener('change', function() {
            const section = document.getElementById('dynamic-filter-section');
            const preview = document.getElementById('filter-preview-section');
            section.style.display = this.checked ? 'block' : 'none';
            preview.style.display = 'none';
            if (!this.checked) {
                const root = document.getElementById('group-filter-root');
                if (root) root.querySelector('.filter-group-content').innerHTML = '';
            }
        });
    }
    
    document.addEventListener('keydown', (e) => {
        if (e.ctrlKey && e.key.toLowerCase() === 'a') {
            const target = e.target;
            if (target.tagName !== 'INPUT' && target.tagName !== 'TEXTAREA') {
                e.preventDefault();
                selectAllVisibleAssets();
            }
        }
    });
});
```

### 📄 `templates/asset_detail.html`

```html
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ asset.ip_address }} - Asset Manager</title>
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
                        <a href="{{ url_for('index') }}" class="btn btn-outline-dark me-3"><i class="bi bi-arrow-left"></i> Назад</a>
                        <span class="navbar-brand mb-0 h1"><i class="bi bi-pc-display"></i> {{ asset.ip_address }}</span>
                    </div>
                    <div class="d-flex align-items-center">
                        <button class="theme-toggle me-2" onclick="toggleTheme()"><i class="bi bi-moon"></i><i class="bi bi-sun"></i></button>
                        <a href="{{ url_for('asset_history', id=asset.id) }}" class="btn btn-outline-info me-2"><i class="bi bi-clock-history"></i> История</a>
                        <a href="{{ url_for('delete_asset', id=asset.id) }}" class="btn btn-outline-danger" onclick="return confirm('Удалить?')"><i class="bi bi-trash"></i></a>
                    </div>
                </nav>

                <div class="card mb-4 {% if asset.status == 'up' %}border-success{% else %}border-danger{% endif %}">
                    <div class="card-body d-flex align-items-center justify-content-between">
                        <div class="d-flex align-items-center">
                            <span class="status-indicator-large {% if asset.status == 'up' %}bg-success{% else %}bg-danger{% endif %} rounded-circle me-3" style="width: 12px; height: 12px;"></span>
                            <div>
                                <h4 class="mb-0">{% if asset.status == 'up' %}<span class="text-success">Активен</span>{% else %}<span class="text-danger">Не доступен</span>{% endif %}</h4>
                                <small class="text-muted">Последнее сканирование: {{ asset.last_scanned.strftime('%Y-%m-%d %H:%M') }}</small>
                            </div>
                        </div>
                        <span class="badge {% if asset.status == 'up' %}bg-success{% else %}bg-danger{% endif %} fs-6">{{ asset.status.upper() }}</span>
                    </div>
                </div>

                <div class="row">
                    <div class="col-lg-8">
                        <div class="card mb-4">
                            <div class="card-header"><i class="bi bi-info-circle"></i> Информация</div>
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
                                        <div class="text-muted small text-uppercase">Группа</div>
                                        <form action="{{ url_for('update_asset_group', id=asset.id) }}" method="POST" class="d-inline">
                                            <select name="group_id" class="form-select form-select-sm" style="width: 200px;" onchange="this.form.submit()">
                                                <option value="">-- Без группы --</option>
                                                {% for g in all_groups %}
                                                    <option value="{{ g.id }}" {% if asset.group_id == g.id %}selected{% endif %}>{{ g.name }}</option>
                                                {% endfor %}
                                            </select>
                                        </form>
                                    </div>
                                </div>
                            </div>
                        </div>

                        <div class="card mb-4">
                            <div class="card-header"><i class="bi bi-door-open"></i> Порты <span class="badge bg-primary float-end">{{ ports_detail|length }}</span></div>
                            <div class="card-body">
                                {% if ports_detail %}
                                    <div class="row">
                                        {% for port in ports_detail %}
                                        <div class="col-md-4 col-sm-6 mb-2">
                                            <span class="badge bg-light text-dark border"><i class="bi bi-hdd-network"></i> <strong>{{ port.port }}</strong> {% if port.service != 'unknown' %}({{ port.service }}){% endif %}</span>
                                        </div>
                                        {% endfor %}
                                    </div>
                                {% else %}
                                    <p class="text-muted mb-0"><i class="bi bi-info-circle"></i> Порты не обнаружены</p>
                                {% endif %}
                            </div>
                        </div>
                    </div>

                    <div class="col-lg-4">
                        <div class="card mb-4">
                            <div class="card-header"><i class="bi bi-lightning"></i> Действия</div>
                            <div class="card-body">
                                <div class="d-grid gap-2">
                                    <a href="#" class="btn btn-outline-primary" onclick="copyToClipboard('{{ asset.ip_address }}'); return false;"><i class="bi bi-clipboard"></i> Копировать IP</a>
                                    <a href="ssh://{{ asset.ip_address }}" class="btn btn-outline-dark" target="_blank"><i class="bi bi-terminal"></i> SSH</a>
                                    <a href="https://{{ asset.ip_address }}" class="btn btn-outline-info" target="_blank"><i class="bi bi-globe"></i> Браузер</a>
                                    <form action="{{ url_for('scan_asset_nmap', id=asset.id) }}" method="POST" class="d-inline">
                                        <button type="submit" class="btn btn-outline-danger w-100"><i class="bi bi-radar"></i> Nmap сканирование</button>
                                    </form>
                                    <a href="{{ url_for('scans_page') }}" class="btn btn-outline-secondary"><i class="bi bi-list-task"></i> Все сканирования</a>
                                </div>
                            </div>
                        </div>

                        <div class="card mb-4">
                            <div class="card-header"><i class="bi bi-journal-text"></i> Заметки</div>
                            <div class="card-body">
                                <form action="{{ url_for('update_asset_notes', id=asset.id) }}" method="POST">
                                    <textarea name="notes" class="form-control" rows="6" placeholder="Заметки...">{{ asset.notes or '' }}</textarea>
                                    <button type="submit" class="btn btn-primary w-100 mt-2"><i class="bi bi-save"></i> Сохранить</button>
                                </form>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
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
        function copyToClipboard(text) {
            navigator.clipboard.writeText(text).then(() => {
                const alert = document.createElement('div');
                alert.className = 'alert alert-success alert-fixed alert-dismissible fade show';
                alert.innerHTML = `IP скопирован: ${text}<button type="button" class="btn-close" data-bs-dismiss="alert"></button>`;
                document.body.appendChild(alert);
                setTimeout(() => alert.remove(), 3000);
            });
        }
        document.addEventListener('DOMContentLoaded', initTheme);
    </script>
</body>
</html>
```

### 📄 `templates/asset_history.html`

```html
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>История - {{ asset.ip_address }}</title>
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
            </div>

            <div class="col-md-9 col-lg-10 p-4">
                <nav class="navbar navbar-light mb-4 px-3">
                    <div class="d-flex align-items-center">
                        <a href="{{ url_for('asset_detail', id=asset.id) }}" class="btn btn-outline-dark me-3"><i class="bi bi-arrow-left"></i> Назад</a>
                        <span class="navbar-brand mb-0 h1"><i class="bi bi-clock-history"></i> История: {{ asset.ip_address }}</span>
                    </div>
                    <button class="theme-toggle" onclick="toggleTheme()"><i class="bi bi-moon"></i><i class="bi bi-sun"></i></button>
                </nav>

                <div class="row">
                    <div class="col-lg-8">
                        <div class="card mb-4">
                            <div class="card-header"><i class="bi bi-activity"></i> Таймлайн <span class="badge bg-primary float-end">{{ changes|length }}</span></div>
                            <div class="card-body">
                                {% if changes %}
                                    <div class="timeline">
                                        {% for change in changes %}
                                        <div class="timeline-item">
                                            <div class="timeline-marker">{{ change.changed_at.strftime('%Y-%m-%d %H:%M') }}</div>
                                            <div class="timeline-dot {{ change.change_type|replace('_', '-') }}"></div>
                                            <div class="timeline-content">
                                                <div class="d-flex justify-content-between align-items-start mb-2">
                                                    <h6 class="mb-0">
                                                        {% if change.change_type == 'port_added' %}<span class="text-success">➕ Порт</span>
                                                        {% elif change.change_type == 'port_removed' %}<span class="text-danger">➖ Порт</span>
                                                        {% elif change.change_type == 'service_detected' %}<span class="text-info">🔍 Сервис</span>
                                                        {% elif change.change_type == 'os_changed' %}<span class="text-warning">💻 ОС</span>
                                                        {% elif change.change_type == 'asset_created' %}<span class="text-primary">🆕 Актив</span>
                                                        {% else %}{{ change.change_type }}{% endif %}
                                                    </h6>
                                                    <span class="badge bg-secondary">{{ change.field_name or '-' }}</span>
                                                </div>
                                                {% if change.old_value %}<div class="mb-1"><small class="text-muted">Было:</small> <code>{{ change.old_value }}</code></div>{% endif %}
                                                {% if change.new_value %}<div class="mb-1"><small class="text-muted">Стало:</small> <code>{{ change.new_value }}</code></div>{% endif %}
                                                {% if change.notes %}<div class="mt-2"><small class="text-muted"><i class="bi bi-chat-left-text"></i> {{ change.notes }}</small></div>{% endif %}
                                            </div>
                                        </div>
                                        {% endfor %}
                                    </div>
                                {% else %}
                                    <p class="text-muted text-center py-4"><i class="bi bi-inbox fs-1 d-block mb-2"></i>История пуста</p>
                                {% endif %}
                            </div>
                        </div>
                    </div>

                    <div class="col-lg-4">
                        <div class="card mb-4">
                            <div class="card-header"><i class="bi bi-hdd-network"></i> Сервисы <span class="badge bg-success float-end">{{ services|length }}</span></div>
                            <div class="card-body">
                                {% if services %}
                                    <div class="list-group list-group-flush">
                                        {% for service in services %}
                                        <div class="list-group-item">
                                            <div class="d-flex justify-content-between align-items-start">
                                                <div>
                                                    <h6 class="mb-1"><i class="bi bi-door-open"></i> {{ service.port }}</h6>
                                                    <p class="mb-1"><strong>{{ service.service_name or 'unknown' }}</strong>
                                                        {% if service.product %}<br><small class="text-muted">{{ service.product }} {{ service.version }}</small>{% endif %}
                                                    </p>
                                                    {% if service.cpe %}<span class="cpe-badge">{{ service.cpe }}</span>{% endif %}
                                                </div>
                                                <div class="form-check form-switch">
                                                    <input class="form-check-input" type="checkbox" {% if service.is_active %}checked{% endif %} onchange="toggleServiceStatus({{ service.id }})">
                                                </div>
                                            </div>
                                            {% if service.script_output %}
                                                <button class="btn btn-sm btn-outline-secondary mt-2" type="button" data-bs-toggle="collapse" data-bs-target="#script-{{ service.id }}"><i class="bi bi-terminal"></i> Скрипты</button>
                                                <div class="collapse" id="script-{{ service.id }}"><div class="script-output"><pre>{{ service.script_output }}</pre></div></div>
                                            {% endif %}
                                            <div class="mt-2"><small class="text-muted"><i class="bi bi-calendar-check"></i> {{ service.first_seen[:10] }}</small></div>
                                        </div>
                                        {% endfor %}
                                    </div>
                                {% else %}
                                    <p class="text-muted text-center py-4"><i class="bi bi-inbox fs-1 d-block mb-2"></i>Сервисы не найдены</p>
                                {% endif %}
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
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
        async function toggleServiceStatus(serviceId) {
            const assetId = {{ asset.id }};
            try {
                await fetch(`/asset/${assetId}/service/${serviceId}/toggle`, { method: 'POST' });
            } catch (error) {
                alert('Ошибка');
            }
        }
        document.addEventListener('DOMContentLoaded', initTheme);
    </script>
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
    
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
    <script src="{{ url_for('static', filename='js/main.js') }}"></script>
    {% block extra_js %}{% endblock %}
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
                        <a href="{{ url_for('index') }}" class="btn btn-outline-dark me-3"><i class="bi bi-arrow-left"></i> Назад</a>
                        <span class="navbar-brand mb-0 h1"><i class="bi bi-plus-circle"></i> Новый актив</span>
                    </div>
                    <button class="theme-toggle" onclick="toggleTheme()"><i class="bi bi-moon"></i><i class="bi bi-sun"></i></button>
                </nav>

                <div class="card">
                    <div class="card-body">
                        <form method="POST" action="{{ url_for('index') }}">
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
                                <a href="{{ url_for('index') }}" class="btn btn-secondary">Отмена</a>
                            </div>
                        </form>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
    <script src="{{ url_for('static', filename='js/main.js') }}"></script>
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
                        <a href="{{ url_for('index') }}" class="btn btn-outline-dark me-3"><i class="bi bi-arrow-left"></i> Назад</a>
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
                                <a href="{{ url_for('index') }}" class="btn btn-secondary">Отмена</a>
                            </div>
                        </form>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
    <script src="{{ url_for('static', filename='js/main.js') }}"></script>
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
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Asset Manager</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.10.0/font/bootstrap-icons.css" rel="stylesheet">
    <link href="{{ url_for('static', filename='css/style.css') }}" rel="stylesheet">
</head>
<body>
    <div class="container-fluid">
        <div class="row">
            <!-- Sidebar -->
            <div class="col-md-3 col-lg-2 sidebar p-3 d-none d-md-block">
                {% include 'components/group_tree.html' %}
            </div>

            <!-- Main Content -->
            <div class="col-md-9 col-lg-10 p-4">
                <!-- Navbar -->
                <nav class="navbar navbar-light mb-4 px-3">
                    <span class="navbar-brand mb-0 h1">
                        <i class="bi bi-shield-check"></i> Asset Manager
                    </span>
                    <div class="d-flex align-items-center">
                        <button class="theme-toggle me-2" onclick="toggleTheme()" title="Переключить тему">
                            <i class="bi bi-moon"></i>
                            <i class="bi bi-sun"></i>
                        </button>
                        <a href="{{ url_for('scans_page') }}" class="btn btn-outline-dark me-2">
                            <i class="bi bi-wifi"></i> Сканирования
                        </a>
                        <a href="{{ url_for('utilities') }}" class="btn btn-outline-dark me-2">
                            <i class="bi bi-tools"></i> Утилиты
                        </a>
                        <button class="btn btn-primary me-2" data-bs-toggle="modal" data-bs-target="#scanModal">
                            <i class="bi bi-upload"></i> Импорт
                        </button>
                        <button class="btn btn-outline-dark me-2" data-bs-toggle="collapse" data-bs-target="#filterPanel">
                            <i class="bi bi-funnel"></i> Фильтры
                        </button>
                        <button class="btn btn-outline-info" data-bs-toggle="collapse" data-bs-target="#analyticsPanel">
                            <i class="bi bi-bar-chart"></i> Аналитика
                        </button>
                    </div>
                </nav>

                <!-- Filter Builder Panel -->
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
                        <div class="mt-2">
                            <button class="btn btn-sm btn-outline-primary" onclick="addConditionToRoot()">
                                <i class="bi bi-plus"></i> Условие
                            </button>
                            <button class="btn btn-sm btn-outline-success" onclick="addGroupToRoot()">
                                <i class="bi bi-plus-circle"></i> Группа
                            </button>
                        </div>
                    </div>
                </div>

                <!-- Analytics Panel -->
                <div class="collapse mb-4" id="analyticsPanel">
                    <div class="card card-body bg-light">
                        <div class="row">
                            <div class="col-md-4">
                                <label>Группировать по:</label>
                                <select id="analytics-group-by" class="form-select">
                                    <option value="os_info">ОС</option>
                                    <option value="status">Статус</option>
                                    <option value="group_id">Группа</option>
                                </select>
                            </div>
                            <div class="col-md-4 d-flex align-items-end">
                                <button class="btn btn-info text-white w-100" onclick="loadAnalytics()">
                                    Построить отчёт
                                </button>
                            </div>
                        </div>
                        <div id="analytics-results" class="mt-3"></div>
                    </div>
                </div>

                <!-- Flash Messages -->
                {% with messages = get_flashed_messages(with_categories=true) %}
                    {% if messages %}
                        {% for category, message in messages %}
                        <div class="alert alert-{{ category }} alert-dismissible fade show">
                            {{ message }}
                            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
                        </div>
                        {% endfor %}
                    {% endif %}
                {% endwith %}

                <!-- Assets Table -->
                <div class="card">
                    <!-- Bulk Actions Toolbar -->
                    <div class="card-header d-flex justify-content-between align-items-center" 
                         id="bulk-toolbar" style="display: none;">
                        <div class="d-flex align-items-center gap-2">
                            <span class="badge bg-primary" id="selected-count">0</span>
                            <span class="text-muted small">выбрано</span>
                        </div>
                        <div class="d-flex gap-2">
                            <button class="btn btn-sm btn-outline-secondary" onclick="clearSelection()">
                                <i class="bi bi-x-lg"></i> Снять
                            </button>
                            <button class="btn btn-sm btn-danger" onclick="confirmBulkDelete()">
                                <i class="bi bi-trash"></i> Удалить
                            </button>
                        </div>
                    </div>
                    
                    <div class="card-body p-0">
                        <table class="table table-hover mb-0">
                            <thead class="table-light">
                                <tr>
                                    <th style="width: 40px;">
                                        <input type="checkbox" class="form-check-input" id="select-all" title="Выделить все (Ctrl+A)">
                                    </th>
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
                    
                    <!-- Empty State -->
                    <div id="empty-state" class="text-center p-4 text-muted" style="display: none;">
                        <i class="bi bi-inbox fs-1 d-block mb-2"></i>
                        <p class="mb-0">Нет активов для отображения</p>
                        <small class="text-muted">Импортируйте Nmap XML или добавьте актив вручную</small>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <!-- Context Menu -->
    <div id="group-context-menu" class="context-menu">
        <button class="context-menu-item" onclick="showCreateGroupModal(currentGroupId)">
            <i class="bi bi-folder-plus"></i> Создать подгруппу
        </button>
        <button class="context-menu-item" onclick="showRenameModal(currentGroupId)">
            <i class="bi bi-pencil"></i> Переименовать
        </button>
        <button class="context-menu-item" onclick="showMoveModal(currentGroupId)">
            <i class="bi bi-arrow-left-right"></i> Переместить
        </button>
        <div class="context-menu-divider"></div>
        <button class="context-menu-item text-danger" onclick="showDeleteModal(currentGroupId)">
            <i class="bi bi-trash"></i> Удалить
        </button>
    </div>

    <!-- Modals -->
    {% include 'components/modals.html' %}

    <!-- Bootstrap JS -->
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
    
    <!-- Custom JS -->
    <script src="{{ url_for('static', filename='js/main.js') }}"></script>
    
    <!-- Page-specific scripts -->
    <script>
        // === THEME TOGGLE ===
        function initTheme() {
            const savedTheme = localStorage.getItem('theme') || 'light';
            document.documentElement.setAttribute('data-bs-theme', savedTheme === 'dark' ? 'dark' : 'light');
            updateThemeIcon(savedTheme);
        }

        function toggleTheme() {
            const html = document.documentElement;
            const currentTheme = html.getAttribute('data-bs-theme');
            const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
            document.body.classList.add('theme-transition');
            html.setAttribute('data-bs-theme', newTheme);
            localStorage.setItem('theme', newTheme);
            updateThemeIcon(newTheme);
            setTimeout(() => {
                document.body.classList.remove('theme-transition');
            }, 300);
        }

        function updateThemeIcon(theme) {
            const toggle = document.querySelector('.theme-toggle');
            if (!toggle) return;
            const moonIcon = toggle.querySelector('.bi-moon');
            const sunIcon = toggle.querySelector('.bi-sun');
            if (theme === 'dark') {
                moonIcon.style.display = 'none';
                sunIcon.style.display = 'block';
            } else {
                moonIcon.style.display = 'block';
                sunIcon.style.display = 'none';
            }
        }

        // === URL PARAMS HANDLING ===
        function handleUrlParams() {
            const urlParams = new URLSearchParams(window.location.search);
            const ungroupedParam = urlParams.get('ungrouped');
            const groupIdParam = urlParams.get('group_id');
            
            if (ungroupedParam === 'true') {
                console.log('📁 Loading ungrouped assets from URL');
                if (typeof filterByGroup === 'function') {
                    filterByGroup('ungrouped');
                }
            } else if (groupIdParam) {
                console.log('📁 Loading group assets from URL:', groupIdParam);
                if (typeof filterByGroup === 'function') {
                    filterByGroup(groupIdParam);
                }
            }
        }

        // === INITIALIZATION ===
        document.addEventListener('DOMContentLoaded', () => {
            console.log('🚀 Index page loaded');
            initTheme();
            handleUrlParams();
        });
    </script>
</body>
</html>
```

### 📄 `templates/scans.html`

```html
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Сканирования</title>
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
            </div>

            <div class="col-md-9 col-lg-10 p-4">
                <nav class="navbar navbar-light mb-4 px-3">
                    <span class="navbar-brand mb-0 h1"><i class="bi bi-wifi"></i> Сканирования</span>
                    <div class="d-flex align-items-center">
                        <button class="theme-toggle me-2" onclick="toggleTheme()"><i class="bi bi-moon"></i><i class="bi bi-sun"></i></button>
                        <a href="{{ url_for('index') }}" class="btn btn-outline-dark"><i class="bi bi-arrow-left"></i> На главную</a>
                    </div>
                </nav>

                <!-- Flash Messages -->
                {% with messages = get_flashed_messages(with_categories=true) %}
                    {% if messages %}
                        {% for category, message in messages %}
                        <div class="alert alert-{{ category }} alert-dismissible fade show">{{ message }}
                            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
                        </div>
                        {% endfor %}
                    {% endif %}
                {% endwith %}

                <!-- New Scan Form -->
                <div class="card mb-4">
                    <div class="card-header">
                        <i class="bi bi-plus-circle"></i> Новое сканирование
                    </div>
                    <div class="card-body">
                        <form id="scanForm">
                            <div class="row mb-3">
                                <div class="col-md-6">
                                    <label class="form-label">Тип сканирования</label>
                                    <select id="scan-type" class="form-select" onchange="toggleScanOptions()">
                                        <option value="rustscan">🚀 Rustscan (быстрое обнаружение портов)</option>
                                        <option value="nmap">🔍 Nmap (детальное сканирование)</option>
                                    </select>
                                </div>
                                <div class="col-md-6">
                                    <label class="form-label">Метод выбора цели</label>
                                    <select id="target-method" class="form-select" onchange="toggleTargetInput()">
                                        <option value="ip">IP / CIDR / Диапазон</option>
                                        <option value="group">Группа активов</option>
                                    </select>
                                </div>
                            </div>
                            
                            <!-- 🔥 Ввод IP/CIDR 🔥 -->
                            <div class="mb-3" id="target-ip-section">
                                <label class="form-label">Цель сканирования</label>
                                <input type="text" id="scan-target" class="form-control" placeholder="192.168.1.0/24 или 192.168.1.1,192.168.1.2">
                                <small class="text-muted">Поддерживаются: одиночные IP, CIDR, списки через запятую</small>
                            </div>
                            
                            <!-- 🔥 Выбор группы 🔥 -->
                            <div class="mb-3" id="target-group-section" style="display: none;">
                                <label class="form-label">Группа активов</label>
                                <select id="scan-group" class="form-select">
                                    <option value="">-- Выберите группу --</option>
                                    <option value="ungrouped">📂 Без группы</option>
                                    {% for g in all_groups %}
                                        <option value="{{ g.id }}">{{ g.name }}</option>
                                    {% endfor %}
                                </select>
                                <small class="text-muted">Будут просканированы все активы из группы (включая вложенные)</small>
                            </div>
                            
                            <!-- 🔥 Порты для Nmap 🔥 -->
                            <div class="mb-3" id="ports-section" style="display: none;">
                                <label class="form-label">Порты (для Nmap)</label>
                                <input type="text" id="scan-ports" class="form-control" placeholder="22,80,443 или оставить пустым для всех">
                                <small class="text-muted">Формат: 22,80,443 или 1-1000</small>
                            </div>
                            
                            <!-- 🔥 Кастомные аргументы 🔥 -->
                            <div class="mb-3">
                                <label class="form-label">
                                    <i class="bi bi-sliders"></i> Кастомные аргументы
                                    <button type="button" class="btn btn-sm btn-link p-0 ms-2" data-bs-toggle="collapse" data-bs-target="#customArgsHelp">
                                        <i class="bi bi-question-circle"></i> Помощь
                                    </button>
                                </label>
                                <div class="collapse mb-2" id="customArgsHelp">
                                    <div class="card card-body bg-light">
                                        <h6>Rustscan примеры:</h6>
                                        <code class="d-block mb-2">--batch-size 500 --timeout 2000</code>
                                        <h6>Nmap примеры:</h6>
                                        <code class="d-block mb-2">-sS -T4 --min-rate 1000</code>
                                        <small class="text-muted">⚠️ Аргументы вставляются в команду. Используйте с осторожностью!</small>
                                    </div>
                                </div>
                                <input type="text" id="scan-custom-args" class="form-control" placeholder="--batch-size 500 (для Rustscan) или -sS -T4 (для Nmap)">
                            </div>
                            
                            <div class="d-grid gap-2 d-md-flex justify-content-md-end">
                                <button type="button" class="btn btn-secondary" onclick="resetScanForm()">
                                    <i class="bi bi-arrow-counterclockwise"></i> Сброс
                                </button>
                                <button type="submit" class="btn btn-primary">
                                    <i class="bi bi-play-fill"></i> Запустить сканирование
                                </button>
                            </div>
                        </form>
                    </div>
                </div>

                <!-- Active Scans -->
                <div class="card mb-4">
                    <div class="card-header">
                        <i class="bi bi-activity"></i> Активные сканирования
                    </div>
                    <div class="card-body">
                        <div id="active-scans">
                            <p class="text-muted mb-0"><i class="bi bi-check-circle"></i> Нет активных сканирований</p>
                        </div>
                    </div>
                </div>

                <!-- Scan History -->
                <div class="card">
                    <div class="card-header">
                        <i class="bi bi-clock-history"></i> История сканирований
                    </div>
                    <div class="card-body p-0">
                        <table class="table table-hover mb-0">
                            <thead class="table-light">
                                <tr>
                                    <th>ID</th>
                                    <th>Тип</th>
                                    <th>Цель</th>
                                    <th>Статус</th>
                                    <th>Прогресс</th>
                                    <th>Начало</th>
                                    <th>Завершение</th>
                                    <th>Действия</th>
                                </tr>
                            </thead>
                            <tbody>
                                {% for job in scan_jobs %}
                                <tr>
                                    <td>{{ job.id }}</td>
                                    <td>
                                        {% if job.scan_type == 'rustscan' %}
                                            <span class="badge bg-danger">🚀 Rustscan</span>
                                        {% else %}
                                            <span class="badge bg-info text-dark">🔍 Nmap</span>
                                        {% endif %}
                                    </td>
                                    <td><code>{{ job.target }}</code></td>
                                    <td>
                                        {% if job.status == 'pending' %}
                                            <span class="badge bg-secondary">Ожидание</span>
                                        {% elif job.status == 'running' %}
                                            <span class="badge bg-warning text-dark">В процессе</span>
                                        {% elif job.status == 'completed' %}
                                            <span class="badge bg-success">Завершено</span>
                                        {% else %}
                                            <span class="badge bg-danger">Ошибка</span>
                                        {% endif %}
                                    </td>
                                    <td>
                                        <div class="progress" style="width: 100px;">
                                            <div class="progress-bar" role="progressbar" 
                                                 style="width: {{ job.progress }}%" 
                                                 aria-valuenow="{{ job.progress }}" 
                                                 aria-valuemin="0" aria-valuemax="100">
                                            </div>
                                        </div>
                                        <small>{{ job.progress }}%</small>
                                    </td>
                                    <td>{{ job.started_at.strftime('%Y-%m-%d %H:%M') if job.started_at else '-' }}</td>
                                    <td>{{ job.completed_at.strftime('%Y-%m-%d %H:%M') if job.completed_at else '-' }}</td>
                                    <td>
                                        {% if job.status == 'completed' %}
                                            {% if job.scan_type == 'rustscan' %}
                                                <a href="/scans/{{ job.id }}/download/greppable" class="btn btn-sm btn-outline-primary" title="Скачать">
                                                    <i class="bi bi-download"></i>
                                                </a>
                                            {% else %}
                                                <div class="btn-group">
                                                    <a href="/scans/{{ job.id }}/download/xml" class="btn btn-sm btn-outline-primary" title="XML">
                                                        <i class="bi bi-file-xml"></i>
                                                    </a>
                                                    <a href="/scans/{{ job.id }}/download/greppable" class="btn btn-sm btn-outline-primary" title="Grepable">
                                                        <i class="bi bi-file-text"></i>
                                                    </a>
                                                    <a href="/scans/{{ job.id }}/download/normal" class="btn btn-sm btn-outline-primary" title="Normal">
                                                        <i class="bi bi-file-earmark"></i>
                                                    </a>
                                                </div>
                                            {% endif %}
                                        {% endif %}
                                        <button class="btn btn-sm btn-outline-info" onclick="viewScanResults({{ job.id }})" title="Результаты">
                                            <i class="bi bi-eye"></i>
                                        </button>
                                    </td>
                                </tr>
                                {% else %}
                                <tr>
                                    <td colspan="8" class="text-center py-4 text-muted">
                                        <i class="bi bi-inbox fs-1 d-block mb-2"></i>
                                        Нет сканирований
                                    </td>
                                </tr>
                                {% endfor %}
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <!-- Modal: Scan Results -->
    <div class="modal fade" id="scanResultsModal" tabindex="-1">
        <div class="modal-dialog modal-lg">
            <div class="modal-content">
                <div class="modal-header">
                    <h5 class="modal-title">Результаты сканирования</h5>
                    <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                </div>
                <div class="modal-body">
                    <div id="scan-results-content">
                        <div class="text-center">
                            <div class="spinner-border" role="status"></div>
                            <p class="mt-2">Загрузка...</p>
                        </div>
                    </div>
                </div>
                <div class="modal-footer">
                    <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Закрыть</button>
                </div>
            </div>
        </div>
    </div>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
    <script>
        // === THEME TOGGLE ===
        function initTheme() {
            const savedTheme = localStorage.getItem('theme') || 'light';
            document.documentElement.setAttribute('data-bs-theme', savedTheme === 'dark' ? 'dark' : 'light');
            updateThemeIcon(savedTheme);
        }

        function toggleTheme() {
            const html = document.documentElement;
            const newTheme = html.getAttribute('data-bs-theme') === 'dark' ? 'light' : 'dark';
            document.body.classList.add('theme-transition');
            html.setAttribute('data-bs-theme', newTheme);
            localStorage.setItem('theme', newTheme);
            updateThemeIcon(newTheme);
            setTimeout(() => {
                document.body.classList.remove('theme-transition');
            }, 300);
        }

        function updateThemeIcon(theme) {
            const toggle = document.querySelector('.theme-toggle');
            if (!toggle) return;
            const moonIcon = toggle.querySelector('.bi-moon');
            const sunIcon = toggle.querySelector('.bi-sun');
            if (theme === 'dark') {
                moonIcon.style.display = 'none';
                sunIcon.style.display = 'block';
            } else {
                moonIcon.style.display = 'block';
                sunIcon.style.display = 'none';
            }
        }

        // === SCAN FORM TOGGLES ===
        function toggleTargetInput() {
            const method = document.getElementById('target-method').value;
            const ipSection = document.getElementById('target-ip-section');
            const groupSection = document.getElementById('target-group-section');
            
            if (method === 'group') {
                ipSection.style.display = 'none';
                groupSection.style.display = 'block';
            } else {
                ipSection.style.display = 'block';
                groupSection.style.display = 'none';
            }
        }

        function toggleScanOptions() {
            const scanType = document.getElementById('scan-type').value;
            const portsSection = document.getElementById('ports-section');
            const customArgsInput = document.getElementById('scan-custom-args');
            
            if (scanType === 'nmap') {
                portsSection.style.display = 'block';
                customArgsInput.placeholder = '-sS -T4 --min-rate 1000 (для Nmap)';
            } else {
                portsSection.style.display = 'none';
                customArgsInput.placeholder = '--batch-size 500 --timeout 2000 (для Rustscan)';
            }
        }

        function resetScanForm() {
            document.getElementById('scanForm').reset();
            toggleTargetInput();
            toggleScanOptions();
        }

        // === SCAN SUBMISSION ===
        document.getElementById('scanForm').addEventListener('submit', async (e) => {
            e.preventDefault();
            
            const scanType = document.getElementById('scan-type').value;
            const targetMethod = document.getElementById('target-method').value;
            const target = document.getElementById('scan-target').value;
            const groupId = document.getElementById('scan-group').value;
            const ports = document.getElementById('scan-ports').value;
            const customArgs = document.getElementById('scan-custom-args').value;
            
            // Валидация
            if (targetMethod === 'ip' && !target) {
                alert('⚠️ Укажите цель сканирования');
                return;
            }
            if (targetMethod === 'group' && !groupId) {
                alert('⚠️ Выберите группу');
                return;
            }
            
            const endpoint = scanType === 'rustscan' ? '/api/scans/rustscan' : '/api/scans/nmap';
            const body = {};
            
            if (targetMethod === 'group') {
                body.group_id = groupId;
            } else {
                body.target = target;
            }
            
            if (scanType === 'nmap' && ports) {
                body.ports = ports;
            }
            
            if (customArgs) {
                body.custom_args = customArgs;
            }
            
            try {
                const response = await fetch(endpoint, {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify(body)
                });
                
                const result = await response.json();
                
                if (response.ok) {
                    alert(`✅ ${result.message}`);
                    location.reload();
                } else {
                    alert(`❌ Ошибка: ${result.error}`);
                }
            } catch (error) {
                alert(`❌ Ошибка: ${error.message}`);
            }
        });

        // === VIEW SCAN RESULTS ===
        async function viewScanResults(jobId) {
            const modal = new bootstrap.Modal(document.getElementById('scanResultsModal'));
            const content = document.getElementById('scan-results-content');
            
            content.innerHTML = '<div class="text-center"><div class="spinner-border"></div><p class="mt-2">Загрузка...</p></div>';
            modal.show();
            
            try {
                const response = await fetch(`/api/scans/${jobId}/results`);
                const data = await response.json();
                
                let html = `<h6>Задание #${data.job.id} - ${data.job.scan_type.toUpperCase()}</h6>`;
                html += `<p><strong>Цель:</strong> ${data.job.target}</p>`;
                html += `<p><strong>Статус:</strong> ${data.job.status}</p>`;
                if (data.job.error_message && data.job.scan_type === 'nmap') {
                    html += `<p><small class="text-muted">Аргументы: ${data.job.error_message}</small></p>`;
                }
                html += `<hr>`;
                
                if (data.results.length === 0) {
                    html += '<p class="text-muted">Нет результатов</p>';
                } else {
                    html += `<p><strong>Найдено хостов:</strong> ${data.results.length}</p>`;
                    html += '<div class="list-group">';
                    data.results.forEach(result => {
                        html += `
                            <div class="list-group-item">
                                <div class="d-flex w-100 justify-content-between">
                                    <h6 class="mb-1">${result.ip}</h6>
                                    <small>${result.scanned_at}</small>
                                </div>
                                <p class="mb-1">
                                    <strong>Порты:</strong> ${result.ports.join(', ') || 'Нет'}
                                </p>
                                ${result.os ? `<p class="mb-1"><strong>ОС:</strong> ${result.os}</p>` : ''}
                                ${result.services && result.services.length > 0 ? `
                                    <p class="mb-1"><strong>Сервисы:</strong></p>
                                    <ul class="small">
                                        ${result.services.map(s => `<li>${s.port}: ${s.name} ${s.product} ${s.version}</li>`).join('')}
                                    </ul>
                                ` : ''}
                            </div>
                        `;
                    });
                    html += '</div>';
                }
                
                content.innerHTML = html;
            } catch (error) {
                content.innerHTML = `<div class="alert alert-danger">❌ Ошибка: ${error.message}</div>`;
            }
        }

        // === POLLING FOR ACTIVE SCANS ===
        function pollActiveScans() {
            fetch('/api/scans/status')
                .then(r => {
                    const contentType = r.headers.get('content-type');
                    if (!contentType || !contentType.includes('application/json')) {
                        throw new Error('Expected JSON response');
                    }
                    return r.json();
                })
                .then(data => {
                    const container = document.getElementById('active-scans');
                    if (data.active && data.active.length > 0) {
                        let html = '<div class="row">';
                        data.active.forEach(job => {
                            const progressBarClass = job.status === 'running' ? 'progress-bar-striped progress-bar-animated' : '';
                            const badgeClass = job.scan_type === 'rustscan' ? 'bg-danger' : 'bg-info text-dark';
                            const statusClass = job.status === 'running' ? 'bg-warning text-dark' : 'bg-secondary';
                            
                            html += `
                                <div class="col-md-6 mb-3">
                                    <div class="card">
                                        <div class="card-body">
                                            <div class="d-flex justify-content-between align-items-center mb-2">
                                                <h6 class="mb-0">
                                                    <span class="badge ${badgeClass} me-2">${job.scan_type.toUpperCase()}</span>
                                                    ${job.target}
                                                </h6>
                                                <span class="badge ${statusClass}">${job.status}</span>
                                            </div>
                                            <div class="progress mb-2" style="height: 6px;">
                                                <div class="progress-bar ${progressBarClass}" role="progressbar" style="width: ${job.progress}%"></div>
                                            </div>
                                            <div class="d-flex justify-content-between small text-muted">
                                                <span>Прогресс: ${job.progress}%</span>
                                                <span>${job.started_at ? 'Started: ' + job.started_at : 'Pending...'}</span>
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            `;
                        });
                        html += '</div>';
                        container.innerHTML = html;
                    } else {
                        container.innerHTML = '<p class="text-muted mb-0"><i class="bi bi-check-circle"></i> Нет активных сканирований</p>';
                    }
                })
                .catch(err => {
                    console.warn('⚠️ Polling error:', err.message);
                });
        }

        // === INITIALIZATION ===
        document.addEventListener('DOMContentLoaded', () => {
            initTheme();
            toggleTargetInput();
            toggleScanOptions();
            pollActiveScans();
            setInterval(pollActiveScans, 5000);
        });
    </script>
</body>
</html>
```

### 📄 `templates/utilities.html`

```html
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Утилиты</title>
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
            </div>

            <div class="col-md-9 col-lg-10 p-4">
                <nav class="navbar navbar-light mb-4 px-3">
                    <span class="navbar-brand mb-0 h1"><i class="bi bi-tools"></i> Утилиты</span>
                    <div class="d-flex align-items-center">
                        <button class="theme-toggle me-2" onclick="toggleTheme()"><i class="bi bi-moon"></i><i class="bi bi-sun"></i></button>
                        <a href="{{ url_for('index') }}" class="btn btn-outline-dark"><i class="bi bi-arrow-left"></i> На главную</a>
                    </div>
                </nav>

                <div class="row">
                    <div class="col-md-6 col-lg-4 mb-4">
                        <div class="card h-100" data-bs-toggle="modal" data-bs-target="#nmapRustscanModal" style="cursor: pointer;">
                            <div class="card-body text-center p-4">
                                <i class="bi bi-lightning-charge display-4 text-primary mb-3"></i>
                                <h5>Nmap → Rustscan</h5>
                                <p class="text-muted">Конвертация XML в список IP для rustscan</p>
                            </div>
                        </div>
                    </div>
                    <div class="col-md-6 col-lg-4 mb-4">
                        <div class="card h-100" data-bs-toggle="modal" data-bs-target="#extractPortsModal" style="cursor: pointer;">
                            <div class="card-body text-center p-4">
                                <i class="bi bi-door-open display-4 text-info mb-3"></i>
                                <h5>Извлечь порты</h5>
                                <p class="text-muted">Извлечение портов из Nmap XML</p>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <div class="modal fade" id="nmapRustscanModal" tabindex="-1">
        <div class="modal-dialog">
            <div class="modal-content">
                <form id="nmapRustscanForm" enctype="multipart/form-data">
                    <div class="modal-header">
                        <h5 class="modal-title">Nmap → Rustscan</h5>
                        <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                    </div>
                    <div class="modal-body">
                        <div class="mb-3">
                            <label class="form-label">Nmap XML файл</label>
                            <input type="file" name="file" class="form-control" accept=".xml" required>
                        </div>
                        <div id="nmapRustscanResult" class="mt-3"></div>
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Отмена</button>
                        <button type="submit" class="btn btn-primary"><i class="bi bi-download"></i> Скачать</button>
                    </div>
                </form>
            </div>
        </div>
    </div>

    <div class="modal fade" id="extractPortsModal" tabindex="-1">
        <div class="modal-dialog">
            <div class="modal-content">
                <form id="extractPortsForm" enctype="multipart/form-data">
                    <div class="modal-header">
                        <h5 class="modal-title">Извлечь порты</h5>
                        <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                    </div>
                    <div class="modal-body">
                        <div class="mb-3">
                            <label class="form-label">Nmap XML файл</label>
                            <input type="file" name="file" class="form-control" accept=".xml" required>
                        </div>
                        <div id="extractPortsResult" class="mt-3"></div>
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Отмена</button>
                        <button type="submit" class="btn btn-primary"><i class="bi bi-download"></i> Скачать</button>
                    </div>
                </form>
            </div>
        </div>
    </div>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
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
        document.getElementById('nmapRustscanForm').addEventListener('submit', async (e) => {
            e.preventDefault();
            const form = e.target;
            const formData = new FormData(form);
            const resultDiv = document.getElementById('nmapRustscanResult');
            resultDiv.innerHTML = '<div class="text-center"><div class="spinner-border"></div></div>';
            try {
                const response = await fetch('/utilities/nmap-to-rustscan', { method: 'POST', body: formData });
                if (response.ok) {
                    const blob = await response.blob();
                    const url = window.URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = url;
                    a.download = response.headers.get('Content-Disposition').split('filename=')[1];
                    document.body.appendChild(a);
                    a.click();
                    window.URL.revokeObjectURL(url);
                    document.body.removeChild(a);
                    resultDiv.innerHTML = '<div class="alert alert-success">Готово!</div>';
                    setTimeout(() => { bootstrap.Modal.getInstance(document.getElementById('nmapRustscanModal')).hide(); resultDiv.innerHTML = ''; form.reset(); }, 2000);
                } else {
                    const error = await response.json();
                    resultDiv.innerHTML = `<div class="alert alert-danger">${error.error}</div>`;
                }
            } catch (error) {
                resultDiv.innerHTML = `<div class="alert alert-danger">${error.message}</div>`;
            }
        });
        document.getElementById('extractPortsForm').addEventListener('submit', async (e) => {
            e.preventDefault();
            const form = e.target;
            const formData = new FormData(form);
            const resultDiv = document.getElementById('extractPortsResult');
            resultDiv.innerHTML = '<div class="text-center"><div class="spinner-border"></div></div>';
            try {
                const response = await fetch('/utilities/extract-ports', { method: 'POST', body: formData });
                if (response.ok) {
                    const blob = await response.blob();
                    const url = window.URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = url;
                    a.download = response.headers.get('Content-Disposition').split('filename=')[1];
                    document.body.appendChild(a);
                    a.click();
                    window.URL.revokeObjectURL(url);
                    document.body.removeChild(a);
                    resultDiv.innerHTML = '<div class="alert alert-success">Готово!</div>';
                    setTimeout(() => { bootstrap.Modal.getInstance(document.getElementById('extractPortsModal')).hide(); resultDiv.innerHTML = ''; form.reset(); }, 2000);
                } else {
                    const error = await response.json();
                    resultDiv.innerHTML = `<div class="alert alert-danger">${error.error}</div>`;
                }
            } catch (error) {
                resultDiv.innerHTML = `<div class="alert alert-danger">${error.message}</div>`;
            }
        });
        document.addEventListener('DOMContentLoaded', initTheme);
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
    <td>{{ asset.hostname }}</td>
    <td><span class="badge bg-info text-dark">{{ asset.os_info }}</span></td>
    <td><small class="text-muted">{{ asset.open_ports }}</small></td>
    <td>
        {% if asset.group %}
            <span class="badge bg-secondary">{{ asset.group.name }}</span>
        {% else %}
            <span class="badge bg-light text-muted border">—</span>
        {% endif %}
    </td>
    <td>
        <a href="/asset/{{ asset.id }}" class="btn btn-sm btn-outline-info" title="Подробно"><i class="bi bi-eye"></i></a>
        <a href="/asset/{{ asset.id }}/delete" class="btn btn-sm btn-outline-danger" onclick="return confirm('Удалить?')"><i class="bi bi-trash"></i></a>
    </td>
</tr>
{% else %}
<tr><td colspan="7" class="text-center py-4 text-muted">Нет данных</td></tr>
{% endfor %}
```

### 📄 `templates/components/group_tree.html`

```html
<div class="group-tree-container">
    <div class="d-flex justify-content-between align-items-center mb-3">
        <h6 class="mb-0 text-uppercase text-muted small fw-bold">
            <i class="bi bi-folder-tree me-2"></i>Группы активов
        </h6>
        <button class="btn btn-sm btn-outline-primary" onclick="showCreateGroupModal(null)">
            <i class="bi bi-plus-lg"></i>
        </button>
    </div>
    
    <div class="group-tree" id="groupTree">
        <ul class="list-group list-group-flush">
            <!-- 🔥 Группа "Без группы" в корне 🔥 -->
<li class="list-group-item px-0 border-0">
    <div class="group-item d-flex align-items-center justify-content-between py-2 {% if current_filter == 'ungrouped' or current_filter is none %}active{% endif %}" 
         data-group-id="ungrouped"
         data-bs-toggle="tooltip" 
         title="Активы без группы">
        
        <div class="d-flex align-items-center flex-grow-1" style="cursor: pointer;" onclick="filterByGroup('ungrouped')">
            <span class="me-2" style="width: 16px;"></span>
            <i class="bi bi-folder-minus-fill text-muted me-2"></i>
            <span class="group-name flex-grow-1">Без группы</span>
            <span class="badge bg-light text-dark rounded-pill ms-2" id="ungrouped-count">
                {{ ungrouped_count if ungrouped_count is defined else 0 }}
            </span>
        </div>
    </div>
</li>
            
            <!-- Остальные группы -->
            {% if group_tree %}
                {% macro render_groups(nodes, level=0) %}
                    {% for node in nodes %}
                        <li class="list-group-item px-0 border-0" style="padding-left: {{ level * 20 }}px !important;">
                            <div class="group-item d-flex align-items-center justify-content-between py-2 {% if node.is_dynamic %}group-dynamic{% endif %}" 
                                 data-group-id="{{ node.id }}"
                                 data-bs-toggle="tooltip" 
                                 title="{% if node.is_dynamic %}Динамическая группа{% else %}Статическая группа{% endif %}">
                                
                                <div class="d-flex align-items-center flex-grow-1" style="cursor: pointer;" onclick="filterByGroup({{ node.id }})">
                                    {% if node.children %}
                                        <i class="bi bi-caret-right-fill me-2 text-muted group-toggle" 
                                           data-group-id="{{ node.id }}"
                                           onclick="event.stopPropagation(); toggleGroup(this, {{ node.id }})"></i>
                                    {% else %}
                                        <span class="me-2" style="width: 16px;"></span>
                                    {% endif %}
                                    
                                    <i class="bi {% if node.is_dynamic %}bi-lightning-charge-fill text-warning{% else %}bi-folder-fill text-primary{% endif %} me-2"></i>
                                    
                                    <span class="group-name flex-grow-1">{{ node.name }}</span>
                                    
                                    <span class="badge bg-light text-dark rounded-pill ms-2">
                                        {{ node.count }}
                                    </span>
                                </div>
                                
                                <div class="group-actions btn-group">
                                    <button class="btn btn-sm btn-link text-muted p-0 me-1" 
                                            onclick="event.stopPropagation(); showRenameModal({{ node.id }})"
                                            title="Переименовать">
                                        <i class="bi bi-pencil"></i>
                                    </button>
                                    <button class="btn btn-sm btn-link text-muted p-0" 
                                            onclick="event.stopPropagation(); showMoveModal({{ node.id }})"
                                            title="Переместить">
                                        <i class="bi bi-arrow-left-right"></i>
                                    </button>
                                </div>
                            </div>
                            
                            {% if node.children %}
                                <ul class="list-group list-group-flush ms-3 d-none" id="group-children-{{ node.id }}">
                                    {{ render_groups(node.children, level + 1) }}
                                </ul>
                            {% endif %}
                        </li>
                    {% endfor %}
                {% endmacro %}
                
                {{ render_groups(group_tree) }}
            {% endif %}
        </ul>
    </div>
    
    <div class="mt-3 pt-3 border-top">
        <button class="btn btn-sm btn-outline-secondary w-100" onclick="showCreateGroupModal(null)">
            <i class="bi bi-plus-lg me-1"></i>Новая группа
        </button>
    </div>
</div>

<script>
function toggleGroup(element, groupId) {
    const children = document.getElementById(`group-children-${groupId}`);
    if (children) {
        children.classList.toggle('d-none');
        element.classList.toggle('bi-caret-right-fill');
        element.classList.toggle('bi-caret-down-fill');
    }
}

function filterByGroup(groupId) {
    console.log('📁 Filtering by group:', groupId, 'Type:', typeof groupId);
    
    // 🔥 Явно преобразуем к строке 🔥
    groupId = String(groupId);
    
    // Подсветка активной группы
    document.querySelectorAll('.group-item').forEach(item => {
        item.classList.remove('active');
    });
    
    const activeGroup = document.querySelector(`[data-group-id="${groupId}"]`);
    if (activeGroup) {
        activeGroup.classList.add('active');
    }
    
    // 🔥 Проверка на "Без группы" 🔥
    console.log('🔍 Checking groupId:', groupId, 'Equals ungrouped:', groupId === 'ungrouped');
    
    let url;
    if (groupId === 'ungrouped') {
        url = '/api/assets?ungrouped=true';
        console.log('✅ Fetching UNGROUPED assets:', url);
    } else {
        // 🔥 Проверяем, что groupId - валидное число 🔥
        const numericId = parseInt(groupId, 10);
        if (isNaN(numericId)) {
            console.error('❌ Invalid group ID:', groupId);
            alert('Ошибка: некорректный ID группы');
            return;
        }
        url = `/api/assets?group_id=${numericId}`;
        console.log('✅ Fetching GROUP assets:', url);
    }
    
    fetch(url)
        .then(response => {
            console.log('📡 Response status:', response.status);
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            console.log('📦 Assets loaded:', data.length);
            
            if (typeof window.renderAssets === 'function') {
                window.renderAssets(data);
            } else {
                console.error('❌ renderAssets function not found!');
                // Fallback: перезагрузка с параметром
                if (groupId === 'ungrouped') {
                    window.location.href = '/?ungrouped=true';
                } else {
                    window.location.href = `/?group_id=${groupId}`;
                }
            }
        })
        .catch(error => {
            console.error('❌ Error loading assets:', error);
            alert('Ошибка загрузки активов: ' + error.message);
        });
}

// Обновление счётчика "Без группы"
async function updateUngroupedCount() {
    try {
        const response = await fetch('/api/assets?ungrouped=true');
        const data = await response.json();
        const countElement = document.getElementById('ungrouped-count');
        if (countElement) {
            countElement.textContent = data.length || 0;
        }
    } catch (error) {
        console.warn('Could not update ungrouped count:', error);
    }
}

// Инициализация тултипов
document.addEventListener('DOMContentLoaded', function() {
    // Проверяем, что Bootstrap загружен
    if (typeof bootstrap !== 'undefined') {
        var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
        tooltipTriggerList.map(function (tooltipTriggerEl) {
            return new bootstrap.Tooltip(tooltipTriggerEl);
        });
    }
    
    // Разворачивание первой группы при загрузке
    const firstGroup = document.querySelector('.group-toggle');
    if (firstGroup) {
        const groupId = firstGroup.getAttribute('data-group-id');
        toggleGroup(firstGroup, groupId);
    }
    
    // Обновляем счётчик "Без группы" при загрузке
    updateUngroupedCount();
});
</script>

<style>
.group-tree-container {
    background: var(--bs-body-bg);
    border-radius: 0.5rem;
}

.group-tree .list-group-item {
    background: transparent;
    border: none;
    padding-left: 0 !important;
}

.group-item {
    border-radius: 0.375rem;
    transition: all 0.2s ease;
    margin-bottom: 0.25rem;
}

.group-item:hover {
    background: var(--bs-tertiary-bg);
}

.group-item.active {
    background: rgba(13, 110, 253, 0.1);
    border-left: 3px solid var(--bs-primary);
}

.group-item.active .group-name {
    color: var(--bs-primary);
    font-weight: 600;
}

/* Стиль для "Без группы" */
.group-item[data-group-id="ungrouped"] .bi-folder-minus-fill {
    color: var(--bs-secondary) !important;
}

.group-item[data-group-id="ungrouped"].active {
    border-left-color: var(--bs-secondary);
}

.group-dynamic {
    border-left: 2px solid var(--bs-warning);
    padding-left: 8px !important;
}

.group-toggle {
    transition: transform 0.2s ease;
    cursor: pointer;
}

.group-toggle:hover {
    color: var(--bs-primary) !important;
}

.group-actions {
    opacity: 0;
    transition: opacity 0.2s ease;
}

.group-item:hover .group-actions {
    opacity: 1;
}

.group-actions .btn-link {
    text-decoration: none;
    font-size: 0.875rem;
}

.group-actions .btn-link:hover {
    color: var(--bs-primary) !important;
}

.list-group .list-group {
    margin-top: 0.25rem;
}

@media (max-width: 768px) {
    .group-actions {
        opacity: 1;
    }
}
</style>
```

### 📄 `templates/components/modals.html`

```html
<div class="modal fade" id="scanModal" tabindex="-1">
    <div class="modal-dialog">
        <div class="modal-content">
            <form action="{{ url_for('import_scan') }}" method="post" enctype="multipart/form-data">
                <div class="modal-header">
                    <h5 class="modal-title">Импорт Nmap</h5>
                    <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                </div>
                <div class="modal-body">
                    <div class="mb-3">
                        <label class="form-label">XML файл</label>
                        <input type="file" name="file" class="form-control" accept=".xml" required>
                    </div>
                    <div class="mb-3">
                        <label class="form-label">Группа</label>
                        <select name="group_id" class="form-select">
                            <option value="">Без группы</option>
                            {% for g in all_groups %}<option value="{{ g.id }}">{{ g.name }}</option>{% endfor %}
                        </select>
                    </div>
                </div>
                <div class="modal-footer">
                    <button type="submit" class="btn btn-primary">Загрузить</button>
                </div>
            </form>
        </div>
    </div>
</div>

<div class="modal fade" id="groupEditModal" tabindex="-1">
    <div class="modal-dialog modal-lg">
        <div class="modal-content">
            <form id="groupEditForm">
                <div class="modal-header">
                    <h5 class="modal-title" id="groupEditTitle">Группа</h5>
                    <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                </div>
                <div class="modal-body">
                    <input type="hidden" id="edit-group-id">
                    <div class="mb-3">
                        <label class="form-label">Название</label>
                        <input type="text" id="edit-group-name" class="form-control" required>
                    </div>
                    <div class="mb-3">
                        <label class="form-label">Родитель</label>
                        <select id="edit-group-parent" class="form-select">
                            <option value="">-- Корень --</option>
                            {% for g in all_groups %}<option value="{{ g.id }}">{{ g.name }}</option>{% endfor %}
                        </select>
                    </div>
                    <div class="mb-3">
                        <div class="form-check form-switch">
                            <input class="form-check-input" type="checkbox" id="edit-group-dynamic">
                            <label class="form-check-label" for="edit-group-dynamic">Динамическая группа</label>
                        </div>
                    </div>
                    <div id="dynamic-filter-section" class="mb-3" style="display: none;">
                        <label class="form-label">Фильтр</label>
                        <div id="group-filter-root" class="filter-group"></div>
                        <div class="mt-2">
                            <button type="button" class="btn btn-sm btn-outline-primary" onclick="addGroupFilterCondition()">+ Условие</button>
                            <button type="button" class="btn btn-sm btn-outline-success" onclick="addGroupFilterGroup()">+ Группа</button>
                            <button type="button" class="btn btn-sm btn-outline-secondary" onclick="previewGroupFilter()">Предпросмотр</button>
                        </div>
                    </div>
                    <div id="filter-preview-section" class="mb-3" style="display: none;">
                        <div class="card border-info">
                            <div class="card-body" id="filter-preview-content"></div>
                        </div>
                    </div>
                </div>
                <div class="modal-footer">
                    <button type="submit" class="btn btn-primary">Сохранить</button>
                </div>
            </form>
        </div>
    </div>
</div>

<div class="modal fade" id="groupMoveModal" tabindex="-1">
    <div class="modal-dialog">
        <div class="modal-content">
            <form id="groupMoveForm">
                <div class="modal-header">
                    <h5 class="modal-title">Переместить</h5>
                    <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                </div>
                <div class="modal-body">
                    <input type="hidden" id="move-group-id">
                    <div class="mb-3">
                        <label class="form-label">Новый родитель</label>
                        <select id="move-group-parent" class="form-select">
                            <option value="">-- Корень --</option>
                        </select>
                    </div>
                </div>
                <div class="modal-footer">
                    <button type="submit" class="btn btn-primary">Переместить</button>
                </div>
            </form>
        </div>
    </div>
</div>

<div class="modal fade" id="groupDeleteModal" tabindex="-1">
    <div class="modal-dialog">
        <div class="modal-content">
            <div class="modal-header">
                <h5 class="modal-title text-danger">Удаление</h5>
                <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
            </div>
            <div class="modal-body">
                <input type="hidden" id="delete-group-id">
                <p class="text-warning"><i class="bi bi-exclamation-triangle"></i> Вы уверены?</p>
                <div class="mb-3">
                    <label class="form-label">Перенести активы:</label>
                    <select id="delete-move-assets" class="form-select">
                        <option value="">-- Не переносить --</option>
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

<div class="modal fade" id="bulkDeleteModal" tabindex="-1">
    <div class="modal-dialog">
        <div class="modal-content">
            <div class="modal-header">
                <h5 class="modal-title text-danger">Удаление активов</h5>
                <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
            </div>
            <div class="modal-body">
                <p>Удалить <strong id="bulk-delete-count">0</strong> активов?</p>
                <div id="bulk-delete-preview" class="small text-muted"></div>
            </div>
            <div class="modal-footer">
                <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Отмена</button>
                <button type="button" class="btn btn-danger" onclick="executeBulkDelete()">Удалить</button>
            </div>
        </div>
    </div>
</div>
```

---

✅ **Экспорт завершён.** Файл содержит 15 файлов общим размером 219.3 KB.
💡 **Совет:** Скопируйте содержимое этого файла целиком в новое окно чата для сохранения контекста разработки.
