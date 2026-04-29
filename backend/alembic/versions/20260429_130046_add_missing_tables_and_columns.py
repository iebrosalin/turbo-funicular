"""add missing tables and columns

Revision ID: 20260429_130046
Revises: initial
Create Date: 2026-04-29 13:00:46.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '20260429_130046'
down_revision: Union[str, None] = 'initial'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Проверяем, какие таблицы уже существуют
    from sqlalchemy import inspect
    insp = inspect(op.get_bind())
    existing_tables = insp.get_table_names()
    
    # === Создаем отсутствующие таблицы (если их нет) ===
    
    # Таблица asset_groups (many-to-many связь)
    if 'asset_groups' not in existing_tables:
        op.create_table('asset_groups',
            sa.Column('asset_id', sa.Integer(), nullable=False),
            sa.Column('group_id', sa.Integer(), nullable=False),
            sa.ForeignKeyConstraint(['asset_id'], ['assets.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['group_id'], ['groups.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('asset_id', 'group_id')
        )
        op.create_index(op.f('ix_asset_groups_asset_id'), 'asset_groups', ['asset_id'], unique=False)
        op.create_index(op.f('ix_asset_groups_group_id'), 'asset_groups', ['group_id'], unique=False)
    
    # Таблица activity_logs
    if 'activity_logs' not in existing_tables:
        op.create_table('activity_logs',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('asset_id', sa.Integer(), nullable=True),
            sa.Column('user_id', sa.Integer(), nullable=True),
            sa.Column('action', sa.String(length=100), nullable=False),
            sa.Column('resource_type', sa.String(length=50), nullable=False),
            sa.Column('resource_id', sa.Integer(), nullable=True),
            sa.Column('details', sa.JSON(), nullable=True),
            sa.Column('ip_address', sa.String(length=45), nullable=True),
            sa.Column('user_agent', sa.String(length=255), nullable=True),
            sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=True),
            sa.ForeignKeyConstraint(['asset_id'], ['assets.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index(op.f('ix_activity_logs_id'), 'activity_logs', ['id'], unique=False)
        op.create_index(op.f('ix_activity_logs_asset_id'), 'activity_logs', ['asset_id'], unique=False)
    
    # Таблица asset_change_logs
    if 'asset_change_logs' not in existing_tables:
        op.create_table('asset_change_logs',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('asset_id', sa.Integer(), nullable=False),
            sa.Column('field_name', sa.String(length=100), nullable=False),
            sa.Column('old_value', sa.Text(), nullable=True),
            sa.Column('new_value', sa.Text(), nullable=True),
            sa.Column('changed_by', sa.Integer(), nullable=True),
            sa.Column('change_reason', sa.String(length=255), nullable=True),
            sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=True),
            sa.ForeignKeyConstraint(['asset_id'], ['assets.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index(op.f('ix_asset_change_logs_id'), 'asset_change_logs', ['id'], unique=False)
        op.create_index(op.f('ix_asset_change_logs_asset_id'), 'asset_change_logs', ['asset_id'], unique=False)
    
    # Таблица service_inventory
    if 'service_inventory' not in existing_tables:
        op.create_table('service_inventory',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('asset_id', sa.Integer(), nullable=False),
            sa.Column('port', sa.Integer(), nullable=False),
            sa.Column('protocol', sa.String(length=10), nullable=True),
            sa.Column('state', sa.String(length=50), nullable=True),
            sa.Column('service_name', sa.String(length=100), nullable=True),
            sa.Column('product', sa.String(length=255), nullable=True),
            sa.Column('version', sa.String(length=255), nullable=True),
            sa.Column('extrainfo', sa.Text(), nullable=True),
            sa.Column('ostype', sa.String(length=100), nullable=True),
            sa.Column('devicetype', sa.String(length=100), nullable=True),
            sa.Column('ssl_cert_subject', sa.Text(), nullable=True),
            sa.Column('ssl_cert_issuer', sa.Text(), nullable=True),
            sa.Column('ssl_cert_not_before', sa.DateTime(), nullable=True),
            sa.Column('ssl_cert_not_after', sa.DateTime(), nullable=True),
            sa.Column('ssl_cert_serial', sa.String(length=255), nullable=True),
            sa.Column('scripts', sa.JSON(), nullable=True),
            sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=True),
            sa.Column('updated_at', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['asset_id'], ['assets.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index(op.f('ix_service_inventory_id'), 'service_inventory', ['id'], unique=False)
        op.create_index(op.f('ix_service_inventory_asset_id'), 'service_inventory', ['asset_id'], unique=False)
    
    # Проверяем существующие колонки в assets
    existing_columns = [col['name'] for col in insp.get_columns('assets')]
    
    # === Добавляем отсутствующие колонки в таблицу assets ===
    with op.batch_alter_table('assets', schema=None) as batch_op:
        # Основные поля
        if 'device_type' not in existing_columns:
            batch_op.add_column(sa.Column('device_type', sa.String(length=50), nullable=True))
        if 'os_family' not in existing_columns:
            batch_op.add_column(sa.Column('os_family', sa.String(length=50), nullable=True))
        if 'os_version' not in existing_columns:
            batch_op.add_column(sa.Column('os_version', sa.String(length=100), nullable=True))
        if 'location' not in existing_columns:
            batch_op.add_column(sa.Column('location', sa.String(length=100), nullable=True))
        if 'owner' not in existing_columns:
            batch_op.add_column(sa.Column('owner', sa.String(length=100), nullable=True))
        
        # DNS поля
        if 'dns_names' not in existing_columns:
            batch_op.add_column(sa.Column('dns_names', sa.JSON(), nullable=True))
        if 'fqdn' not in existing_columns:
            batch_op.add_column(sa.Column('fqdn', sa.String(length=255), nullable=True))
        if 'dns_records' not in existing_columns:
            batch_op.add_column(sa.Column('dns_records', sa.JSON(), nullable=True))
        
        # Порты
        if 'rustscan_ports' not in existing_columns:
            batch_op.add_column(sa.Column('rustscan_ports', sa.JSON(), nullable=True))
        if 'nmap_ports' not in existing_columns:
            batch_op.add_column(sa.Column('nmap_ports', sa.JSON(), nullable=True))
        if 'open_ports' not in existing_columns:
            batch_op.add_column(sa.Column('open_ports', sa.JSON(), nullable=True))
        
        # Временные метки сканирований
        if 'last_rustscan' not in existing_columns:
            batch_op.add_column(sa.Column('last_rustscan', sa.DateTime(), nullable=True))
        if 'last_nmap' not in existing_columns:
            batch_op.add_column(sa.Column('last_nmap', sa.DateTime(), nullable=True))
        if 'last_dns_scan' not in existing_columns:
            batch_op.add_column(sa.Column('last_dns_scan', sa.DateTime(), nullable=True))
    
    # Создаем индексы для новых колонок (если они еще не созданы)
    existing_indexes = [idx['name'] for idx in insp.get_indexes('assets')]
    if 'ix_assets_device_type' not in existing_indexes:
        op.create_index(op.f('ix_assets_device_type'), 'assets', ['device_type'], unique=False)
    if 'ix_assets_os_family' not in existing_indexes:
        op.create_index(op.f('ix_assets_os_family'), 'assets', ['os_family'], unique=False)
    if 'ix_assets_status' not in existing_indexes:
        op.create_index(op.f('ix_assets_status'), 'assets', ['status'], unique=False)
    
    # Проверяем существующие колонки в groups
    existing_group_columns = [col['name'] for col in insp.get_columns('groups')]
    
    # === Добавляем отсутствующие колонки в таблицу groups ===
    with op.batch_alter_table('groups', schema=None) as batch_op:
        if 'is_dynamic' not in existing_group_columns:
            batch_op.add_column(sa.Column('is_dynamic', sa.Boolean(), nullable=True))
        if 'filter_rules' not in existing_group_columns:
            batch_op.add_column(sa.Column('filter_rules', sa.Text(), nullable=True))
    
    # === Удаляем лишние/устаревшие колонки из assets (если они существуют) ===
    columns_to_drop = ['group_id', 'last_seen', 'mac_address', 'notes', 'os_info']
    columns_to_drop = [col for col in columns_to_drop if col in existing_columns]
    
    if columns_to_drop:
        # Сначала удаляем индексы для старых колонок
        existing_idx_names = [idx['name'] for idx in insp.get_indexes('assets')]
        if 'ix_assets_group_id' in existing_idx_names:
            op.drop_index(op.f('ix_assets_group_id'), table_name='assets')
        
        with op.batch_alter_table('assets', schema=None) as batch_op:
            for col_name in columns_to_drop:
                batch_op.drop_column(col_name)


def downgrade() -> None:
    # === Восстанавливаем удалённые колонки в assets ===
    with op.batch_alter_table('assets', schema=None) as batch_op:
        batch_op.add_column(sa.Column('group_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('last_seen', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('mac_address', sa.String(length=17), nullable=True))
        batch_op.add_column(sa.Column('notes', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('os_info', sa.String(length=255), nullable=True))
    
    # Восстанавливаем индексы для старых колонок
    op.create_index(op.f('ix_assets_group_id'), 'assets', ['group_id'], unique=False)
    
    # === Удаляем добавленные колонки из groups ===
    with op.batch_alter_table('groups', schema=None) as batch_op:
        batch_op.drop_column('filter_rules')
        batch_op.drop_column('is_dynamic')
    
    # === Удаляем индексы ===
    op.drop_index(op.f('ix_assets_status'), table_name='assets')
    op.drop_index(op.f('ix_assets_os_family'), table_name='assets')
    op.drop_index(op.f('ix_assets_device_type'), table_name='assets')
    
    # === Удаляем добавленные колонки из assets ===
    with op.batch_alter_table('assets', schema=None) as batch_op:
        batch_op.drop_column('last_dns_scan')
        batch_op.drop_column('last_nmap')
        batch_op.drop_column('last_rustscan')
        batch_op.drop_column('open_ports')
        batch_op.drop_column('nmap_ports')
        batch_op.drop_column('rustscan_ports')
        batch_op.drop_column('dns_records')
        batch_op.drop_column('fqdn')
        batch_op.drop_column('dns_names')
        batch_op.drop_column('owner')
        batch_op.drop_column('location')
        batch_op.drop_column('os_version')
        batch_op.drop_column('os_family')
        batch_op.drop_column('device_type')
    
    # === Удаляем таблицы ===
    op.drop_index(op.f('ix_service_inventory_asset_id'), table_name='service_inventory')
    op.drop_index(op.f('ix_service_inventory_id'), table_name='service_inventory')
    op.drop_table('service_inventory')
    
    op.drop_index(op.f('ix_asset_change_logs_asset_id'), table_name='asset_change_logs')
    op.drop_index(op.f('ix_asset_change_logs_id'), table_name='asset_change_logs')
    op.drop_table('asset_change_logs')
    
    op.drop_index(op.f('ix_activity_logs_asset_id'), table_name='activity_logs')
    op.drop_index(op.f('ix_activity_logs_id'), table_name='activity_logs')
    op.drop_table('activity_logs')
    
    op.drop_index(op.f('ix_asset_groups_group_id'), table_name='asset_groups')
    op.drop_index(op.f('ix_asset_groups_asset_id'), table_name='asset_groups')
    op.drop_table('asset_groups')
