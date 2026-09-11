"""Add optional homepage hero animation video to SiteSettings.

Revision ID: b4c7d9e1f203
Revises: 9b2d4f6c8e10
Create Date: 2026-08-22
"""

from alembic import op
import sqlalchemy as sa


revision = 'b4c7d9e1f203'
down_revision = '9b2d4f6c8e10'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('site_settings', sa.Column('hero_animation_video', sa.String(length=500), nullable=True))


def downgrade():
    op.drop_column('site_settings', 'hero_animation_video')
