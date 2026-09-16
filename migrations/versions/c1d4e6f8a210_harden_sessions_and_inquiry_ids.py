"""Harden staff sessions and marketplace enquiry primary-key generation.

Revision ID: c1d4e6f8a210
Revises: b4c7d9e1f203
Create Date: 2026-09-16
"""
from alembic import op
import sqlalchemy as sa


revision = 'c1d4e6f8a210'
down_revision = 'b4c7d9e1f203'
branch_labels = None
depends_on = None


def _table_names(bind):
    return set(sa.inspect(bind).get_table_names())


def _ensure_session_version(bind):
    if 'users' not in _table_names(bind):
        return
    columns = {column['name'] for column in sa.inspect(bind).get_columns('users')}
    if 'session_version' in columns:
        return
    with op.batch_alter_table('users') as batch_op:
        batch_op.add_column(
            sa.Column('session_version', sa.Integer(), nullable=False, server_default='0')
        )


def _ensure_marketplace_inquiry_id_default(bind):
    if bind.dialect.name != 'postgresql' or 'marketplace_inquiries' not in _table_names(bind):
        return

    row = bind.execute(sa.text(
        """
        SELECT column_default
        FROM information_schema.columns
        WHERE table_schema = current_schema()
          AND table_name = 'marketplace_inquiries'
          AND column_name = 'id'
        """
    )).first()
    if row is None or row[0]:
        return

    bind.execute(sa.text(
        "CREATE SEQUENCE IF NOT EXISTS marketplace_inquiries_id_seq "
        "OWNED BY marketplace_inquiries.id"
    ))
    bind.execute(sa.text(
        "ALTER TABLE marketplace_inquiries "
        "ALTER COLUMN id SET DEFAULT nextval('marketplace_inquiries_id_seq')"
    ))
    bind.execute(sa.text(
        """
        SELECT setval(
            'marketplace_inquiries_id_seq',
            COALESCE((SELECT MAX(id) FROM marketplace_inquiries), 0) + 1,
            false
        )
        """
    ))


def upgrade():
    bind = op.get_bind()
    _ensure_session_version(bind)
    _ensure_marketplace_inquiry_id_default(bind)


def downgrade():
    bind = op.get_bind()
    if 'users' not in _table_names(bind):
        return
    columns = {column['name'] for column in sa.inspect(bind).get_columns('users')}
    if 'session_version' in columns:
        with op.batch_alter_table('users') as batch_op:
            batch_op.drop_column('session_version')
