"""Retain operational partner details and package links for quotes and trips."""
from alembic import op
import sqlalchemy as sa

revision = 'c8f1a2d3e470'
down_revision = 'b7d2e9a4c610'
branch_labels = None
depends_on = None


def upgrade():
    inspector = sa.inspect(op.get_bind())
    if 'control_partner_operations' not in inspector.get_table_names():
        op.create_table('control_partner_operations',
            sa.Column('provider_id', sa.Integer(), sa.ForeignKey('providers.id', ondelete='CASCADE'), primary_key=True),
            sa.Column('contact_person', sa.String(200), nullable=False, server_default=''),
            sa.Column('location', sa.String(240), nullable=False, server_default=''),
            sa.Column('service_area', sa.String(500), nullable=False, server_default=''),
            sa.Column('notes', sa.Text(), nullable=False, server_default=''))
    for table in ('control_trips', 'control_quotes'):
        if 'package_id' not in {c['name'] for c in inspector.get_columns(table)}:
            with op.batch_alter_table(table) as batch:
                batch.add_column(sa.Column('package_id', sa.Integer(), nullable=True))
                batch.create_foreign_key('fk_' + table + '_package', 'packages', ['package_id'], ['id'])


def downgrade():
    for table in ('control_quotes', 'control_trips'):
        with op.batch_alter_table(table) as batch:
            batch.drop_constraint('fk_' + table + '_package', type_='foreignkey')
            batch.drop_column('package_id')
    op.drop_table('control_partner_operations')
