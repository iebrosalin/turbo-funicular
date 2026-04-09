import os
import json
from flask import Flask
from config import Config
from extensions import db
from routes import register_blueprints
from utils import format_moscow_time

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    os.makedirs(app.config['SCAN_RESULTS_FOLDER'], exist_ok=True)
    db.init_app(app)
    
    # 🔥 Фильтр для московского времени
    @app.template_filter('moscow_time')
    def moscow_time_filter(dt, format_str='%Y-%m-%d %H:%M:%S'):
        return format_moscow_time(dt, format_str)
    
    # 🔥 Фильтр для парсинга JSON в шаблонах
    @app.template_filter('fromjson')
    def fromjson_filter(s):
        """Парсит JSON-строку в список/словарь для использования в шаблонах"""
        if not s:
            return []
        try:
            return json.loads(s)
        except (json.JSONDecodeError, TypeError, AttributeError):
            return []
    
    with app.app_context():
        from models import Group, Asset, ScanJob, ScanProfile, WazuhConfig, OsqueryInventory, ServiceInventory
        db.create_all()
        if not Group.query.first():
            db.session.add(Group(name="Сеть"))
            db.session.commit()
    
    register_blueprints(app)
    return app

if __name__ == '__main__':
    print("📁 Текущая директория:", os.getcwd())
    print("🚀 Запуск сервера...")
    app = create_app()
    app.run(debug=True, host='10.250.95.39', port=5000)