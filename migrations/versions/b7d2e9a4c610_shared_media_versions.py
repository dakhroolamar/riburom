"""Protect shared media metadata against overlapping editor saves."""
from alembic import op
import sqlalchemy as sa

revision = 'b7d2e9a4c610'
down_revision = 'f9c4d8e1a235'
branch_labels = None
depends_on = None


def upgrade():
    columns = {column['name'] for column in sa.inspect(op.get_bind()).get_columns('cms_media_assets')}
    if 'version' not in columns:
        with op.batch_alter_table('cms_media_assets') as batch:
            batch.add_column(sa.Column('version', sa.Integer(), nullable=False, server_default='1'))


def downgrade():
    with op.batch_alter_table('cms_media_assets') as batch:
        batch.drop_column('version')
