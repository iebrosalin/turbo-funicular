# extensions.py
"""
Инициализация расширений Flask (SQLAlchemy, Migrate).
Вынесено в отдельный модуль для избежания циклических импортов.
"""
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate

# Инициализация объектов расширений
db = SQLAlchemy()
migrate = Migrate()