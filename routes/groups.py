# routes/groups.py
"""
Маршруты для управления группами активов.
Включает CRUD операции, иерархическое дерево и массовые операции.
"""
from flask import Blueprint, request, jsonify
from extensions import db
from models import AssetGroup, Asset, ActivityLog
from utils import MOSCOW_TZ
from models.base import asset_groups
import ipaddress
import json


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
    Возвращает список всех групп с полями id, name, parent_id, asset_count, depth.
    JS сам построит иерархию.
    """
    try:
        from utils import build_group_tree

        # Получаем все группы
        groups = AssetGroup.query.order_by(AssetGroup.name).all()

        # Строим дерево с depth используя существующую утилиту
        tree = build_group_tree(groups)

        # Преобразуем дерево в плоский список с сохранением depth
        def flatten_tree(tree_nodes, result=None):
            if result is None:
                result = []
            for node in tree_nodes:
                # Создаем копию узла без children для плоского списка
                flat_node = {
                    'id': node['id'],
                    'name': node['name'],
                    'parent_id': node['parent_id'],
                    'asset_count': node.get('asset_count', 0),
                    'is_dynamic': node.get('is_dynamic', False),
                    'depth': node.get('depth', 0)
                }
                result.append(flat_node)
                # Рекурсивно добавляем дочерние элементы
                if node.get('children'):
                    flatten_tree(node['children'], result)
            return result

        result = flatten_tree(tree)

        # Подсчет количества активов без группы (не имеющих связей в asset_groups)
        # Используем NOT IN для исключения активов, у которых есть хоть одна связь с группой
        ungrouped_count = db.session.query(Asset).filter(
            ~Asset.id.in_(
                db.session.query(asset_groups.c.asset_id).distinct()
            )
        ).count()

        return jsonify({
            'flat': result,
            'ungrouped_count': ungrouped_count
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
    mode = data.get('mode')

    
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
        # Обработка режима и правил фильтрации
    if mode == 'dynamic':
        filter_rules = data.get('filter_rules', [])
        new_group.is_dynamic = True
        new_group.filter_rules = json.dumps(filter_rules)
    elif mode == 'cidr':
        cidr_network = data.get('cidr_network')
        cidr_mask = data.get('cidr_mask')
        if cidr_network and cidr_mask:
            description = f"CIDR: {cidr_network}/{cidr_mask}"
            new_group.description = description

    
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

@groups_bp.route('/<int:group_id>', methods=['GET'])
def get_group(group_id):
    """Получение информации о группе по ID"""
    group = AssetGroup.query.get_or_404(group_id)
    return jsonify(group.to_dict())


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
    
    parent_id = data.get('parent_id')
    mode = data.get('mode')

    # Обработка имени
    if name and name != group.name:
        if AssetGroup.query.filter_by(name=name).first():
            return jsonify({'error': 'Группа с таким именем уже существует'}), 400
        group.name = name

    # Обработка родительской группы
    
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
    # Обработка режима (dynamic/cidr/manual) и правил фильтрации
    if mode == 'dynamic':
        filter_rules = data.get('filter_rules', [])
        group.is_dynamic = True
        group.filter_rules = json.dumps(filter_rules)
    elif mode == 'manual':
        group.is_dynamic = False
        group.filter_rules = None
    elif mode == 'cidr':
        # CIDR режим обрабатывается отдельно через generate_cidr_groups
        pass


    db.session.commit()
    
    return jsonify(group.to_dict())

@groups_bp.route('/<int:group_id>', methods=['DELETE'])
def delete_group(group_id):
    """Удаление группы"""
    group = AssetGroup.query.get_or_404(group_id)
    data = request.get_json() or {}
    
    move_to_id = data.get('move_to_id')
    
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