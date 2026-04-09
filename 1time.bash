python -c "
from app import app, db
from models import Asset
with app.app_context():
    # Список новых колонок, которые нужно добавить
    new_columns = [
        'device_role VARCHAR(100)',
        'device_tags TEXT',
        'scanners_used TEXT',
        'data_source VARCHAR(20)',
        'wazuh_agent_id VARCHAR(50)',
        'osquery_status VARCHAR(20)',
        'osquery_last_seen DATETIME',
        'osquery_cpu VARCHAR(255)',
        'osquery_ram VARCHAR(50)',
        'osquery_disk VARCHAR(50)',
        'osquery_os VARCHAR(255)',
        'osquery_kernel VARCHAR(255)',
        'osquery_uptime INTEGER',
        'osquery_node_key VARCHAR(100)',
        'osquery_version VARCHAR(50)'
    ]
    
    for col_def in new_columns:
        col_name = col_def.split()[0]
        try:
            db.session.execute(db.text(f'ALTER TABLE asset ADD COLUMN {col_def}'))
            print(f'✅ Добавлена колонка: {col_name}')
        except Exception as e:
            if 'duplicate column name' in str(e).lower():
                print(f'ℹ️ Колонка {col_name} уже существует')
            else:
                print(f'⚠️ Ошибка при добавлении {col_name}: {e}')
    
    db.session.commit()
    print('✅ Миграция базы данных завершена')
"