"""Add independent marketplace enquiries.

Revision ID: 2c8e4a7f1b90
Revises: 6a4b7c9e2d10
Create Date: 2026-08-20

The application bootstrap currently calls ``db.create_all()`` before Alembic
runs.  SQLAlchemy therefore may already have created this table and its model
indexes.  This migration is intentionally idempotent so a deployment can
recover from a partially-applied migration without failing on DuplicateTable.
"""
from alembic import op
import sqlalchemy as sa


revision = '2c8e4a7f1b90'
down_revision = '6a4b7c9e2d10'
branch_labels = None
depends_on = None


INDEXES = (
    ('ix_marketplace_inquiries_email', ['email']),
    ('ix_marketplace_inquiries_status', ['status']),
    ('ix_marketplace_inquiries_created_at', ['created_at']),
    ('ix_marketplace_inquiries_provider_id', ['provider_id']),
    ('ix_marketplace_inquiries_service_id', ['service_id']),
)


def _existing_table_and_indexes(table_name):
    inspector = sa.inspect(op.get_bind())
    tables = set(inspector.get_table_names())
    if table_name not in tables:
        return False, set()
    indexes = {
        index['name']
        for index in inspector.get_indexes(table_name)
        if index.get('name')
    }
    return True, indexes


def _ensure_indexes(table_name):
    table_exists, existing_indexes = _existing_table_and_indexes(table_name)
    if not table_exists:
        return

    for index_name, columns in INDEXES:
        if index_name not in existing_indexes:
            op.create_index(index_name, table_name, columns)


def upgrade():
    table_exists, _ = _existing_table_and_indexes('marketplace_inquiries')

    if not table_exists:
        op.create_table(
            'marketplace_inquiries',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('provider_id', sa.Integer(), nullable=True),
            sa.Column('service_id', sa.Integer(), nullable=True),
            sa.Column('provider_name', sa.String(length=200), nullable=False),
            sa.Column('service_name', sa.String(length=200), nullable=False),
            sa.Column('category_name', sa.String(length=120), nullable=False),
            sa.Column('name', sa.String(length=200), nullable=False),
            sa.Column('email', sa.String(length=254), nullable=False),
            sa.Column('phone', sa.String(length=40), nullable=True),
            sa.Column('travel_date', sa.String(length=120), nullable=True),
            sa.Column('return_date', sa.String(length=120), nullable=True),
            sa.Column('travellers', sa.Integer(), nullable=True),
            sa.Column('pickup_location', sa.String(length=300), nullable=True),
            sa.Column('drop_location', sa.String(length=300), nullable=True),
            sa.Column('check_in', sa.String(length=120), nullable=True),
            sa.Column('check_out', sa.String(length=120), nullable=True),
            sa.Column('rooms', sa.Integer(), nullable=True),
            sa.Column('nights', sa.Integer(), nullable=True),
            sa.Column('language', sa.String(length=120), nullable=True),
            sa.Column('duration', sa.String(length=120), nullable=True),
            sa.Column('requirements', sa.Text(), nullable=True),
            sa.Column('status', sa.String(length=40), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(['provider_id'], ['providers.id'], ondelete='SET NULL'),
            sa.ForeignKeyConstraint(['service_id'], ['services.id'], ondelete='SET NULL'),
            sa.PrimaryKeyConstraint('id'),
        )

    _ensure_indexes('marketplace_inquiries')


def downgrade():
    table_exists, existing_indexes = _existing_table_and_indexes('marketplace_inquiries')
    if not table_exists:
        return

    for index_name, _ in reversed(INDEXES):
        if index_name in existing_indexes:
            op.drop_index(index_name, table_name='marketplace_inquiries')

    op.drop_table('marketplace_inquiries')
