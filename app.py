
# app.py
import os
from flask import Flask
from config import Config
from extensions import db
from routes import register_blueprints

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    os.makedirs(app.config['SCAN_RESULTS_FOLDER'], exist_ok=True)
    
    db.init_app(app)
    
    with app.app_context():
        from models import Group # Import models to register them
        db.create_all()
        if not Group.query.first():
            db.session.add(Group(name="Сеть"))
            db.session.commit()
            
    register_blueprints(app)
    return app

if __name__ == '__main__':
    print("📁 Текущая директория:", os.getcwd())
    print("🔍 Путь к БД:", 'sqlite:///assets.db')
    print("🚀 Запуск сервера...")
    app = create_app()
    
    app.run(debug=True, host='10.250.95.39', port=5000)
