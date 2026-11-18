"""Store editable invoice details alongside historical invoice totals."""
from alembic import op
import sqlalchemy as sa

revision = 'd73b6fc21a80'
down_revision = 'c8f1a2d3e470'
branch_labels = None
depends_on = None


def upgrade():
    columns = {column['name'] for column in sa.inspect(op.get_bind()).get_columns('control_invoices')}
    if 'details' not in columns:
        op.add_column('control_invoices', sa.Column('details', sa.JSON(), nullable=True))
    if 'version' not in columns:
        op.add_column('control_invoices', sa.Column('version', sa.Integer(), nullable=False, server_default='1'))


def downgrade():
    with op.batch_alter_table('control_invoices') as batch:
        batch.drop_column('version')
        batch.drop_column('details')
