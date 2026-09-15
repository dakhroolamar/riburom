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
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    columns = {
        column['name']: column
        for column in inspector.get_columns('site_settings')
    }

    if 'hero_animation_video' in columns:
        column = columns['hero_animation_video']
        column_type = str(column['type']).lower()
        if 'varchar(500)' not in column_type or not column['nullable']:
            raise RuntimeError(
                'Unexpected schema for site_settings.hero_animation_video: '
                'expected nullable VARCHAR(500).'
            )
        return

    op.add_column(
        'site_settings',
        sa.Column('hero_animation_video', sa.String(length=500), nullable=True),
    )


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    columns = {
        column['name'] for column in inspector.get_columns('site_settings')
    }

    if 'hero_animation_video' in columns:
        op.drop_column('site_settings', 'hero_animation_video')
