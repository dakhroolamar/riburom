"""Merge the Phase B marketplace migration heads.

Revision ID: 9b2d4f6c8e10
Revises: 3f7a9c2d1e64, 7e4c91d2ab30, 7f1c9e4a6b20
Create Date: 2026-08-20

This is a graph-only Alembic merge. The referenced migrations have already
performed the schema changes; this revision only gives Alembic one head for
production upgrades.
"""

revision = '9b2d4f6c8e10'
down_revision = ('3f7a9c2d1e64', '7e4c91d2ab30', '7f1c9e4a6b20')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
