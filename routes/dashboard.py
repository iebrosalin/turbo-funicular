# routes/dashboard.py
"""
Маршруты для главного дашборда (список активов, группировка, экспорт).
"""
from flask import Blueprint, render_template, request, jsonify, send_file
import io
import csv
import json
from models import Asset, AssetGroup
from extensions import db
from sqlalchemy import or_

dashboard_bp = Blueprint('dashboard', __name__)

@dashboard_bp.route('/')
@dashboard_bp.route('/dashboard')
def index():
    """Главная страница дашборда"""
    return render_template('dashboard.html')

@dashboard_bp.route('/api/assets')
def get_assets():
    """API для получения списка активов с фильтрацией, поиском и пагинацией"""
    # Параметры запроса
    search = request.args.get('search', '')
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    group_filter = request.args.get('group', '')
    
    query = Asset.query
    
    # Поиск по IP, hostname, DNS именам
    if search:
        search_term = f"%{search}%"
        query = query.filter(
            or_(
                Asset.ip_address.like(search_term),
                Asset.hostname.like(search_term),
                Asset.fqdn.like(search_term)
                # Поиск по JSON массиву dns_names сложнее в стандартном SQL, 
                # для SQLite можно использовать LIKE по строковому представлению или игнорировать
            )
        )
    
    # Фильтр по группе
    if group_filter:
        group = AssetGroup.query.filter_by(name=group_filter).first()
        if group:
            query = query.filter(Asset.groups.contains(group))
        else:
            # Если группа не найдена, возвращаем пустой результат
            query = query.filter(Asset.id == -1)
    
    # Сортировка (по умолчанию по IP)
    sort_by = request.args.get('sort', 'ip_address')
    order = request.args.get('order', 'asc')
    
    valid_sort_columns = ['ip_address', 'hostname', 'os_family', 'status', 'device_type', 'created_at']
    if sort_by in valid_sort_columns:
        col = getattr(Asset, sort_by)
        if order == 'desc':
            query = query.order_by(col.desc())
        else:
            query = query.order_by(col.asc())
    
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    assets = pagination.items
    
    result = []
    for asset in assets:
        item = asset.to_dict()
        # Добавляем имена групп для удобства
        item['group_names'] = [g.name for g in asset.groups]
        result.append(item)
    
    return jsonify({
        'items': result,
        'total': pagination.total,
        'pages': pagination.pages,
        'current_page': page,
        'per_page': per_page
    })

@dashboard_bp.route('/api/groups')
def get_groups():
    """API для получения списка всех групп"""
    groups = AssetGroup.query.all()
    return jsonify([g.to_dict() for g in groups])

@dashboard_bp.route('/api/export/assets')
def export_assets():
    """Экспорт активов в CSV или JSON"""
    format_type = request.args.get('format', 'csv')
    search = request.args.get('search', '')
    # Здесь можно добавить логику повторения фильтрации из get_assets
    # Для краткости берем все или базовый поиск
    query = Asset.query
    if search:
        search_term = f"%{search}%"
        query = query.filter(
            or_(
                Asset.ip_address.like(search_term),
                Asset.hostname.like(search_term)
            )
        )
    
    assets = query.all()
    
    if format_type == 'json':
        data = [a.to_dict() for a in assets]
        output = io.BytesIO()
        output.write(json.dumps(data, indent=2, ensure_ascii=False).encode('utf-8'))
        output.seek(0)
        return send_file(
            output,
            mimetype='application/json',
            as_attachment=True,
            download_name=f'assets_export_{len(assets)}.json'
        )
    
    elif format_type == 'csv':
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Заголовки
        headers = ['ID', 'IP Address', 'Hostname', 'FQDN', 'OS', 'Type', 'Status', 'Ports', 'Groups']
        writer.writerow(headers)
        
        for asset in assets:
            writer.writerow([
                asset.id,
                asset.ip_address,
                asset.hostname or '',
                asset.fqdn or '',
                f"{asset.os_family or ''} {asset.os_version or ''}",
                asset.device_type,
                asset.status,
                ','.join(map(str, asset.open_ports or [])),
                ','.join([g.name for g in asset.groups])
            ])
        
        binary_output = io.BytesIO()
        binary_output.write(output.getvalue().encode('utf-8'))
        binary_output.seek(0)
        
        return send_file(
            binary_output,
            mimetype='text/csv',
            as_attachment=True,
            download_name=f'assets_export_{len(assets)}.csv'
        )
    
    return jsonify({'error': 'Unsupported format'}), 400