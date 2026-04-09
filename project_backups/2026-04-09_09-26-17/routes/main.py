# routes/main.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from extensions import db
from models import Group, Asset, AssetChangeLog, ServiceInventory, ScanJob
from utils import build_group_tree, build_complex_query
from sqlalchemy import func
import json
import threading

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def index():
    all_groups = Group.query.all()
    group_tree = build_group_tree(all_groups)
    assets = Asset.query.all()
    ungrouped_count = Asset.query.filter(Asset.group_id.is_(None)).count()
    current_filter = request.args.get('group_id')
    if request.args.get('ungrouped') == 'true': current_filter = 'ungrouped'
    elif not current_filter or current_filter == 'all': current_filter = 'ungrouped'
    return render_template('index.html', assets=assets, group_tree=group_tree, all_groups=all_groups, ungrouped_count=ungrouped_count, current_filter=current_filter)

@main_bp.route('/api/assets', methods=['GET'])
def get_assets_api():
    query = Asset.query
    filters_raw = request.args.get('filters')
    ungrouped = request.args.get('ungrouped')
    if ungrouped and ungrouped.lower() == 'true':
        query = query.filter(Asset.group_id.is_(None))
    else:
        group_id = request.args.get('group_id')
        if group_id and group_id != 'all':
            try:
                group_id_int = int(group_id)
                group = Group.query.get(group_id_int)
                if group and group.is_dynamic and group.filter_query:
                    try:
                        filter_struct = json.loads(group.filter_query)
                        query = build_complex_query(Asset, filter_struct, query)
                    except Exception: query = query.filter(Asset.group_id == group_id_int)
                else: query = query.filter(Asset.group_id == group_id_int)
            except ValueError: return jsonify({'error': 'Invalid group_id'}), 400
    if filters_raw:
        try:
            filters_structure = json.loads(filters_raw)
            query = build_complex_query(Asset, filters_structure, query)
        except Exception: pass
    assets = query.all()
    data = [{'id': a.id, 'ip': a.ip_address, 'hostname': a.hostname, 'os': a.os_info, 'ports': a.open_ports, 'group': a.group.name if a.group else 'Без группы', 'last_scan': a.last_scanned.strftime('%Y-%m-%d %H:%M')} for a in assets]
    return jsonify(data)

@main_bp.route('/api/analytics', methods=['GET'])
def get_analytics():
    filters_raw = request.args.get('filters')
    group_by_field = request.args.get('group_by', 'os_info')
    query = Asset.query
    if filters_raw:
        try:
            filters_structure = json.loads(filters_raw)
            query = build_complex_query(Asset, filters_structure, query)
        except: pass
    group_col = getattr(Asset, group_by_field, Asset.os_info)
    results = db.session.query(group_col, func.count(Asset.id).label('count')).group_by(group_col).all()
    data = [{'label': r[0] or 'Unknown', 'value': r[1]} for r in results]
    return jsonify(data)

@main_bp.route('/api/groups', methods=['POST'])
def api_create_group():
    data = request.json
    name = data.get('name')
    parent_id = data.get('parent_id')
    filter_query = data.get('filter_query')
    is_dynamic = True if filter_query else False
    if parent_id == '': parent_id = None
    if not name: return jsonify({'error': 'Имя обязательно'}), 400
    new_group = Group(name=name, parent_id=parent_id, filter_query=filter_query, is_dynamic=is_dynamic)
    db.session.add(new_group)
    db.session.commit()
    return jsonify({'id': new_group.id, 'name': new_group.name, 'is_dynamic': is_dynamic}), 201

@main_bp.route('/api/groups/<int:id>', methods=['PUT'])
def api_update_group(id):
    group = Group.query.get_or_404(id)
    data = request.json
    
    # 🔥 ИСПРАВЛЕННЫЙ БЛОК 🔥
    if 'name' in data:
        group.name = data['name']
    if 'parent_id' in data:
        new_parent_id = data['parent_id']
        if new_parent_id == '': new_parent_id = None
        if new_parent_id and int(new_parent_id) == group.id: return jsonify({'error': 'Группа не может быть родителем самой себя'}), 400
        group.parent_id = new_parent_id
    if 'filter_query' in data:
        group.filter_query = data['filter_query'] if data['filter_query'] else None
        group.is_dynamic = bool(data['filter_query'])
        
    db.session.commit()
    return jsonify({'success': True})

@main_bp.route('/api/groups/<int:id>', methods=['DELETE'])
def api_delete_group(id):
    group = Group.query.get_or_404(id)
    move_to_id = request.args.get('move_to')
    if move_to_id: Asset.query.filter_by(group_id=id).update({'group_id': move_to_id})
    db.session.delete(group)
    db.session.commit()
    return jsonify({'success': True})

@main_bp.route('/api/groups/tree')
def api_get_tree():
    all_groups = Group.query.all()
    tree = build_group_tree(all_groups)
    flat_list = []
    def flatten(nodes, level=0):
        for node in nodes:
            flat_list.append({'id': node['id'], 'name': '  ' * level + node['name'], 'is_dynamic': node.get('is_dynamic', False)})
            flatten(node['children'], level + 1)
    flatten(tree)
    return jsonify({'tree': tree, 'flat': flat_list})

