# app.py
"""
Точка входа приложения Asset Management System.
Инициализация Flask, базы данных, очередей сканирования и регистрация модулей.
"""
import os
from flask import Flask, render_template
from extensions import db, migrate
from models import Asset, AssetGroup, ScanJob, ServiceInventory, ActivityLog, ScanResult
from utils import MOSCOW_TZ
from utils.scan_queue import scan_queue_manager, utility_scan_queue_manager

# Импорт蓝图 (Blueprints)
from routes.dashboard import dashboard_bp
from routes.main import main_bp
from routes.groups import groups_bp
from routes.scans import scans_bp


def _init_debug_groups():
    """
    Создает набор базовых групп активов для отладки.
    Выполняется только если в БД еще нет групп.
    Все данные создаются только на стороне клиента через API.
    """
    # Проверяем, есть ли уже группы
    existing_groups = AssetGroup.query.count()
    if existing_groups > 0:
        return  # Группы уже существуют, не создаем дубликаты

    # Создаем иерархию групп для тестирования дерева
    debug_groups = [
        # Корневые группы
        {'name': 'Инфраструктура', 'description': 'Основная инфраструктура компании', 'parent_id': None},
        {'name': 'Серверы', 'description': 'Физические и виртуальные серверы', 'parent_id': None},
        {'name': 'Сеть', 'description': 'Сетевое оборудование', 'parent_id': None},
        {'name': 'Рабочие станции', 'description': 'Компьютеры пользователей', 'parent_id': None},

        # Подгруппы Инфраструктуры
        {'name': 'ЦОД', 'description': 'Центр обработки данных', 'parent_name': 'Инфраструктура'},
        {'name': 'Облако', 'description': 'Облачные сервисы', 'parent_name': 'Инфраструктура'},

        # Подгруппы Серверы
        {'name': 'Linux', 'description': 'Серверы на базе Linux', 'parent_name': 'Серверы'},
        {'name': 'Windows', 'description': 'Серверы на базе Windows', 'parent_name': 'Серверы'},
        {'name': 'Базы данных', 'description': 'Серверы СУБД', 'parent_name': 'Серверы'},

        # Подгруппы Сеть
        {'name': 'Маршрутизаторы', 'description': 'Роутеры и шлюзы', 'parent_name': 'Сеть'},
        {'name': 'Коммутаторы', 'description': 'Свитчи', 'parent_name': 'Сеть'},
        {'name': 'Firewall', 'description': 'Межсетевые экраны', 'parent_name': 'Сеть'},

        # Подгруппы Рабочие станции
        {'name': 'Отдел разработки', 'description': 'Компьютеры разработчиков', 'parent_name': 'Рабочие станции'},
        {'name': 'Отдел продаж', 'description': 'Компьютеры менеджеров', 'parent_name': 'Рабочие станции'},
        {'name': 'Бухгалтерия', 'description': 'Компьютеры бухгалтерии', 'parent_name': 'Рабочие станции'},

        # Вложенные подгруппы (3 уровень)
        {'name': 'Production', 'description': 'Продакшен серверы', 'parent_name': 'Linux'},
        {'name': 'Staging', 'description': 'Тестовые серверы', 'parent_name': 'Linux'},
        {'name': 'PostgreSQL', 'description': 'Серверы PostgreSQL', 'parent_name': 'Базы данных'},
        {'name': 'MySQL', 'description': 'Серверы MySQL', 'parent_name': 'Базы данных'},
    ]

    # Словарь для хранения созданных групп по имени
    created_groups = {}

    # Сначала создаем корневые группы (без parent_name)
    for group_data in debug_groups:
        if group_data.get('parent_name') is None:
            new_group = AssetGroup(
                name=group_data['name'],
                description=group_data['description'],
                parent_id=None
            )
            db.session.add(new_group)
            created_groups[group_data['name']] = new_group

    db.session.commit()

    # Затем создаем подгруппы
    for group_data in debug_groups:
        parent_name = group_data.get('parent_name')
        if parent_name:
            parent_group = created_groups.get(parent_name)
            if parent_group:
                new_group = AssetGroup(
                    name=group_data['name'],
                    description=group_data['description'],
                    parent_id=parent_group.id
                )
                db.session.add(new_group)
                created_groups[group_data['name']] = new_group

    # Логирование создания
    log = ActivityLog(
        asset_id=None,
        event_type='system_init',
        description='Созданы базовые группы для отладки',
        details={'groups_count': len(debug_groups)}
    )
    db.session.add(log)

    db.session.commit()


def create_app():
    """Фабрика приложения Flask"""
    app = Flask(__name__)
    
    # Конфигурация
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-key-change-in-production')
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///assets.db')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max upload
    
    # Инициализация расширений
    db.init_app(app)
    migrate.init_app(app, db)
    
    # Регистрация Blueprint'ов
    app.register_blueprint(main_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(scans_bp)
    app.register_blueprint(groups_bp)
    
    # Создание таблиц БД, если не существуют
    with app.app_context():
        db.create_all()
        
        # Инициализация базовых групп для отладки (только если БД пуста)
        _init_debug_groups()
        
        # Запуск менеджеров очередей
        # Передаем app контекст в потоки
        scan_queue_manager.start_worker(app)
        utility_scan_queue_manager.start_worker(app)
    
    # Фильтры Jinja2 для удобного отображения данных
    @app.template_filter('format_datetime')
    def format_datetime_filter(value, format='%d.%m.%Y %H:%M'):
        if not value:
            return ''
        return value.strftime(format)

    @app.template_filter('resolve_hostname')
    def resolve_hostname_filter(ip_address):
        """Попытка найти первое доменное имя для IP из БД"""
        # Простая реализация: ищем в таблице Asset актив с таким IP и берем первый dns_name или hostname
        # В реальном приложении лучше кэшировать это или делать через JOIN в запросе
        try:
            asset = Asset.query.filter_by(ip_address=ip_address).first()
            if asset:
                if asset.fqdn:
                    return asset.fqdn
                if asset.dns_names and len(asset.dns_names) > 0:
                    return asset.dns_names[0]
                if asset.hostname:
                    return asset.hostname
        except:
            pass
        return None

    @app.route('/')
    def index_redirect():
        """Перенаправление с корня на дашборд"""
        from flask import redirect, url_for
        return redirect(url_for('dashboard.index'))

    @app.errorhandler(404)
    def not_found_error(error):
        return render_template('404.html'), 404

    @app.errorhandler(500)
    def internal_error(error):
        db.session.rollback()
        return render_template('500.html'), 500

    return app

if __name__ == '__main__':
    app = create_app()
    # Отладочный режим только для разработки
    debug_mode = os.environ.get('FLASK_DEBUG', 'False').lower() in ['true', '1', 'yes']
    app.run(host='0.0.0.0', port=5000, debug=debug_mode)