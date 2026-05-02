"""Migration to add asset change log table."""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_asset_change_log'
down_revision = None  # Укажите предыдущую ревизию, если есть
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'asset_change_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('asset_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('username', sa.String(length=255), nullable=True),
        sa.Column('action', sa.String(length=50), nullable=False),
        sa.Column('changed_fields', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['asset_id'], ['assets.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_asset_change_logs_asset_id'), 'asset_change_logs', ['asset_id'], unique=False)
    op.create_index(op.f('ix_asset_change_logs_created_at'), 'asset_change_logs', ['created_at'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_asset_change_logs_created_at'), table_name='asset_change_logs')
    op.drop_index(op.f('ix_asset_change_logs_asset_id'), table_name='asset_change_logs')
    op.drop_table('asset_change_logs')
