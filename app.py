#!/usr/bin/env python3
"""
Точка входа для запуска приложения Network Asset Manager.
Запуск: python app.py
"""
import uvicorn
import sys
import os

# Добавляем backend в path для корректных импортов
backend_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'backend')
sys.path.insert(0, backend_path)

if __name__ == "__main__":
    print("Starting Network Asset Manager...")
    print("Database: SQLite (/workspace/instance/app.db)")
    print("Docs: http://localhost:8000/docs")
    
    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
        log_level="info"
    )
