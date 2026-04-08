# utils.py
import json
from extensions import db
from models import Asset, Group, AssetChangeLog
from sqlalchemy import or_, and_
import xml.etree.ElementTree as ET

def parse_nmap_xml(filepath):
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