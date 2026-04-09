import json
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
