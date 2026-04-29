"""add mac_vendor columns

Revision ID: 20260429_214500
Revises: df858c2c27e5
Create Date: 2026-04-29 21:45:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20260429_214500'
down_revision = 'df858c2c27e5'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Добавляем колонку mac_address, если её нет
    with op.batch_alter_table('assets') as batch_op:
        batch_op.add_column(sa.Column('mac_address', sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column('vendor', sa.String(length=255), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('assets') as batch_op:
        batch_op.drop_column('vendor')
        batch_op.drop_column('mac_address')
