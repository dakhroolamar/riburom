"""Add reusable CMS media and page sections without changing legacy content."""
from alembic import op
import sqlalchemy as sa
import json
from datetime import datetime

revision = 'e6f7a8b9c012'
down_revision = 'd5e8f0a2b341'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('cms_media_assets',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('path', sa.String(1000), nullable=False, unique=True),
        sa.Column('title', sa.String(240), nullable=False),
        sa.Column('alt', sa.String(500), nullable=False),
        sa.Column('caption', sa.String(1000), nullable=False),
        sa.Column('credit', sa.String(500), nullable=False),
        sa.Column('width', sa.Integer()), sa.Column('height', sa.Integer()),
        sa.Column('byte_size', sa.Integer()),
        sa.Column('created_at', sa.DateTime(), nullable=False))
    op.create_table('cms_media_collections',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('key', sa.String(100), nullable=False, unique=True),
        sa.Column('title', sa.String(240), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False))
    op.create_table('cms_media_collection_items',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('collection_id', sa.Integer(), sa.ForeignKey('cms_media_collections.id'), nullable=False),
        sa.Column('asset_id', sa.Integer(), sa.ForeignKey('cms_media_assets.id'), nullable=False),
        sa.Column('position', sa.Integer(), nullable=False),
        sa.Column('focal_x', sa.Integer(), nullable=False),
        sa.Column('focal_y', sa.Integer(), nullable=False),
        sa.Column('organization', sa.String(240), nullable=False),
        sa.Column('url', sa.String(1000), nullable=False),
        sa.Column('label', sa.String(240), nullable=False),
        sa.Column('visible', sa.Boolean(), nullable=False),
        sa.Column('new_tab', sa.Boolean(), nullable=False))
    for column in ('collection_id', 'asset_id'):
        op.create_index('ix_cms_media_collection_items_' + column, 'cms_media_collection_items', [column])
    op.create_table('cms_page_sections',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('page', sa.String(80), nullable=False),
        sa.Column('key', sa.String(80), nullable=False),
        sa.Column('settings', sa.JSON(), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.UniqueConstraint('page', 'key', name='uq_cms_page_section'))
    _register_existing_images()


def _register_existing_images():
    """Register existing references without copying, deleting or downloading files."""
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())
    assets = sa.Table('cms_media_assets', sa.MetaData(), autoload_with=bind)
    paths = set()
    fields = {
        'packages': ['image_file'], 'about_content': ['hero_image'],
        'team_members': ['photo_file'],
        'site_settings': ['header_wordmark', 'header_mark', 'hero_logo', 'blog_image', 'instagram_qr'],
        'providers': ['image_url'], 'services': ['image_url'], 'service_images': ['image_url'],
    }
    for name, names in fields.items():
        if name not in tables:
            continue
        table = sa.Table(name, sa.MetaData(), autoload_with=bind)
        for column in names:
            if column in table.c:
                paths.update(value for value in bind.execute(sa.select(table.c[column])).scalars() if value)
    if 'site_settings' in tables:
        settings = sa.Table('site_settings', sa.MetaData(), autoload_with=bind)
        if 'public_config_json' in settings.c:
            for raw in bind.execute(sa.select(settings.c.public_config_json)).scalars():
                try:
                    theme = json.loads(raw or '{}').get('theme', {})
                    paths.update(v for v in theme.get('section_backgrounds', {}).values() if isinstance(v, str) and v)
                    for gallery in theme.get('galleries', {}).values():
                        paths.update(v for v in gallery if isinstance(v, str) and v)
                except (TypeError, ValueError, AttributeError):
                    continue
    for path in sorted(paths):
        bind.execute(assets.insert().values(path=path, title=path.rsplit('/', 1)[-1][:240],
                     alt='', caption='', credit='', created_at=datetime.utcnow()))


def downgrade():
    # Legacy content and stored files are deliberately retained.
    op.drop_table('cms_page_sections')
    op.drop_table('cms_media_collection_items')
    op.drop_table('cms_media_collections')
    op.drop_table('cms_media_assets')
