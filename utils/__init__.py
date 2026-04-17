import json
import os
import re
import xml.etree.ElementTree as ET
from sqlalchemy import or_, and_
from datetime import datetime, timezone, timedelta
from extensions import db
from models import Asset, Group, AssetChangeLog

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

def detect_device_role_and_tags(ports_str, services_data=None):
    """Определяет роль устройства и набор тегов-корреляций на основе портов и сервисов"""
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

def parse_nmap_xml(filepath):
    import xml.etree.ElementTree as ET
    tree = ET.parse(filepath)
    root = tree.getroot()
    assets = []
    for host in root.findall('host'):
        status = host.find('status')
        if status is None or status.get('state') != 'up': continue
        addr = host.find('address')
        ip = addr.get('addr') if addr is not None else 'Unknown'
        hostnames = host.find('hostnames')
        hostname = 'Unknown'
        if hostnames is not None:
            name_elem = hostnames.find('hostname')
            if name_elem is not None: hostname = name_elem.get('name')
        os_info = 'Unknown'
        os_elem = host.find('os')
        if os_elem is not None:
            os_match = os_elem.find('osmatch')
            if os_match is not None: os_info = os_match.get('name')
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
        assets.append({'ip_address': ip, 'hostname': hostname, 'os_info': os_info, 'status': 'up', 'open_ports': ', '.join(ports)})
    return assets

def build_group_tree(groups, parent_id=None):
    """Построение дерева групп с подсчётом активов"""
    tree = []
    for group in groups:
        if group.parent_id == parent_id:
            children = build_group_tree(groups, group.id)
            
            # 🔥 Подсчёт активов
            if group.is_dynamic and group.filter_query:
                try:
                    filter_struct = json.loads(group.filter_query)
                    count_query = build_complex_query(Asset, filter_struct, Asset.query)
                    count = count_query.count()  # ✅ .count() для Query
                except Exception as e:
                    print(f"⚠️ Ошибка подсчёта динамической группы {group.name}: {e}")
                    count = 0
            else:
                count = group.assets.count()  # ✅ .count() вместо len() для AppenderQuery
            
            tree.append({
                'id': group.id, 
                'name': group.name, 
                'children': children, 
                'count': count, 
                'is_dynamic': group.is_dynamic,
                'cidr_network': group.cidr_network,
                'cidr_mask': group.cidr_mask
            })
    return tree


def create_cidr_groups(network_str, mask, parent_id=None):
    """Создание групп на основе CIDR-диапазона"""
    import ipaddress
    from models import Group
    from extensions import db
    
    try:
        network = ipaddress.ip_network(network_str, strict=False)
    except ValueError as e:
        raise ValueError(f"Неверный формат CIDR: {e}")
    
    # Создаем родительскую группу для диапазона
    parent_group = Group(
        name=f"{network_str} (CIDR)",
        parent_id=parent_id,
        cidr_network=network_str,
        cidr_mask=mask,
        is_dynamic=False
    )
    db.session.add(parent_group)
    db.session.flush()  # Получаем ID
    
    # Генерируем подсети
    subnets = list(network.subnets(new_prefix=mask))
    created_count = 0
    
    for subnet in subnets:
        subgroup = Group(
            name=str(subnet),
            parent_id=parent_group.id,
            is_dynamic=False
        )
        db.session.add(subgroup)
        created_count += 1
    
    db.session.commit()
    return created_count + 1  # +1 для родительской группы

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
        if logic == 'AND': base_query = base_query.filter(and_(*sqlalchemy_filters))
        else: base_query = base_query.filter(or_(*sqlalchemy_filters))
    return base_query

def log_asset_change(asset_id, change_type, field_name, old_value, new_value, scan_job_id=None, notes=None):
    change = AssetChangeLog(asset_id=asset_id, change_type=change_type, field_name=field_name,
                            old_value=json.dumps(old_value) if old_value else None,
                            new_value=json.dumps(new_value) if new_value else None,
                            scan_job_id=scan_job_id, notes=notes)
    db.session.add(change)

