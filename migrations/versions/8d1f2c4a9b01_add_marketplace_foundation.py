"""Add Phase A marketplace foundation tables.

Revision ID: 8d1f2c4a9b01
Revises: None
Create Date: 2026-08-16
"""
from datetime import datetime

from alembic import op
import sqlalchemy as sa


revision = '8d1f2c4a9b01'
down_revision = None
branch_labels = None
depends_on = None


PROVIDER_TYPES = [
    ('Guide', 'guide'),
    ('Driver', 'driver'),
    ('Homestay', 'homestay'),
    ('Hotel/Resort', 'hotel-resort'),
    ('Experience Provider', 'experience-provider'),
    ('Trekking/Adventure Provider', 'trekking-adventure-provider'),
    ('Cultural Practitioner', 'cultural-practitioner'),
    ('Community Tourism Provider', 'community-tourism-provider'),
]

SERVICE_CATEGORIES = [
    ('Accommodation', 'accommodation'),
    ('Transportation', 'transportation'),
    ('Guiding', 'guiding'),
    ('Experiences', 'experiences'),
    ('Adventure & Outdoor', 'adventure-outdoor'),
    ('Food & Culinary', 'food-culinary'),
    ('Wellness', 'wellness'),
    ('Events & Activities', 'events-activities'),
    ('Other', 'other'),
]


def upgrade() -> None:
    op.create_table(
        'provider_types',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(length=120), nullable=False),
        sa.Column('slug', sa.String(length=140), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('sort_order', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.UniqueConstraint('slug', name='uq_provider_types_slug'),
        if_not_exists=True,
    )
    op.create_index('ix_provider_types_slug', 'provider_types', ['slug'], unique=False, if_not_exists=True)
    op.create_index('ix_provider_types_is_active', 'provider_types', ['is_active'], unique=False, if_not_exists=True)
    op.create_index('ix_provider_types_sort_order', 'provider_types', ['sort_order'], unique=False, if_not_exists=True)

    op.create_table(
        'service_categories',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(length=120), nullable=False),
        sa.Column('slug', sa.String(length=140), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('sort_order', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.UniqueConstraint('slug', name='uq_service_categories_slug'),
        if_not_exists=True,
    )
    op.create_index('ix_service_categories_slug', 'service_categories', ['slug'], unique=False, if_not_exists=True)
    op.create_index('ix_service_categories_is_active', 'service_categories', ['is_active'], unique=False, if_not_exists=True)
    op.create_index('ix_service_categories_sort_order', 'service_categories', ['sort_order'], unique=False, if_not_exists=True)

    op.create_table(
        'providers',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('slug', sa.String(length=240), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('email', sa.String(length=254), nullable=True),
        sa.Column('phone', sa.String(length=40), nullable=True),
        sa.Column('status', sa.String(length=40), nullable=False, server_default='DRAFT'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.UniqueConstraint('slug', name='uq_providers_slug'),
        if_not_exists=True,
    )
    op.create_index('ix_providers_slug', 'providers', ['slug'], unique=False, if_not_exists=True)
    op.create_index('ix_providers_is_active', 'providers', ['is_active'], unique=False, if_not_exists=True)

    op.create_table(
        'provider_type_assignments',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('provider_id', sa.Integer(), nullable=False),
        sa.Column('provider_type_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['provider_id'], ['providers.id']),
        sa.ForeignKeyConstraint(['provider_type_id'], ['provider_types.id']),
        sa.UniqueConstraint('provider_id', 'provider_type_id', name='uq_provider_type_assignment'),
        if_not_exists=True,
    )
    op.create_index('ix_provider_type_assignments_provider_id', 'provider_type_assignments', ['provider_id'], unique=False, if_not_exists=True)
    op.create_index('ix_provider_type_assignments_provider_type_id', 'provider_type_assignments', ['provider_type_id'], unique=False, if_not_exists=True)

    op.create_table(
        'services',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('provider_id', sa.Integer(), nullable=False),
        sa.Column('category_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('slug', sa.String(length=240), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=40), nullable=False, server_default='DRAFT'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['provider_id'], ['providers.id']),
        sa.ForeignKeyConstraint(['category_id'], ['service_categories.id']),
        sa.UniqueConstraint('provider_id', 'slug', name='uq_service_provider_slug'),
        if_not_exists=True,
    )
    op.create_index('ix_services_provider_id', 'services', ['provider_id'], unique=False, if_not_exists=True)
    op.create_index('ix_services_category_id', 'services', ['category_id'], unique=False, if_not_exists=True)
    op.create_index('ix_services_status', 'services', ['status'], unique=False, if_not_exists=True)

    now = datetime.utcnow()
    provider_type_table = sa.table(
        'provider_types',
        sa.column('name', sa.String(length=120)),
        sa.column('slug', sa.String(length=140)),
        sa.column('is_active', sa.Boolean()),
        sa.column('sort_order', sa.Integer()),
        sa.column('created_at', sa.DateTime()),
        sa.column('updated_at', sa.DateTime()),
    )
    op.bulk_insert(
        provider_type_table,
        [
            {
                'name': name,
                'slug': slug,
                'is_active': True,
                'sort_order': index,
                'created_at': now,
                'updated_at': now,
            }
            for index, (name, slug) in enumerate(PROVIDER_TYPES, start=1)
        ],
    )

    service_category_table = sa.table(
        'service_categories',
        sa.column('name', sa.String(length=120)),
        sa.column('slug', sa.String(length=140)),
        sa.column('is_active', sa.Boolean()),
        sa.column('sort_order', sa.Integer()),
        sa.column('created_at', sa.DateTime()),
        sa.column('updated_at', sa.DateTime()),
    )
    op.bulk_insert(
        service_category_table,
        [
            {
                'name': name,
                'slug': slug,
                'is_active': True,
                'sort_order': index,
                'created_at': now,
                'updated_at': now,
            }
            for index, (name, slug) in enumerate(SERVICE_CATEGORIES, start=1)
        ],
    )


def downgrade() -> None:
    op.drop_index('ix_services_status', table_name='services', if_exists=True)
    op.drop_index('ix_services_category_id', table_name='services', if_exists=True)
    op.drop_index('ix_services_provider_id', table_name='services', if_exists=True)
    op.drop_table('services', if_exists=True)

    op.drop_index('ix_provider_type_assignments_provider_type_id', table_name='provider_type_assignments', if_exists=True)
    op.drop_index('ix_provider_type_assignments_provider_id', table_name='provider_type_assignments', if_exists=True)
    op.drop_table('provider_type_assignments', if_exists=True)

    op.drop_index('ix_providers_is_active', table_name='providers', if_exists=True)
    op.drop_index('ix_providers_slug', table_name='providers', if_exists=True)
    op.drop_table('providers', if_exists=True)

    op.drop_index('ix_service_categories_sort_order', table_name='service_categories', if_exists=True)
    op.drop_index('ix_service_categories_is_active', table_name='service_categories', if_exists=True)
    op.drop_index('ix_service_categories_slug', table_name='service_categories', if_exists=True)
    op.drop_table('service_categories', if_exists=True)

    op.drop_index('ix_provider_types_sort_order', table_name='provider_types', if_exists=True)
    op.drop_index('ix_provider_types_is_active', table_name='provider_types', if_exists=True)
    op.drop_index('ix_provider_types_slug', table_name='provider_types', if_exists=True)
    op.drop_table('provider_types', if_exists=True)
