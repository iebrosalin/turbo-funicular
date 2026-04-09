from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from extensions import db
from models import Group, Asset, AssetChangeLog, ServiceInventory, ScanResult, ScanJob
from utils import build_group_tree, build_complex_query, format_moscow_time, MOSCOW_TZ
from sqlalchemy import func
import json
import os
from datetime import datetime
from werkzeug.utils import secure_filename
from flask import current_app

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
    data = [{
        'id': a.id, 
        'ip': a.ip_address, 
        'hostname': a.hostname, 
        'os': a.os_info, 
        'ports': a.open_ports, 
        'group': a.group.name if a.group else 'Без группы', 
        'last_scan': format_moscow_time(a.last_scanned, '%Y-%m-%d %H:%M'),  # 🔥 Москва
        'source': a.data_source or 'manual'
    } for a in assets]
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

@main_bp.route('/groups', methods=['POST'])
def manage_groups():
    name = request.form.get('name'); parent_id = request.form.get('parent_id')
    if parent_id == '': parent_id = None
    db.session.add(Group(name=name, parent_id=parent_id)); db.session.commit()
    return redirect(url_for('main.index'))

@main_bp.route('/asset/<int:id>/history')
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

@main_bp.route('/api/assets/<int:asset_id>/scans')
def get_asset_scans(asset_id):
    search = request.args.get('search', '').strip()
    query = db.session.query(ScanResult, ScanJob).join(ScanJob, isouter=True).filter(ScanResult.asset_id == asset_id)
    if search: query = query.filter(db.or_(ScanJob.scan_type.like(f'%{search}%'), ScanJob.status.like(f'%{search}%')))
    results = query.order_by(ScanResult.scanned_at.desc()).limit(100).all()
    return jsonify([{'id': res.id, 
        'scan_type': job.scan_type if job else 'unknown', 
        'status': job.status if job else 'completed',
        'scanned_at': format_moscow_time(res.scanned_at),  # 🔥 Москва
        'ports': json.loads(res.ports) if res.ports else [], 
        'os': res.os_detection or '-'} for res, job in results])

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

@main_bp.route('/scan', methods=['POST'])
def import_scan():
    from utils import parse_nmap_xml
    
    if 'file' not in request.files:
        flash('Файл не найден', 'danger')
        return redirect(url_for('main.index'))
    
    file = request.files['file']
    group_id = request.form.get('group_id')
    if group_id == '':
        group_id = None
    
    if file and file.filename:
        filename = secure_filename(file.filename)
        filepath = os.path.join(current_app.config.get('UPLOAD_FOLDER', 'uploads'), filename)
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
                    existing.ports_list = data.get('ports_list', '[]')  # 🔥 Обновляем
                    existing.last_scanned = datetime.now(MOSCOW_TZ)
                    existing.status = data.get('status')
                    if group_id and not existing.group_id:
                        existing.group_id = group_id
                    updated_count += 1
                else:
                    # 🔥 Теперь можно передавать ports_list напрямую
                    new_asset = Asset(
                        ip_address=data['ip_address'],
                        hostname=data.get('hostname'),
                        os_info=data.get('os_info'),
                        open_ports=data.get('open_ports'),
                        ports_list=data.get('ports_list', '[]'),  # 🔥 Поле теперь валидно
                        status=data.get('status', 'up'),
                        group_id=group_id,
                        data_source='scanning'
                    )
                    db.session.add(new_asset)
                    created_count += 1
            
            db.session.commit()
            flash(f'Успех! Создано: {created_count}, Обновлено: {updated_count}', 'success')
        except Exception as e:
            flash(f'Ошибка парсинга: {str(e)}', 'danger')
            print(f"❌ Ошибка импорта: {e}")
            import traceback
            traceback.print_exc()
        finally:
            if os.path.exists(filepath):
                os.remove(filepath)
    
    return redirect(url_for('main.index'))

