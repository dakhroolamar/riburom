"""Store multiple selected services on marketplace enquiries.

Revision ID: 7e4c91d2ab30
Revises: 2c8e4a7f1b90
Create Date: 2026-08-20
"""
from alembic import op
import sqlalchemy as sa


revision = '7e4c91d2ab30'
down_revision = '2c8e4a7f1b90'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column['name'] for column in inspector.get_columns('marketplace_inquiries')}
    if 'selected_services_json' not in columns:
        op.add_column(
            'marketplace_inquiries',
            sa.Column('selected_services_json', sa.Text(), nullable=True),
        )


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column['name'] for column in inspector.get_columns('marketplace_inquiries')}
    if 'selected_services_json' in columns:
        op.drop_column('marketplace_inquiries', 'selected_services_json')
