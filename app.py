#!/usr/bin/env python3
"""
Точка входа для запуска приложения Network Asset Manager.
Запуск: python app.py
"""
import uvicorn
import sys
import os
import socket

# Добавляем backend в path для корректных импортов
backend_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'backend')
sys.path.insert(0, backend_path)

def get_all_interfaces():
    """Получить все доступные сетевые интерфейсы и их IP-адреса."""
    hostname = socket.gethostname()
    local_ip = socket.gethostbyname(hostname)
    
    interfaces = []
    try:
        # Получаем все адреса хоста
        addr_info = socket.getaddrinfo(hostname, None)
        seen_ips = set()
        
        for info in addr_info:
            ip = info[4][0]
            # Фильтруем только IPv4 и исключаем локальные адреса если нужно
            if ':' not in ip and ip not in seen_ips:  # Простая проверка на IPv6
                seen_ips.add(ip)
                interfaces.append(ip)
        
        # Если не нашли ничего кроме localhost, добавим стандартные варианты
        if not interfaces or interfaces == ['127.0.0.1']:
            interfaces = ['127.0.0.1', local_ip]
            if local_ip != '127.0.0.1':
                interfaces.append(local_ip)
    except Exception:
        interfaces = ['127.0.0.1']
    
    return list(set(interfaces))

if __name__ == "__main__":
    HOST = "0.0.0.0"
    PORT = 8000
    
    print("=" * 60)
    print("🚀 Starting Network Asset Manager...")
    print("=" * 60)
    print(f"Database: SQLite (/workspace/instance/app.db)")
    print("\n🌐 Доступные интерфейсы для подключения:")
    
    # Получаем и выводим все доступные интерфейсы
    available_interfaces = get_all_interfaces()
    for ip in available_interfaces:
        print(f"   ➤ http://{ip}:{PORT}")
    
    print(f"\n📚 API Documentation: http://localhost:{PORT}/docs")
    print(f"🏠 Web Interface:     http://localhost:{PORT}/")
    print("=" * 60)
    
    uvicorn.run(
        "backend.main:app",
        host=HOST,
        port=PORT,
        reload=False,
        log_level="info"
    )
