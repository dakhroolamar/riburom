"""Add instantly published traveller reviews."""
from alembic import op
import sqlalchemy as sa

revision = 'a9c4d7e2f015'
down_revision = 'f8b3c7d0e124'
branch_labels = None
depends_on = None


def upgrade():
    if 'traveller_reviews' not in sa.inspect(op.get_bind()).get_table_names():
        op.create_table('traveller_reviews',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('name', sa.String(80), nullable=False),
            sa.Column('rating', sa.Integer(), nullable=False),
            sa.Column('comment', sa.String(600), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.CheckConstraint('rating >= 1 AND rating <= 5', name='ck_review_rating'))


def downgrade():
    op.drop_table('traveller_reviews')
