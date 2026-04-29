"""initial migration

Revision ID: initial
Revises: 
Create Date: 2024-01-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'initial'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Создаем таблицу groups
    op.create_table('groups',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('parent_id', sa.Integer(), nullable=True),
        sa.Column('group_type', sa.String(length=50), nullable=True),
        sa.Column('is_dynamic', sa.Boolean(), nullable=True),
        sa.Column('filter_rules', sa.Text(), nullable=True),
        sa.Column('rule', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['parent_id'], ['groups.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_groups_id'), 'groups', ['id'], unique=False)
    op.create_index(op.f('ix_groups_name'), 'groups', ['name'], unique=True)
    op.create_index(op.f('ix_groups_parent_id'), 'groups', ['parent_id'], unique=False)

    # Создаем таблицу assets
    op.create_table('assets',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('ip_address', sa.String(length=45), nullable=False),
        sa.Column('hostname', sa.String(length=255), nullable=True),
        sa.Column('os_family', sa.String(length=50), nullable=True),
        sa.Column('os_version', sa.String(length=100), nullable=True),
        sa.Column('device_type', sa.String(length=50), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=True),
        sa.Column('location', sa.String(length=100), nullable=True),
        sa.Column('owner', sa.String(length=100), nullable=True),
        sa.Column('dns_names', sa.JSON(), nullable=True),
        sa.Column('fqdn', sa.String(length=255), nullable=True),
        sa.Column('dns_records', sa.JSON(), nullable=True),
        sa.Column('rustscan_ports', sa.JSON(), nullable=True),
        sa.Column('nmap_ports', sa.JSON(), nullable=True),
        sa.Column('open_ports', sa.JSON(), nullable=True),
        sa.Column('last_rustscan', sa.DateTime(), nullable=True),
        sa.Column('last_nmap', sa.DateTime(), nullable=True),
        sa.Column('last_dns_scan', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_assets_id'), 'assets', ['id'], unique=False)
    op.create_index(op.f('ix_assets_ip_address'), 'assets', ['ip_address'], unique=False)
    op.create_index(op.f('ix_assets_hostname'), 'assets', ['hostname'], unique=False)
    op.create_index(op.f('ix_assets_device_type'), 'assets', ['device_type'], unique=False)
    op.create_index(op.f('ix_assets_os_family'), 'assets', ['os_family'], unique=False)
    op.create_index(op.f('ix_assets_status'), 'assets', ['status'], unique=False)

    # Создаем таблицу asset_groups (many-to-many связь)
    op.create_table('asset_groups',
        sa.Column('asset_id', sa.Integer(), nullable=False),
        sa.Column('group_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['asset_id'], ['assets.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['group_id'], ['groups.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('asset_id', 'group_id')
    )
    op.create_index(op.f('ix_asset_groups_asset_id'), 'asset_groups', ['asset_id'], unique=False)
    op.create_index(op.f('ix_asset_groups_group_id'), 'asset_groups', ['group_id'], unique=False)

    # Создаем таблицу scans
    op.create_table('scans',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('target', sa.String(length=500), nullable=False),
        sa.Column('scan_type', sa.String(length=50), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=True),
        sa.Column('progress', sa.Integer(), nullable=True),
        sa.Column('result', sa.Text(), nullable=True),
        sa.Column('group_id', sa.Integer(), nullable=True),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['group_id'], ['groups.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_scans_id'), 'scans', ['id'], unique=False)
    op.create_index(op.f('ix_scans_group_id'), 'scans', ['group_id'], unique=False)

    # Создаем таблицу scan_jobs
    op.create_table('scan_jobs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('scan_id', sa.Integer(), nullable=False),
        sa.Column('job_type', sa.String(length=50), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=True),
        sa.Column('priority', sa.Integer(), nullable=True),
        sa.Column('worker_id', sa.String(length=100), nullable=True),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['scan_id'], ['scans.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_scan_jobs_id'), 'scan_jobs', ['id'], unique=False)
    op.create_index(op.f('ix_scan_jobs_scan_id'), 'scan_jobs', ['scan_id'], unique=False)

    # Создаем таблицу scan_results
    op.create_table('scan_results',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('scan_id', sa.Integer(), nullable=False),
        sa.Column('scan_job_id', sa.Integer(), nullable=True),
        sa.Column('asset_id', sa.Integer(), nullable=True),
        sa.Column('ip_address', sa.String(length=45), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=True),
        sa.Column('ports', sa.JSON(), nullable=True),
        sa.Column('services', sa.JSON(), nullable=True),
        sa.Column('os_info', sa.String(length=255), nullable=True),
        sa.Column('hostname', sa.String(length=255), nullable=True),
        sa.Column('raw_output', sa.Text(), nullable=True),
        sa.Column('scanned_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['scan_id'], ['scans.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['scan_job_id'], ['scan_jobs.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['asset_id'], ['assets.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_scan_results_id'), 'scan_results', ['id'], unique=False)
    op.create_index(op.f('ix_scan_results_scan_id'), 'scan_results', ['scan_id'], unique=False)
    op.create_index(op.f('ix_scan_results_scan_job_id'), 'scan_results', ['scan_job_id'], unique=False)
    op.create_index(op.f('ix_scan_results_asset_id'), 'scan_results', ['asset_id'], unique=False)
    op.create_index(op.f('ix_scan_results_ip_address'), 'scan_results', ['ip_address'], unique=False)

    # Создаем таблицу activity_logs
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

    # Создаем таблицу asset_change_logs
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

    # Создаем таблицу service_inventory
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


def downgrade() -> None:
    # Удаляем новые таблицы
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
    
    # Удаляем индексы и таблицы scan_results, scan_jobs, scans
    op.drop_index(op.f('ix_scan_results_ip_address'), table_name='scan_results')
    op.drop_index(op.f('ix_scan_results_asset_id'), table_name='scan_results')
    op.drop_index(op.f('ix_scan_results_scan_job_id'), table_name='scan_results')
    op.drop_index(op.f('ix_scan_results_scan_id'), table_name='scan_results')
    op.drop_index(op.f('ix_scan_results_id'), table_name='scan_results')
    op.drop_table('scan_results')
    
    op.drop_index(op.f('ix_scan_jobs_scan_id'), table_name='scan_jobs')
    op.drop_index(op.f('ix_scan_jobs_id'), table_name='scan_jobs')
    op.drop_table('scan_jobs')
    
    op.drop_index(op.f('ix_scans_group_id'), table_name='scans')
    op.drop_index(op.f('ix_scans_id'), table_name='scans')
    op.drop_table('scans')
    
    # Удаляем индексы и таблицу assets
    op.drop_index(op.f('ix_assets_status'), table_name='assets')
    op.drop_index(op.f('ix_assets_os_family'), table_name='assets')
    op.drop_index(op.f('ix_assets_device_type'), table_name='assets')
    op.drop_index(op.f('ix_assets_hostname'), table_name='assets')
    op.drop_index(op.f('ix_assets_ip_address'), table_name='assets')
    op.drop_index(op.f('ix_assets_id'), table_name='assets')
    op.drop_table('assets')
    
    # Удаляем индексы и таблицу groups
    op.drop_index(op.f('ix_groups_parent_id'), table_name='groups')
    op.drop_index(op.f('ix_groups_name'), table_name='groups')
    op.drop_index(op.f('ix_groups_id'), table_name='groups')
    op.drop_table('groups')
