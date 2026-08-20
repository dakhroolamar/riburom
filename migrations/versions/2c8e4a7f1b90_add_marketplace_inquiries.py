"""Add independent marketplace enquiries.

Revision ID: 2c8e4a7f1b90
Revises: 6a4b7c9e2d10
Create Date: 2026-08-20
"""
from alembic import op
import sqlalchemy as sa


revision = '2c8e4a7f1b90'
down_revision = '6a4b7c9e2d10'
branch_labels = None
depends_on = None


def upgrade():
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
    op.create_index('ix_marketplace_inquiries_email', 'marketplace_inquiries', ['email'])
    op.create_index('ix_marketplace_inquiries_status', 'marketplace_inquiries', ['status'])
    op.create_index('ix_marketplace_inquiries_created_at', 'marketplace_inquiries', ['created_at'])
    op.create_index('ix_marketplace_inquiries_provider_id', 'marketplace_inquiries', ['provider_id'])
    op.create_index('ix_marketplace_inquiries_service_id', 'marketplace_inquiries', ['service_id'])


def downgrade():
    op.drop_index('ix_marketplace_inquiries_service_id', table_name='marketplace_inquiries')
    op.drop_index('ix_marketplace_inquiries_provider_id', table_name='marketplace_inquiries')
    op.drop_index('ix_marketplace_inquiries_created_at', table_name='marketplace_inquiries')
    op.drop_index('ix_marketplace_inquiries_status', table_name='marketplace_inquiries')
    op.drop_index('ix_marketplace_inquiries_email', table_name='marketplace_inquiries')
    op.drop_table('marketplace_inquiries')
