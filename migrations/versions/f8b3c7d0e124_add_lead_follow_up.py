"""Add next actions and follow-up dates to the existing Control Room desk."""
from alembic import op
import sqlalchemy as sa

revision = 'f8b3c7d0e124'
down_revision = 'f7a2b6c9d013'
branch_labels = None
depends_on = None


def upgrade():
    columns = {c['name'] for c in sa.inspect(op.get_bind()).get_columns('control_leads')}
    with op.batch_alter_table('control_leads') as batch:
        if 'next_action' not in columns:
            batch.add_column(sa.Column('next_action', sa.String(500), nullable=False, server_default=''))
        if 'follow_up' not in columns:
            batch.add_column(sa.Column('follow_up', sa.Date()))


def downgrade():
    with op.batch_alter_table('control_leads') as batch:
        batch.drop_column('follow_up')
        batch.drop_column('next_action')
