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