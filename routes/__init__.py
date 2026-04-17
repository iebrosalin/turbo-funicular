from .main import main_bp, groups_bp
from .scans import scans_bp
from .wazuh import wazuh_bp
from .osquery import osquery_bp
from .utilities import utilities_bp

def register_blueprints(app):
    app.register_blueprint(main_bp)
    app.register_blueprint(scans_bp)
    app.register_blueprint(wazuh_bp)
    app.register_blueprint(osquery_bp)
    app.register_blueprint(utilities_bp)
    app.register_blueprint(groups_bp)
