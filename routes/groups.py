# routes/groups.py
"""
Маршруты для управления группами активов.
Включает CRUD операции, иерархическое дерево и массовые операции.
"""
from flask import Blueprint, request, jsonify
from extensions import db
from models import AssetGroup, Asset, ActivityLog
from models.base import asset_groups
from utils import MOSCOW_TZ
import ipaddress

# Определяем Blueprint с префиксом /api/groups
groups_bp = Blueprint('groups', __name__, url_prefix='/api/groups')

@groups_bp.route('', methods=['GET'])
def list_groups():
    """Получение списка всех групп (плоский список)"""
    try:
        groups = AssetGroup.query.order_by(AssetGroup.name).all()
        return jsonify([g.to_dict() for g in groups])
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@groups_bp.route('/tree', methods=['GET'])
def get_group_tree():
    """
    Получение плоского списка групп для построения дерева на клиенте.
    Возвращает список всех групп с полями id, name, parent_id, asset_count.
    JS сам построит иерархию.
    """
    try:
        groups = AssetGroup.query.order_by(AssetGroup.name).all()
        
        # Подсчет количества активов в каждой группе (оптимизировано)
        # Создаем словарь {group_id: count}
        asset_counts = db.session.query(
            db.func.count(asset_groups.c.asset_id).label('count'),
            asset_groups.c.group_id
        ).group_by(asset_groups.c.group_id).all()
        
        count_map = {row.group_id: row.count for row in asset_counts}
        
        result = []
        for g in groups:
            result.append({
                'id': g.id,
                'name': g.name,
                'parent_id': g.parent_id,
                'asset_count': count_map.get(g.id, 0),
                'is_dynamic': 'DYNAMIC_RULES' in (g.description or '') # Простая эвристика
            })
            
        # Добавляем статистику для "Без группы" (активы, не входящие ни в одну группу)
        # Это требует более сложного запроса, пока вернем 0 или посчитаем отдельно если нужно
        # Для простоты пока оставим только группы. 
        # Если нужно точно считать "ungrouped", это делается через запрос к Asset где нет связей в asset_groups
        
        return jsonify({
            'flat': result,
            'ungrouped_count': 0 # Заглушка, можно реализовать отдельным запросом
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@groups_bp.route('', methods=['POST'])
def create_group():
    """Создание новой группы"""
    data = request.get_json()
    
    if not data:
        return jsonify({'error': 'Нет данных в запросе'}), 400

    name = data.get('name')
    if not name:
        return jsonify({'error': 'Название группы обязательно'}), 400
    
    # Проверка уникальности
    if AssetGroup.query.filter_by(name=name).first():
        return jsonify({'error': 'Группа с таким именем уже существует'}), 400
    
    parent_id = data.get('parent_id')
    description = data.get('description', '')
    
    # Валидация parent_id если передан
    if parent_id:
        parent = AssetGroup.query.get(parent_id)
        if not parent:
            return jsonify({'error': 'Родительская группа не найдена'}), 404

    new_group = AssetGroup(
        name=name,
        description=description,
        parent_id=parent_id
    )
    
    db.session.add(new_group)
    
    # Логирование
    log = ActivityLog(
        asset_id=None,
        event_type='group_created',
        description=f"Создана группа '{name}'",
        details={'id': new_group.id, 'parent_id': parent_id}
    )
    db.session.add(log)
    
    db.session.commit()
    
    return jsonify(new_group.to_dict()), 201

@groups_bp.route('/<int:group_id>', methods=['PUT'])
def update_group(group_id):
    """Обновление информации о группе"""
    group = AssetGroup.query.get_or_404(group_id)
    data = request.get_json()
    
    if not data:
        return jsonify({'error': 'Нет данных в запросе'}), 400

    name = data.get('name')
    if name and name != group.name:
        if AssetGroup.query.filter_by(name=name).first():
            return jsonify({'error': 'Группа с таким именем уже существует'}), 400
        group.name = name
    
    if 'description' in data:
        group.description = data['description']
    
    if 'parent_id' in data:
        new_parent_id = data['parent_id']
        
        # Нельзя сделать родителем себя
        if new_parent_id == group.id:
            return jsonify({'error': 'Группа не может быть своим собственным родителем'}), 400
        
        # Проверка на цикл: новый родитель не должен быть потомком текущей группы
        if new_parent_id:
            # Простая проверка на прямых детей
            child_ids = [g.id for g in group.children]
            if new_parent_id in child_ids:
                return jsonify({'error': 'Нельзя сделать родителем прямую дочернюю группу'}), 400
            
            if not AssetGroup.query.get(new_parent_id):
                return jsonify({'error': 'Новая родительская группа не найдена'}), 404
        
        group.parent_id = new_parent_id
    
    db.session.commit()
    
    return jsonify(group.to_dict())

@groups_bp.route('/<int:group_id>', methods=['DELETE'])
def delete_group(group_id):
    """Удаление группы"""
    group = AssetGroup.query.get_or_404(group_id)
    data = request.get_json() or {}
    
    move_to_id = data.get('move_assets_to')
    
    if group.assets:
        if move_to_id:
            target_group = AssetGroup.query.get(move_to_id)
            if not target_group:
                return jsonify({'error': 'Целевая группа не найдена'}), 404
            
            for asset in group.assets:
                if target_group not in asset.groups:
                    asset.groups.append(target_group)
                if group in asset.groups:
                    asset.groups.remove(group)
        else:
            for asset in group.assets:
                asset.groups.remove(group)
    
    db.session.delete(group)
    db.session.commit()
    
    return jsonify({'message': f'Группа "{group.name}" удалена'})

@groups_bp.route('/<int:group_id>/assets', methods=['GET'])
def get_group_assets(group_id):
    """Получение списка активов в группе"""
    group = AssetGroup.query.get_or_404(group_id)
    assets = group.assets
    return jsonify([a.to_dict() for a in assets])

@groups_bp.route('/cidr/generate', methods=['POST'])
def generate_cidr_groups():
    """Генерация иерархии групп на основе CIDR диапазона"""
    data = request.get_json()
    
    if not data:
        return jsonify({'error': 'Нет данных в запросе'}), 400

    network_str = data.get('network')
    mask = int(data.get('mask', 24))
    parent_id = data.get('parent_id')
    
    if not network_str:
        return jsonify({'error': 'CIDR сеть обязательна'}), 400
    
    try:
        network = ipaddress.ip_network(network_str, strict=False)
    except ValueError as e:
        return jsonify({'error': f'Неверный формат CIDR: {str(e)}'}), 400
    
    created_count = 0
    try:
        subnets = list(network.subnets(new_prefix=mask))
    except ValueError as e:
        return jsonify({'error': f'Неверная маска подсети: {str(e)}'}), 400
    
    if len(subnets) > 1000:
        return jsonify({'error': f'Слишком много подсетей ({len(subnets)}). Увеличьте маску.'}), 400
    
    for subnet in subnets:
        group_name = str(subnet)
        if AssetGroup.query.filter_by(name=group_name).first():
            continue
        
        new_group = AssetGroup(
            name=group_name,
            description=f'Авто-группа для подсети {group_name}',
            parent_id=parent_id
        )
        db.session.add(new_group)
        created_count += 1
    
    db.session.commit()
    
    return jsonify({
        'message': f'Создано {created_count} групп',
        'count': created_count
    })

@groups_bp.route('/dynamic/rules', methods=['POST'])
def save_dynamic_rules():
    """Сохранение правил для динамической группы (заглушка)"""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Нет данных'}), 400

    group_id = data.get('group_id')
    rules = data.get('rules', [])
    
    group = AssetGroup.query.get_or_404(group_id)
    group.description = f"DYNAMIC_RULES: {str(rules)}" 
    db.session.commit()
    
    return jsonify({'message': 'Правила сохранены'})