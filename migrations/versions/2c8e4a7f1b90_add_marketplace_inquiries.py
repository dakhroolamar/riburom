"""Add independent marketplace enquiries.

Revision ID: 2c8e4a7f1b90
Revises: 6a4b7c9e2d10
Create Date: 2026-08-20

The application bootstrap may create SQLAlchemy tables/indexes before Alembic
runs. The migration therefore uses IF NOT EXISTS semantics so deployment can
recover cleanly when the schema objects already exist.
"""
from alembic import op
import sqlalchemy as sa


revision = '2c8e4a7f1b90'
down_revision = '6a4b7c9e2d10'
branch_labels = None
depends_on = None


TABLE_SQLITE = """
CREATE TABLE IF NOT EXISTS marketplace_inquiries (
    id INTEGER NOT NULL PRIMARY KEY,
    provider_id INTEGER NULL REFERENCES providers(id) ON DELETE SET NULL,
    service_id INTEGER NULL REFERENCES services(id) ON DELETE SET NULL,
    provider_name VARCHAR(200) NOT NULL,
    service_name VARCHAR(200) NOT NULL,
    category_name VARCHAR(120) NOT NULL,
    name VARCHAR(200) NOT NULL,
    email VARCHAR(254) NOT NULL,
    phone VARCHAR(40) NULL,
    travel_date VARCHAR(120) NULL,
    return_date VARCHAR(120) NULL,
    travellers INTEGER NULL,
    pickup_location VARCHAR(300) NULL,
    drop_location VARCHAR(300) NULL,
    check_in VARCHAR(120) NULL,
    check_out VARCHAR(120) NULL,
    rooms INTEGER NULL,
    nights INTEGER NULL,
    language VARCHAR(120) NULL,
    duration VARCHAR(120) NULL,
    requirements TEXT NULL,
    status VARCHAR(40) NOT NULL,
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL
)
"""

TABLE_POSTGRESQL = TABLE_SQLITE.replace(
    'id INTEGER NOT NULL PRIMARY KEY,',
    'id SERIAL PRIMARY KEY,',
    1,
)

INDEX_SQL = (
    "CREATE INDEX IF NOT EXISTS ix_marketplace_inquiries_email "
    "ON marketplace_inquiries (email)",
    "CREATE INDEX IF NOT EXISTS ix_marketplace_inquiries_status "
    "ON marketplace_inquiries (status)",
    "CREATE INDEX IF NOT EXISTS ix_marketplace_inquiries_created_at "
    "ON marketplace_inquiries (created_at)",
    "CREATE INDEX IF NOT EXISTS ix_marketplace_inquiries_provider_id "
    "ON marketplace_inquiries (provider_id)",
    "CREATE INDEX IF NOT EXISTS ix_marketplace_inquiries_service_id "
    "ON marketplace_inquiries (service_id)",
)


def upgrade():
    bind = op.get_bind()
    dialect = bind.dialect.name

    if dialect in {'postgresql', 'sqlite'}:
        table_sql = TABLE_POSTGRESQL if dialect == 'postgresql' else TABLE_SQLITE
        op.execute(sa.text(table_sql))
        for statement in INDEX_SQL:
            op.execute(sa.text(statement))
        return

    # Fallback for other SQLAlchemy dialects.
    inspector = sa.inspect(bind)
    if 'marketplace_inquiries' not in inspector.get_table_names():
        op.create_table(
            'marketplace_inquiries',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('provider_id', sa.Integer(), nullable=True),
            sa.Column('service_id', sa.Integer(), nullable=True),
            sa.Column('provider_name', sa.String(length=200), nullable=False),
            sa.Column('service_name', sa.String(length=200), nullable=False),
            sa.Column('category_name', sa.String(length=120), nullable=False),
            sa.Column('name', sa.String(length=200), nullable=False),
            sa.Column('email', sa.String(length=254), nullable=False),
            sa.Column('phone', sa.String(length=40), nullable=True),
            sa.Column('travel_date', sa.String(length=120), nullable=True),
            sa.Column('return_date', sa.String(length=120), nullable=True),
            sa.Column('travellers', sa.Integer(), nullable=True),
            sa.Column('pickup_location', sa.String(length=300), nullable=True),
            sa.Column('drop_location', sa.String(length=300), nullable=True),
            sa.Column('check_in', sa.String(length=120), nullable=True),
            sa.Column('check_out', sa.String(length=120), nullable=True),
            sa.Column('rooms', sa.Integer(), nullable=True),
            sa.Column('nights', sa.Integer(), nullable=True),
            sa.Column('language', sa.String(length=120), nullable=True),
            sa.Column('duration', sa.String(length=120), nullable=True),
            sa.Column('requirements', sa.Text(), nullable=True),
            sa.Column('status', sa.String(length=40), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(['provider_id'], ['providers.id'], ondelete='SET NULL'),
            sa.ForeignKeyConstraint(['service_id'], ['services.id'], ondelete='SET NULL'),
            sa.PrimaryKeyConstraint('id'),
        )

    existing = {index['name'] for index in sa.inspect(bind).get_indexes('marketplace_inquiries')}
    for index_name, columns in (
        ('ix_marketplace_inquiries_email', ['email']),
        ('ix_marketplace_inquiries_status', ['status']),
        ('ix_marketplace_inquiries_created_at', ['created_at']),
        ('ix_marketplace_inquiries_provider_id', ['provider_id']),
        ('ix_marketplace_inquiries_service_id', ['service_id']),
    ):
        if index_name not in existing:
            op.create_index(index_name, 'marketplace_inquiries', columns)


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if 'marketplace_inquiries' not in inspector.get_table_names():
        return

    existing = {index['name'] for index in inspector.get_indexes('marketplace_inquiries')}
    for index_name in (
        'ix_marketplace_inquiries_service_id',
        'ix_marketplace_inquiries_provider_id',
        'ix_marketplace_inquiries_created_at',
        'ix_marketplace_inquiries_status',
        'ix_marketplace_inquiries_email',
    ):
        if index_name in existing:
            op.drop_index(index_name, table_name='marketplace_inquiries')

    op.drop_table('marketplace_inquiries')
