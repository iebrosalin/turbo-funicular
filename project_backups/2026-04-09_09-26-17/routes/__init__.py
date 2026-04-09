# routes/__init__.py
from .main import main_bp
from .scans import scans_bp
from .utilities import utilities_bp

def register_blueprints(app):
    app.register_blueprint(main_bp)
    app.register_blueprint(scans_bp)
    app.register_blueprint(utilities_bp)