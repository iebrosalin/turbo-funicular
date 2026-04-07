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
# МАРШРУТЫ
# ═══════════════════════════════════════════════════════════════

@app.route('/')
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

    print(f"🔍 API /api/assets called")
    print(f"   - ungrouped: {request.args.get('ungrouped')}")
    print(f"   - group_id: {request.args.get('group_id')}")
    print(f"   - filters: {request.args.get('filters')}")

    filters_raw = request.args.get('filters')

    ungrouped = request.args.get('ungrouped')
    if ungrouped and ungrouped.lower() == 'true':
        print(f"   ✅ Filtering UNGROUPED assets (group_id IS NULL)")
        query = query.filter(Asset.group_id.is_(None))
    else:
        group_id = request.args.get('group_id')
        if group_id and group_id != 'all':
            print(f"   ✅ Filtering by group_id: {group_id}")
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

    scan_job = ScanJob(
        scan_type='rustscan',
        target=target_description,
        status='pending',
        rustscan_output=custom_args if custom_args else None
    )
    db.session.add(scan_job)
    db.session.commit()

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

    scan_job = ScanJob(
        scan_type='nmap',
        target=target_description,
        status='pending',
        rustscan_output=f'Ports: {ports}' if ports else None
    )
    if custom_args:
        scan_job.error_message = f'Custom args: {custom_args}'

    db.session.add(scan_job)
    db.session.commit()

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

# ═══════════════════════════════════════════════════════════════
# API УПРАВЛЕНИЯ СКАНИРОВАНИЯМИ
# ═══════════════════════════════════════════════════════════════

@app.route('/api/scans/<int:job_id>/control', methods=['POST'])
def control_scan_job(job_id):
    """Управление сканированием: stop, pause, resume, delete"""
    data = request.json
    action = data.get('action')
    scan_job = ScanJob.query.get_or_404(job_id)
    
    try:
        # 🔥 НОВАЯ ПРОВЕРКА ДЛЯ DELETE С pending ЗАДАЧ
        if action == 'delete':
            if scan_job.status in ['pending', 'completed', 'failed', 'stopped']:
                # Удаляем файлы результатов если есть
                files_to_delete = [
                    scan_job.nmap_xml_path, 
                    scan_job.nmap_grep_path, 
                    scan_job.nmap_normal_path
                ]
                for f in files_to_delete:
                    if f and os.path.exists(f):
                        try:
                            os.remove(f)
                        except:
                            pass
                
                db.session.delete(scan_job)
                db.session.commit()
                return jsonify({'success': True, 'message': 'Задание удалено'})
            else:
                return jsonify({'error': 'Нельзя удалить активное задание. Сначала остановите его.'}), 400
        
        elif action == 'stop':
            if scan_job.status in ['running', 'paused']:
                scan_job.status = 'stopped'
                scan_job.error_message = "Сканирование остановлено пользователем."
                scan_job.completed_at = datetime.utcnow()
                db.session.commit()
                
                # Процесс сам завершится в цикле while в фоновой задаче
                return jsonify({'success': True, 'message': 'Команда остановки отправлена'})
            else:
                return jsonify({'error': 'Нельзя остановить задание в статусе: ' + scan_job.status}), 400
        
        elif action == 'pause':
            if scan_job.status == 'running':
                scan_job.status = 'paused'
                db.session.commit()
                return jsonify({'success': True, 'message': 'Сканирование приостановлено'})
            else:
                return jsonify({'error': 'Нельзя приостановить задание в статусе: ' + scan_job.status}), 400
        
        elif action == 'resume':
            if scan_job.status == 'paused':
                scan_job.status = 'running'
                db.session.commit()
                return jsonify({'success': True, 'message': 'Сканирование возобновлено'})
            else:
                return jsonify({'error': 'Нельзя возобновить задание в статусе: ' + scan_job.status}), 400
        
        else:
            return jsonify({'error': 'Неизвестная команда'}), 400
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

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