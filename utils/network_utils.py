import ipaddress
from models import db, Group

def create_cidr_groups(network_str, mask_prefix, parent_id=None):
    """
    Создает группы для подсетей внутри указанной сети.
    
    :param network_str: Строка сети в формате CIDR (например, "192.168.0.0/16")
    :param mask_prefix: Префикс маски для подгрупп (например, 24 для /24)
    :param parent_id: ID родительской группы (опционально)
    :return: Список созданных объектов Group
    """
    try:
        network = ipaddress.ip_network(network_str, strict=False)
        subnets = network.subnets(new_prefix=mask_prefix)
        
        created_groups = []
        
        for subnet in subnets:
            group_name = str(subnet)
            
            # Проверяем, существует ли уже группа с таким именем и родителем
            existing_group = Group.query.filter_by(
                name=group_name, 
                parent_id=parent_id
            ).first()
            
            if not existing_group:
                new_group = Group(
                    name=group_name,
                    parent_id=parent_id,
                    description=f"Автоматически созданная группа для подсети {group_name}"
                )
                db.session.add(new_group)
                created_groups.append(new_group)
        
        db.session.commit()
        return created_groups
    
    except Exception as e:
        db.session.rollback()
        raise ValueError(f"Ошибка при создании CIDR групп: {str(e)}")