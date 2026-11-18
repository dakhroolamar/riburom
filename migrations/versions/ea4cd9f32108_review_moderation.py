"""Queue existing traveller reviews for approval and store private attachments."""
from alembic import op
import sqlalchemy as sa

revision = 'ea4cd9f32108'
down_revision = 'd73b6fc21a80'
branch_labels = None
depends_on = None


def upgrade():
    inspector = sa.inspect(op.get_bind())
    if 'status' not in {column['name'] for column in inspector.get_columns('traveller_reviews')}:
        with op.batch_alter_table('traveller_reviews') as batch:
            batch.add_column(sa.Column('status', sa.String(16), nullable=False, server_default='pending'))
            batch.add_column(sa.Column('reply', sa.String(1200)))
            batch.add_column(sa.Column('reply_updated_at', sa.DateTime()))
            batch.add_column(sa.Column('reply_version', sa.Integer(), nullable=False, server_default='0'))
            batch.alter_column('is_visible', existing_type=sa.Boolean(), server_default=sa.false())
        op.execute("UPDATE traveller_reviews SET status = 'declined' WHERE is_visible = false")
        op.execute("UPDATE traveller_reviews SET is_visible = false")
    if 'review_attachments' not in inspector.get_table_names():
        op.create_table('review_attachments',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('review_id', sa.Integer(), sa.ForeignKey('traveller_reviews.id', ondelete='CASCADE'), nullable=False),
            sa.Column('mimetype', sa.String(32), nullable=False),
            sa.Column('content', sa.LargeBinary(), nullable=False))
        op.create_index('ix_review_attachments_review_id', 'review_attachments', ['review_id'])


def downgrade():
    op.drop_table('review_attachments')
    with op.batch_alter_table('traveller_reviews') as batch:
        batch.drop_column('reply_version')
        batch.drop_column('reply_updated_at')
        batch.drop_column('reply')
        batch.drop_column('status')
        batch.alter_column('is_visible', existing_type=sa.Boolean(), server_default=sa.true())
