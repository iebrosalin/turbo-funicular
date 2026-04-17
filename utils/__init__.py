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

def build_group_tree(groups, parent_id=None):
    """Построение дерева групп"""
    Asset, Group, _, _, _ = get_models()
    from sqlalchemy import and_, or_
    
    tree = []
    for group in groups:
        if group.parent_id == parent_id:
            children = build_group_tree(groups, group.id)
            
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
            
            tree.append({
                'id': group.id, 
                'name': group.name, 
                'children': children, 
                'count': count, 
                'is_dynamic': group.is_dynamic
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