"""add reusable service image galleries

Revision ID: 7f1c9e4a6b20
Revises: 2c8e4a7f1b90
Create Date: 2026-08-20 15:50:00
"""
from alembic import op
import sqlalchemy as sa

revision = '7f1c9e4a6b20'
down_revision = '2c8e4a7f1b90'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if 'service_images' not in set(inspector.get_table_names()):
        op.create_table(
            'service_images',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('service_id', sa.Integer(), nullable=False),
            sa.Column('image_url', sa.String(length=500), nullable=False),
            sa.Column('alt_text', sa.String(length=300), nullable=True),
            sa.Column('sort_order', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(['service_id'], ['services.id'], ondelete='CASCADE'),
        )
    existing_indexes = {idx['name'] for idx in sa.inspect(bind).get_indexes('service_images')}
    if 'ix_service_images_service_sort' not in existing_indexes:
        op.create_index('ix_service_images_service_sort', 'service_images', ['service_id', 'sort_order'], unique=False)


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if 'service_images' not in set(inspector.get_table_names()):
        return
    existing_indexes = {idx['name'] for idx in inspector.get_indexes('service_images')}
    if 'ix_service_images_service_sort' in existing_indexes:
        op.drop_index('ix_service_images_service_sort', table_name='service_images')
    op.drop_table('service_images')
