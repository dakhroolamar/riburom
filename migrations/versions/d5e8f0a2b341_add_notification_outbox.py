"""Add durable notification outbox.

Revision ID: d5e8f0a2b341
Revises: c1d4e6f8a210
Create Date: 2026-09-16
"""
from alembic import op
import sqlalchemy as sa


revision = 'd5e8f0a2b341'
down_revision = 'c1d4e6f8a210'
branch_labels = None
depends_on = None


TABLE_NAME = 'notification_outbox'
UNIQUE_NAME = 'uq_notification_outbox_source_event_channel'
INDEX_NAME = 'ix_notification_outbox_status_created'


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if TABLE_NAME not in inspector.get_table_names():
        op.create_table(
            TABLE_NAME,
            sa.Column('id', sa.Integer(), primary_key=True, nullable=False),
            sa.Column('source_type', sa.String(length=80), nullable=False),
            sa.Column('source_id', sa.String(length=80), nullable=False),
            sa.Column('event_type', sa.String(length=80), nullable=False, server_default='new_enquiry'),
            sa.Column('channel', sa.String(length=30), nullable=False),
            sa.Column('recipient', sa.String(length=320), nullable=False),
            sa.Column('subject', sa.String(length=300), nullable=True),
            sa.Column('body', sa.Text(), nullable=False),
            sa.Column('status', sa.String(length=30), nullable=False, server_default='PENDING'),
            sa.Column('attempts', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('last_error', sa.String(length=500), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), nullable=False),
            sa.Column('sent_at', sa.DateTime(), nullable=True),
            sa.UniqueConstraint(
                'source_type', 'source_id', 'event_type', 'channel',
                name=UNIQUE_NAME,
            ),
        )

    inspector = sa.inspect(bind)
    existing_indexes = {item['name'] for item in inspector.get_indexes(TABLE_NAME)}
    if INDEX_NAME not in existing_indexes:
        op.create_index(
            INDEX_NAME,
            TABLE_NAME,
            ['status', 'created_at'],
            unique=False,
        )


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if TABLE_NAME in inspector.get_table_names():
        op.drop_table(TABLE_NAME)