@main_bp.route('/asset/<int:id>/delete')
def delete_asset(id):
    """Удаление актива"""
    asset = Asset.query.get_or_404(id)
    
    # Получаем группу для перенаправления
    group_id = asset.group_id
    
    db.session.delete(asset)
    db.session.commit()
    
    flash(f'Актив {asset.ip_address} удалён', 'warning')
    
    # Перенаправляем на главную с фильтром по группе
    if group_id:
        return redirect(url_for('main.index', group_id=group_id))
    else:
        return redirect(url_for('main.index', ungrouped='true'))
    
@main_bp.route('/asset/<int:id>/update-notes', methods=['POST'])
def update_asset_notes(id):
    """Обновление заметок актива"""
    asset = Asset.query.get_or_404(id)
    notes = request.form.get('notes', '')
    asset.notes = notes
    db.session.commit()
    flash('Заметки обновлены', 'success')
    return redirect(url_for('main.asset_detail', id=id))

@main_bp.route('/asset/<int:id>/update-group', methods=['POST'])
def update_asset_group(id):
    """Обновление группы актива"""
    asset = Asset.query.get_or_404(id)
    group_id = request.form.get('group_id')
    asset.group_id = int(group_id) if group_id and group_id.strip() else None
    db.session.commit()
    flash('Группа обновлена', 'success')
    return redirect(url_for('main.asset_detail', id=id))

@main_bp.route('/asset/<int:id>/scan-nmap', methods=['POST'])
def scan_asset_nmap(id):
    """Запуск Nmap сканирования для актива"""
    from routes.scans import run_nmap_scan
    from flask import current_app
    import threading
    
    asset = Asset.query.get_or_404(id)
    scan_job = ScanJob(scan_type='nmap', target=asset.ip_address, status='pending')
    db.session.add(scan_job)
    db.session.commit()
    
    app_obj = current_app._get_current_object()
    thread = threading.Thread(target=run_nmap_scan, args=(app_obj, scan_job.id, asset.ip_address, None, ''))
    thread.daemon = True
    thread.start()
    
    flash(f'Nmap сканирование запущено для {asset.ip_address}', 'info')
    return redirect(url_for('main.asset_detail', id=id))

@main_bp.route('/asset/<int:id>/taxonomy')
def asset_taxonomy(id):
    """Страница таксономии актива"""
    from utils import generate_asset_taxonomy
    asset = Asset.query.get_or_404(id)
    all_groups = Group.query.all()
    
    # Получаем сервисы для таксономии
    services = ServiceInventory.query.filter_by(asset_id=id, is_active=True).all()
    
    # Генерируем таксономию
    taxonomy_data = generate_asset_taxonomy(asset, services)
    
    return render_template('asset_taxonomy.html', 
                          asset=asset, 
                          taxonomy=taxonomy_data,
                          all_groups=all_groups)

@main_bp.route('/api/groups/tree')
def api_get_tree():
    """Возвращает дерево групп с актуальными счётчиками"""
    all_groups = Group.query.all()
    tree = build_group_tree(all_groups)
    
    # 🔥 Плоский список для удобного обновления на клиенте
    flat_list = []
    def flatten(nodes, level=0):
        for node in nodes:
            flat_list.append({
                'id': node['id'], 
                'name': '  ' * level + node['name'], 
                'count': node['count'],  # 🔥 Актуальный счётчик
                'is_dynamic': node.get('is_dynamic', False)
            })
            flatten(node['children'], level + 1)
    flatten(tree)
    
    return jsonify({'tree': tree, 'flat': flat_list})

@main_bp.route('/asset/<int:id>')
def asset_detail(id):
    """Детальная страница актива"""
    asset = Asset.query.get_or_404(id)
    all_groups = Group.query.all()
    
    # Получаем сервисы для отображения
    services = ServiceInventory.query.filter_by(asset_id=id, is_active=True).all()
    
    return render_template('asset_detail.html', 
                          asset=asset, 
                          all_groups=all_groups,
                          services=services)