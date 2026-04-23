# app.py
"""
Точка входа приложения Asset Management System.
Инициализация Flask, базы данных, очередей сканирования и регистрация модулей.
"""
import os
from dotenv import load_dotenv

# Загрузка переменных окружения из .env файла
load_dotenv()

from flask import Flask, render_template
from extensions import db, migrate
from models import Asset, AssetGroup, ScanJob, ServiceInventory, ActivityLog, ScanResult
from utils import MOSCOW_TZ
from utils.scan_queue import scan_queue_manager, utility_scan_queue_manager

# Импорт blueprint (Blueprints)
from routes.dashboard import dashboard_bp
from routes.main import main_bp
from routes.groups import groups_bp
from routes.scans import scans_bp

def _init_debug_groups():
    """
    Функция отключена - создание тестовых групп удалено.
    """
    pass


def create_app():
    """Фабрика приложения Flask"""
    app = Flask(__name__)
    
    # Конфигурация из переменных окружения (загружаются из .env файла)
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-key-change-in-production')
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///assets.db')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['MAX_CONTENT_LENGTH'] = int(os.environ.get('MAX_CONTENT_LENGTH', 16 * 1024 * 1024))  # 16MB max upload
    
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