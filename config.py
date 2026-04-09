import os
class Config:
    SECRET_KEY = 'super-secret-key-change-me'
    SQLALCHEMY_DATABASE_URI = 'sqlite:///assets.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
    SCAN_RESULTS_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'scan_results')
    MAX_SCAN_THREADS = 5
