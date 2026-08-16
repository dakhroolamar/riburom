"""Add the Phase B PackageItem marketplace bridge.

Revision ID: 3f7a9c2d1e64
Revises: 8d1f2c4a9b01
Create Date: 2026-08-17
"""
from alembic import op
import sqlalchemy as sa


revision = '3f7a9c2d1e64'
down_revision = '8d1f2c4a9b01'
branch_labels = None
depends_on = None


def upgrade():
    inspector = sa.inspect(op.get_bind())
    if 'packages' not in inspector.get_table_names():
        raise RuntimeError(
            'Cannot create package_items: the existing Package table is required.'
        )

    if 'package_items' in inspector.get_table_names():
        raise RuntimeError(
            'Unexpected pre-existing package_items table; refusing to adopt it silently.'
        )

    op.create_table(
        'package_items',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column(
            'package_id',
            sa.Integer(),
            sa.ForeignKey('packages.id', ondelete='CASCADE'),
            nullable=False,
        ),
        sa.Column(
            'service_id',
            sa.Integer(),
            sa.ForeignKey('services.id', ondelete='RESTRICT'),
            nullable=False,
        ),
        sa.Column('sort_order', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.UniqueConstraint(
            'package_id',
            'service_id',
            name='uq_package_item_package_service',
        ),
    )
    op.create_index(
        'ix_package_items_package_sort',
        'package_items',
        ['package_id', 'sort_order'],
        unique=False,
    )
    op.create_index(
        'ix_package_items_service_id',
        'package_items',
        ['service_id'],
        unique=False,
    )


def downgrade():
    op.drop_index('ix_package_items_service_id', table_name='package_items')
    op.drop_index('ix_package_items_package_sort', table_name='package_items')
    op.drop_table('package_items')
