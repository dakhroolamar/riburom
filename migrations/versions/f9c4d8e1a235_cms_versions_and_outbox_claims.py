"""Protect overlapping CMS edits and lease durable background deliveries."""
from alembic import op
import sqlalchemy as sa

revision = 'f9c4d8e1a235'
down_revision = 'a9c4d7e2f015'
branch_labels = None
depends_on = None


def upgrade():
    additions = {
        'site_settings': [sa.Column('version', sa.Integer(), nullable=False, server_default='1')],
        'control_website_revisions': [sa.Column('is_backup', sa.Boolean(), nullable=False, server_default=sa.false())],
        'notification_outbox': [sa.Column('claim_token', sa.String(80)), sa.Column('next_attempt_at', sa.DateTime())],
        'traveller_reviews': [sa.Column('is_visible', sa.Boolean(), nullable=False, server_default=sa.true())],
    }
    for table, columns in additions.items():
        existing = {c['name'] for c in sa.inspect(op.get_bind()).get_columns(table)}
        with op.batch_alter_table(table) as batch:
            for column in columns:
                if column.name not in existing:
                    batch.add_column(column)
    indexes = {i['name'] for i in sa.inspect(op.get_bind()).get_indexes('notification_outbox')}
    if 'ix_notification_outbox_next_attempt_at' not in indexes:
        op.create_index('ix_notification_outbox_next_attempt_at', 'notification_outbox', ['next_attempt_at'])


def downgrade():
    with op.batch_alter_table('traveller_reviews') as batch:
        batch.drop_column('is_visible')
    op.drop_index('ix_notification_outbox_next_attempt_at', table_name='notification_outbox')
    with op.batch_alter_table('notification_outbox') as batch:
        batch.drop_column('next_attempt_at')
        batch.drop_column('claim_token')
    with op.batch_alter_table('control_website_revisions') as batch:
        batch.drop_column('is_backup')
    with op.batch_alter_table('site_settings') as batch:
        batch.drop_column('version')