def generate_asset_taxonomy(asset, services=None):
    """Генерирует таксономию актива на основе его атрибутов"""
    ports = set()
    if asset.open_ports:
        for p in asset.open_ports.split(','):
            port_num = p.strip().split('/')[0]
            if port_num.isdigit(): ports.add(port_num)
    device_class = "Не классифицировано"
    device_subclass = ""
    if asset.os_info:
        os_lower = asset.os_info.lower()
        if any(w in os_lower for w in ['windows', 'microsoft']): 
            device_class = "Сервер/АРМ (Windows)"
            device_subclass = "Windows" if 'server' in os_lower else "Windows Workstation"
        elif any(w in os_lower for w in ['linux', 'ubuntu', 'centos', 'debian', 'red hat']): 
            device_class = "Сервер/АРМ (Linux)"
            device_subclass = "Linux"
        elif any(w in os_lower for w in ['cisco', 'juniper', 'mikrotik', 'router', 'switch']): 
            device_class = "Сетевое оборудование"
            device_subclass = "Network Device"
        elif any(w in os_lower for w in ['iot', 'embedded', 'camera', 'printer']): 
            device_class = "Специализированное / IoT"
            device_subclass = "IoT/Embedded"
    if not device_class:
        if '3389' in ports or '445' in ports: 
            device_class = "Сервер/АРМ (Windows)"
            device_subclass = "Windows (по портам)"
        elif '22' in ports: 
            device_class = "Сервер/АРМ (Linux)"
            device_subclass = "Linux (по портам)"
        elif '161' in ports or '23' in ports: 
            device_class = "Сетевое оборудование"
            device_subclass = "Network (по портам)"
    role = asset.device_role or "Не определена"
    role_category = "Общего назначения"
    role_map = {
        'контроллер': "Инфраструктура идентификации", 'domain controller': "Инфраструктура идентификации",
        'база данных': "Хранение данных", 'database': "Хранение данных",
        'веб': "Публикация контента / Приложения", 'web': "Публикация контента / Приложения", 'сервер приложений': "Публикация контента / Приложения",
        'почт': "Коммуникации", 'mail': "Коммуникации", 'exchange': "Коммуникации",
        'файл': "Файловые сервисы", 'file': "Файловые сервисы", 'nas': "Файловые сервисы",
        'принтер': "Периферия", 'printer': "Периферия",
        'мониторинг': "Управление и обслуживание", 'backup': "Управление и обслуживание", 'резерв': "Управление и обслуживание",
        'видео': "Мультимедиа / Телефония", 'voip': "Мультимедиа / Телефония", 'телефон': "Мультимедиа / Телефония"
    }
    for key, cat in role_map.items():
        if key in role.lower(): 
            role_category = cat
            break
    services_tree = []
    svc_map = {
        '22': ('Удаленный доступ', 'SSH'), '23': ('Удаленный доступ', 'Telnet'), 
        '80': ('Веб-сервисы', 'HTTP'), '443': ('Веб-сервисы', 'HTTPS'), '8080': ('Веб-сервисы', 'HTTP-Proxy/Alt'), 
        '21': ('Файловые сервисы', 'FTP'), '445': ('Файловые сервисы', 'SMB/CIFS'), 
        '3306': ('Базы данных', 'MySQL'), '1433': ('Базы данных', 'MSSQL'), '5432': ('Базы данных', 'PostgreSQL'), 
        '27017': ('Базы данных', 'MongoDB'), '3389': ('Удаленный доступ', 'RDP'), '53': ('Инфраструктура', 'DNS'), 
        '25': ('Почта', 'SMTP'), '110': ('Почта', 'POP3'), '143': ('Почта', 'IMAP'), 
        '88': ('Инфраструктура', 'Kerberos'), '389': ('Инфраструктура', 'LDAP'), '161': ('Мониторинг', 'SNMP'), 
        '5900': ('Удаленный доступ', 'VNC'), '9100': ('Периферия', 'JetDirect/Printer'),
    }
    grouped_services = {}
    for port in sorted(ports):
        if port in svc_map:
            cat, svc_name = svc_map[port]
            grouped_services.setdefault(cat, []).append(svc_name)
    for cat, svcs in grouped_services.items(): 
        services_tree.append({'category': cat, 'services': svcs})
    sources = []
    if asset.scanners_used:
        try:
            for s in json.loads(asset.scanners_used): 
                sources.append({'name': s.upper(), 'type': 'Сканер уязвимостей/портов'})
        except: pass
    if asset.osquery_status == 'online': 
        sources.append({'name': 'OSquery Agent', 'type': 'Агент инвентаризации'})
    if not sources: 
        sources.append({'name': 'Ручной ввод', 'type': 'Статический'})
    return {
        'asset_id': asset.id, 
        'ip_address': asset.ip_address, 
        'hostname': asset.hostname or 'N/A', 
        'nodes': [
            {'id': 'device', 'title': 'Класс устройства', 'icon': 'bi-pc-display', 'value': device_class,
             'children': [{'title': 'Подкласс', 'value': device_subclass}] if device_subclass else []},
            {'id': 'role', 'title': 'Функциональная роль', 'icon': 'bi-briefcase', 'value': role,
             'children': [{'title': 'Категория', 'value': role_category}] if role_category else []},
            {'id': 'services', 'title': 'Сетевые сервисы', 'icon': 'bi-hdd-network', 'value': f"{len(ports)} портов",
             'children': [{'title': cat, 'value': ', '.join(svcs)} for cat, svcs in grouped_services.items()] or [{'title': 'Нет классифицируемых сервисов', 'value': ''}]},
            {'id': 'sources', 'title': 'Источники данных', 'icon': 'bi-database', 'value': f"{len(sources)} источников",
             'children': [{'title': s['name'], 'value': s['type']} for s in sources]}
        ]
    }

def parse_nmap_xml(filepath):
    """Парсинг Nmap XML файла для импорта через интерфейс"""
    import xml.etree.ElementTree as ET
    import json
    
    try:
        tree = ET.parse(filepath)
        root = tree.getroot()
        assets = []
        
        for host in root.findall('host'):
            status = host.find('status')
            if status is None or status.get('state') != 'up':
                continue
            
            addr = host.find('address')
            ip = addr.get('addr') if addr is not None else 'Unknown'
            if ip == 'Unknown':
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
            ports_elem = host.find('ports')
            if ports_elem is not None:
                for port in ports_elem.findall('port'):
                    state = port.find('state')
                    if state is not None and state.get('state') == 'open':
                        port_id = port.get('portid')
                        service = port.find('service')
                        service_name = service.get('name') if service is not None else ''
                        ports.append(f"{port_id}/{service_name}" if service_name else port_id)
            
            # ✅ Теперь ports_list можно передавать — поле есть в модели
            assets.append({
                'ip_address': ip,
                'hostname': hostname,
                'os_info': os_info,
                'status': 'up',
                'open_ports': ', '.join(ports),
                'ports_list': json.dumps(ports)  # 🔥 Сохраняем как JSON
            })
        
        print(f"✅ Спарсено {len(assets)} активов из {filepath}")
        return assets
        
    except Exception as e:
        print(f"❌ Ошибка парсинга Nmap XML {filepath}: {e}")
        return []