@main_bp.route('/groups', methods=['POST'])
def manage_groups():
    name = request.form.get('name')
    parent_id = request.form.get('parent_id')
    if parent_id == '': parent_id = None
    db.session.add(Group(name=name, parent_id=parent_id))
    db.session.commit()
    return redirect(url_for('main.index'))

@main_bp.route('/asset/<int:id>')
def asset_detail(id):
    asset = Asset.query.get_or_404(id)
    all_groups = Group.query.all()
    ports_detail = []
    if asset.open_ports:
        for port_str in asset.open_ports.split(', '):
            if '/' in port_str:
                port_id, service = port_str.split('/', 1)
                ports_detail.append({'port': port_id, 'service': service if service else 'unknown'})
    scan_history = [{'date': asset.last_scanned, 'status': asset.status, 'ports_count': len(asset.open_ports.split(', ')) if asset.open_ports else 0}]
    return render_template('asset_detail.html', asset=asset, ports_detail=ports_detail, scan_history=scan_history, all_groups=all_groups)

@main_bp.route('/asset/<int:id>/history')
def asset_history(id):
    asset = Asset.query.get_or_404(id)
    all_groups = Group.query.all()
    group_tree = build_group_tree(all_groups)
    changes = AssetChangeLog.query.filter_by(asset_id=id).order_by(AssetChangeLog.changed_at.desc()).all()
    services = ServiceInventory.query.filter_by(asset_id=id, is_active=True).all()
    return render_template('asset_history.html', asset=asset, changes=changes, services=services, group_tree=group_tree, all_groups=all_groups)

@main_bp.route('/api/asset/<int:id>/history')
def api_asset_history(id):
    changes = AssetChangeLog.query.filter_by(asset_id=id).order_by(AssetChangeLog.changed_at.desc()).limit(100).all()
    return jsonify({'asset_id': id, 'total_changes': len(changes), 'changes': [change.to_dict() for change in changes]})

@main_bp.route('/api/asset/<int:id>/services')
def api_asset_services(id):
    services = ServiceInventory.query.filter_by(asset_id=id).all()
    return jsonify({'asset_id': id, 'total_services': len(services), 'active_services': len([s for s in services if s.is_active]), 'services': [s.to_dict() for s in services]})

@main_bp.route('/asset/<int:id>/service/<int:service_id>/toggle', methods=['POST'])
def toggle_service_status(id, service_id):
    service = ServiceInventory.query.get_or_404(service_id)
    if service.asset_id != id: return jsonify({'error': 'Service does not belong to this asset'}), 400
    service.is_active = not service.is_active
    db.session.commit()
    return jsonify({'success': True, 'is_active': service.is_active})

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
    asset.group_id = group_id if group_id else None
    db.session.commit()
    flash('Группа обновлена', 'success')
    return redirect(url_for('main.asset_detail', id=id))

@main_bp.route('/asset/<int:id>/delete')
def delete_asset(id):
    asset = Asset.query.get_or_404(id)
    db.session.delete(asset)
    db.session.commit()
    flash('Актив удалён', 'warning')
    return redirect(url_for('main.index'))

@main_bp.route('/asset/<int:id>/scan-nmap', methods=['POST'])
def scan_asset_nmap(id):
    from scanner import run_nmap_scan
    asset = Asset.query.get_or_404(id)
    scan_job = ScanJob(scan_type='nmap', target=asset.ip_address, status='pending')
    db.session.add(scan_job)
    db.session.commit()
    thread = threading.Thread(target=run_nmap_scan, args=(scan_job.id, asset.ip_address, None))
    thread.daemon = True
    thread.start()
    flash(f'Nmap сканирование запущено для {asset.ip_address}', 'info')
    return redirect(url_for('main.asset_detail', id=id))

@main_bp.route('/api/assets/bulk-delete', methods=['POST'])
def bulk_delete_assets():
    data = request.json
    asset_ids = data.get('ids', [])
    if not asset_ids: return jsonify({'error': 'No IDs provided'}), 400
    deleted_count = Asset.query.filter(Asset.id.in_(asset_ids)).delete(synchronize_session=False)
    db.session.commit()
    return jsonify({'success': True, 'deleted': deleted_count, 'message': f'Удалено активов: {deleted_count}'})

@main_bp.route('/api/assets/bulk-move', methods=['POST'])
def bulk_move_assets():
    data = request.json
    asset_ids = data.get('ids', [])
    group_id = data.get('group_id')
    if group_id == '': group_id = None
    elif group_id: group_id = int(group_id)
    if not asset_ids: return jsonify({'error': 'No IDs provided'}), 400
    moved_count = Asset.query.filter(Asset.id.in_(asset_ids)).update({'group_id': group_id}, synchronize_session=False)
    db.session.commit()
    return jsonify({'success': True, 'moved': moved_count, 'message': f'Перемещено активов: {moved_count}'})