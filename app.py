import os
from flask import Flask
from extensions import db
from routes import register_blueprints
# Убираем прямой импорт scanner здесь, если он не нужен для конфигурации
# import scanner 

def create_app():
    app = Flask(__name__)

    # 1. Конфигурация
    basedir = os.path.abspath(os.path.dirname(__file__))
    instance_dir = os.path.join(basedir, 'instance')
    
    if not os.path.exists(instance_dir):
        os.makedirs(instance_dir)

    db_path = os.path.join(instance_dir, 'app.db')
    
    app.config['SECRET_KEY'] = 'dev-secret-key-change-in-production'
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['UPLOAD_FOLDER'] = os.path.join(basedir, 'uploads')
    app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

    # 2. Инициализация расширений (Привязка app к db)
    db.init_app(app)

    # 3. Регистрация маршрутов
    register_blueprints(app)

    # 4. Создание таблиц и начальных данных ТОЛЬКО внутри контекста
    with app.app_context():
        try:
            # Создаем таблицы
            db.create_all()
            print(f"✅ Таблицы БД созданы/проверены: {db_path}")

            # Проверка данных теперь безопасна, так как мы внутри контекста
            # и db уже инициализирован через init_app выше.
            from models import Group
            if not Group.query.first():
                root = Group(name="Root")
                db.session.add(root)
                db.session.commit()
                print("✅ Создана корневая группа 'Root'")

        except Exception as e:
            print(f"❌ Ошибка создания таблиц БД или начальных данных: {e}")
            # Пробрасываем ошибку дальше, чтобы приложение не запустилось в сломанном состоянии
            raise

    return app

if __name__ == '__main__':
    print(f"📁 Текущая директория: {os.getcwd()}")
    print("🚀 Запуск сервера...")
    
    try:
        app = create_app()
        app.run(host='0.0.0.0', port=5000, debug=True)
    except Exception as e:
        print(f"🛑 Критическая ошибка запуска: {e}")