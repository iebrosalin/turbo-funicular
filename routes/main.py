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
    
    flat_list = []
    def flatten(nodes, level=0):
        for node in nodes:
            flat_list.append({
                'id': node['id'], 
                'name': node['name'], # Убрал отступы, их делает фронт
                'count': node['count'],
                'parent_id': node.get('parent_id'), # Добавил parent_id для дерева
                'is_dynamic': node.get('is_dynamic', False)
            })
            flatten(node['children'], level + 1)
            
    # Добавим корневые элементы с явным parent_id=None
    # Функция build_group_tree уже возвращает структуру, но для flat списка нужно пройтись по всем группам
    # Проще вернуть просто список всех групп с parent_id
    simple_flat = []
    for g in all_groups:
        count = Asset.query.filter_by(group_id=g.id).count()
        simple_flat.append({
            'id': g.id,
            'name': g.name,
            'parent_id': g.parent_id,
            'count': count,
            'is_dynamic': g.is_dynamic
        })
    
    return jsonify({'tree': tree, 'flat': simple_flat})

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