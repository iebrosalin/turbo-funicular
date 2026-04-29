"""restore_removed_asset_columns

Revision ID: df858c2c27e5
Revises: 20260429_130046
Create Date: 2026-04-29 13:09:59.549808

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'df858c2c27e5'
down_revision = '20260429_130046'
branch_labels = None
depends_on = None


def upgrade():
    # Добавляем удалённые колонки обратно в таблицу assets
    op.add_column('assets', sa.Column('group_id', sa.Integer(), nullable=True))
    op.add_column('assets', sa.Column('last_seen', sa.DateTime(), nullable=True))
    op.add_column('assets', sa.Column('mac_address', sa.String(17), nullable=True))
    op.add_column('assets', sa.Column('notes', sa.Text(), nullable=True))
    op.add_column('assets', sa.Column('os_info', sa.String(255), nullable=True))
    
    # Создаём индекс для group_id если нужно
    op.create_index(op.f('ix_assets_group_id'), 'assets', ['group_id'], unique=False)


def downgrade():
    # Удаляем добавленные колонки
    op.drop_index(op.f('ix_assets_group_id'), table_name='assets')
    op.drop_column('assets', 'os_info')
    op.drop_column('assets', 'notes')
    op.drop_column('assets', 'mac_address')
    op.drop_column('assets', 'last_seen')
    op.drop_column('assets', 'group_id')
