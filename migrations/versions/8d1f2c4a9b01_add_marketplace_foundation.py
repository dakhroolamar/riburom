"""Establish the Phase A marketplace foundation.

Revision ID: 8d1f2c4a9b01
Revises: None
Create Date: 2026-08-16

This is a controlled adoption/baseline migration. It supports either a
fresh database or the known pre-Alembic production state in which all five
Phase A tables already exist, are empty, and were created from the Phase A
SQLAlchemy metadata before Alembic was introduced.
"""
from datetime import datetime

from alembic import op
import sqlalchemy as sa


revision = '8d1f2c4a9b01'
down_revision = None
branch_labels = None
depends_on = None


MARKETPLACE_TABLES = (
    'provider_types',
    'service_categories',
    'providers',
    'provider_type_assignments',
    'services',
)

PROVIDER_TYPES = [
    ('Guide', 'guide'),
    ('Driver', 'driver'),
    ('Homestay', 'homestay'),
    ('Hotel/Resort', 'hotel-resort'),
    ('Experience Provider', 'experience-provider'),
    ('Trekking/Adventure Provider', 'trekking-adventure-provider'),
    ('Cultural Practitioner', 'cultural-practitioner'),
    ('Community Tourism Provider', 'community-tourism-provider'),
]

SERVICE_CATEGORIES = [
    ('Accommodation', 'accommodation'),
    ('Transportation', 'transportation'),
    ('Guiding', 'guiding'),
    ('Experiences', 'experiences'),
    ('Adventure & Outdoor', 'adventure-outdoor'),
    ('Food & Culinary', 'food-culinary'),
    ('Wellness', 'wellness'),
    ('Events & Activities', 'events-activities'),
    ('Other', 'other'),
]

EXPECTED_COLUMNS = {
    'provider_types': (
        ('id', 'integer', False),
        ('name', 'string:120', False),
        ('slug', 'string:140', False),
        ('description', 'text', True),
        ('is_active', 'boolean', False),
        ('sort_order', 'integer', False),
        ('created_at', 'datetime', False),
        ('updated_at', 'datetime', False),
    ),
    'service_categories': (
        ('id', 'integer', False),
        ('name', 'string:120', False),
        ('slug', 'string:140', False),
        ('description', 'text', True),
        ('is_active', 'boolean', False),
        ('sort_order', 'integer', False),
        ('created_at', 'datetime', False),
        ('updated_at', 'datetime', False),
    ),
    'providers': (
        ('id', 'integer', False),
        ('name', 'string:200', False),
        ('slug', 'string:240', False),
        ('description', 'text', True),
        ('email', 'string:254', True),
        ('phone', 'string:40', True),
        ('status', 'string:40', False),
        ('is_active', 'boolean', False),
        ('created_at', 'datetime', False),
        ('updated_at', 'datetime', False),
    ),
    'provider_type_assignments': (
        ('id', 'integer', False),
        ('provider_id', 'integer', False),
        ('provider_type_id', 'integer', False),
        ('created_at', 'datetime', False),
    ),
    'services': (
        ('id', 'integer', False),
        ('provider_id', 'integer', False),
        ('category_id', 'integer', False),
        ('name', 'string:200', False),
        ('slug', 'string:240', False),
        ('description', 'text', True),
        ('status', 'string:40', False),
        ('is_active', 'boolean', False),
        ('created_at', 'datetime', False),
        ('updated_at', 'datetime', False),
    ),
}

EXPECTED_FOREIGN_KEYS = {
    'provider_type_assignments': {
        ('provider_id', 'providers', 'id'),
        ('provider_type_id', 'provider_types', 'id'),
    },
    'services': {
        ('provider_id', 'providers', 'id'),
        ('category_id', 'service_categories', 'id'),
    },
    'provider_types': set(),
    'service_categories': set(),
    'providers': set(),
}

# These are the non-unique indexes owned by the Phase A schema. The slug and
# composite uniqueness rules are handled separately so the migration can
# reconcile the known pre-Alembic unique-index representation.
EXPECTED_INDEXES = {
    'provider_types': {
        ('is_active',),
        ('sort_order',),
    },
    'service_categories': {
        ('is_active',),
        ('sort_order',),
    },
    'providers': {
        ('is_active',),
    },
    'provider_type_assignments': {
        ('provider_id',),
        ('provider_type_id',),
    },
    'services': {
        ('provider_id',),
        ('category_id',),
        ('status',),
    },
}

EXPECTED_UNIQUES = {
    'provider_types': {('slug',)},
    'service_categories': {('slug',)},
    'providers': {('slug',)},
    'provider_type_assignments': {('provider_id', 'provider_type_id')},
    'services': {('provider_id', 'slug')},
}

CANONICAL_CONSTRAINT_NAMES = {
    ('provider_types', ('slug',)): 'uq_provider_types_slug',
    ('service_categories', ('slug',)): 'uq_service_categories_slug',
    ('providers', ('slug',)): 'uq_providers_slug',
    ('provider_type_assignments', ('provider_id', 'provider_type_id')): 'uq_provider_type_assignment',
    ('services', ('provider_id', 'slug')): 'uq_service_provider_slug',
}


def _type_signature(column_type):
    """Return a small dialect-independent signature for schema validation."""
    if isinstance(column_type, sa.Boolean):
        return 'boolean'
    if isinstance(column_type, sa.Integer):
        return 'integer'
    if isinstance(column_type, sa.Text):
        return 'text'
    if isinstance(column_type, sa.String):
        return f'string:{column_type.length}'
    if isinstance(column_type, sa.DateTime):
        return 'datetime'
    return str(column_type).lower()


def _schema_snapshot(inspector, table):
    columns = {
        column['name']: (
            _type_signature(column['type']),
            bool(column['nullable']),
        )
        for column in inspector.get_columns(table)
    }
    primary_key = tuple(inspector.get_pk_constraint(table).get('constrained_columns') or ())
    foreign_keys = {
        (
            column,
            fk['referred_table'],
            fk['referred_columns'][0],
        )
        for fk in inspector.get_foreign_keys(table)
        for column in fk['constrained_columns']
    }
    indexes = []
    for index in inspector.get_indexes(table):
        indexes.append((tuple(index['column_names']), bool(index.get('unique'))))
    unique_constraints = {
        tuple(constraint['column_names'])
        for constraint in inspector.get_unique_constraints(table)
    }
    return columns, primary_key, foreign_keys, indexes, unique_constraints


def _validate_known_pre_alembic_schema(inspector):
    """Reject anything other than the known empty Phase A metadata shape."""
    for table in MARKETPLACE_TABLES:
        columns, primary_key, foreign_keys, indexes, unique_constraints = _schema_snapshot(
            inspector,
            table,
        )
        expected_columns = {
            name: (type_name, nullable)
            for name, type_name, nullable in EXPECTED_COLUMNS[table]
        }
        if columns != expected_columns:
            raise RuntimeError(
                f'Unexpected schema for {table}: columns/nullability do not match '
                'the known pre-Alembic Phase A schema.'
            )
        if primary_key != ('id',):
            raise RuntimeError(f'Unexpected primary key for {table}: {primary_key!r}')
        if foreign_keys != EXPECTED_FOREIGN_KEYS[table]:
            raise RuntimeError(
                f'Unexpected foreign keys for {table}: {foreign_keys!r}'
            )

        non_unique_indexes = {
            columns_tuple
            for columns_tuple, unique in indexes
            if not unique
        }
        unique_indexes = {
            columns_tuple
            for columns_tuple, unique in indexes
            if unique
        }
        expected_indexes = EXPECTED_INDEXES[table]

        # A duplicate ordinary slug index is a known, safe redundancy from the
        # earlier unique=True,index=True SQLAlchemy declaration. It is removed
        # during reconciliation rather than treated as an unknown schema.
        allowed_duplicate_slug = {
            ('slug',),
        } if ('slug',) in EXPECTED_UNIQUES[table] else set()
        unexpected_non_unique = non_unique_indexes - expected_indexes - allowed_duplicate_slug
        if unexpected_non_unique:
            raise RuntimeError(
                f'Unexpected indexes for {table}: {sorted(unexpected_non_unique)!r}'
            )

        missing_indexes = expected_indexes - non_unique_indexes
        if missing_indexes:
            raise RuntimeError(
                f'Missing expected indexes for {table}: {sorted(missing_indexes)!r}'
            )

        actual_unique_rules = set(unique_constraints) | unique_indexes
        if not EXPECTED_UNIQUES[table].issubset(actual_unique_rules):
            raise RuntimeError(
                f'Missing expected uniqueness for {table}: '
                f'expected {sorted(EXPECTED_UNIQUES[table])!r}, '
                f'found {sorted(actual_unique_rules)!r}'
            )
        unexpected_unique = actual_unique_rules - EXPECTED_UNIQUES[table]
        if unexpected_unique:
            raise RuntimeError(
                f'Unexpected uniqueness rules for {table}: {sorted(unexpected_unique)!r}'
            )


def _assert_empty_tables(connection, inspector):
    for table in MARKETPLACE_TABLES:
        if connection.execute(sa.text(f'SELECT COUNT(*) FROM "{table}"')).scalar_one() != 0:
            raise RuntimeError(
                f'Cannot adopt pre-existing {table}: the table is not empty.'
            )


def _table_exists(inspector, table):
    return table in inspector.get_table_names()


def _reconcile_server_defaults(connection):
    if connection.dialect.name != 'postgresql':
        # SQLite cannot alter an existing column default without rebuilding the
        # table. Production is PostgreSQL; fresh SQLite test databases receive
        # the defaults directly from the CREATE TABLE path.
        return

    statements = {
        'provider_types': (
            'ALTER TABLE provider_types ALTER COLUMN is_active SET DEFAULT TRUE',
            'ALTER TABLE provider_types ALTER COLUMN sort_order SET DEFAULT 0',
        ),
        'service_categories': (
            'ALTER TABLE service_categories ALTER COLUMN is_active SET DEFAULT TRUE',
            'ALTER TABLE service_categories ALTER COLUMN sort_order SET DEFAULT 0',
        ),
        'providers': (
            "ALTER TABLE providers ALTER COLUMN status SET DEFAULT 'DRAFT'",
            'ALTER TABLE providers ALTER COLUMN is_active SET DEFAULT TRUE',
        ),
        'services': (
            "ALTER TABLE services ALTER COLUMN status SET DEFAULT 'DRAFT'",
            'ALTER TABLE services ALTER COLUMN is_active SET DEFAULT TRUE',
        ),
    }
    for table_statements in statements.values():
        for statement in table_statements:
            connection.execute(sa.text(statement))


def _reconcile_uniqueness(connection, inspector):
    """Adopt known unique indexes as the canonical named constraints."""
    if connection.dialect.name != 'postgresql':
        return

    for table in MARKETPLACE_TABLES:
        unique_constraints = {
            tuple(constraint['column_names'])
            for constraint in inspector.get_unique_constraints(table)
        }
        for index in inspector.get_indexes(table):
            if not index.get('unique'):
                continue
            columns = tuple(index['column_names'])
            if columns not in EXPECTED_UNIQUES[table] or columns in unique_constraints:
                continue
            constraint_name = CANONICAL_CONSTRAINT_NAMES[(table, columns)]
            connection.execute(
                sa.text(
                    f'ALTER TABLE "{table}" ADD CONSTRAINT "{constraint_name}" '
                    f'UNIQUE USING INDEX "{index["name"]}"'
                )
            )

        # Remove the known duplicate ordinary slug index if it remains beside
        # the canonical uniqueness representation.
        inspector = sa.inspect(connection)
        for index in inspector.get_indexes(table):
            if index.get('unique'):
                continue
            if tuple(index['column_names']) != ('slug',):
                continue
            if ('slug',) not in EXPECTED_UNIQUES[table]:
                continue
            connection.execute(
                sa.text(f'DROP INDEX IF EXISTS "{index["name"]}"')
            )


def _seed_taxonomy(connection):
    provider_type_count = connection.execute(
        sa.text('SELECT COUNT(*) FROM provider_types')
    ).scalar_one()
    service_category_count = connection.execute(
        sa.text('SELECT COUNT(*) FROM service_categories')
    ).scalar_one()
    if provider_type_count or service_category_count:
        raise RuntimeError(
            'Unexpected pre-existing marketplace taxonomy rows; refusing to overwrite them.'
        )

    now = datetime.utcnow()
    provider_type_table = sa.table(
        'provider_types',
        sa.column('name', sa.String(length=120)),
        sa.column('slug', sa.String(length=140)),
        sa.column('is_active', sa.Boolean()),
        sa.column('sort_order', sa.Integer()),
        sa.column('created_at', sa.DateTime()),
        sa.column('updated_at', sa.DateTime()),
    )
    op.bulk_insert(
        provider_type_table,
        [
            {
                'name': name,
                'slug': slug,
                'is_active': True,
                'sort_order': index,
                'created_at': now,
                'updated_at': now,
            }
            for index, (name, slug) in enumerate(PROVIDER_TYPES, start=1)
        ],
    )

    service_category_table = sa.table(
        'service_categories',
        sa.column('name', sa.String(length=120)),
        sa.column('slug', sa.String(length=140)),
        sa.column('is_active', sa.Boolean()),
        sa.column('sort_order', sa.Integer()),
        sa.column('created_at', sa.DateTime()),
        sa.column('updated_at', sa.DateTime()),
    )
    op.bulk_insert(
        service_category_table,
        [
            {
                'name': name,
                'slug': slug,
                'is_active': True,
                'sort_order': index,
                'created_at': now,
                'updated_at': now,
            }
            for index, (name, slug) in enumerate(SERVICE_CATEGORIES, start=1)
        ],
    )


def _create_fresh_schema():
    op.create_table(
        'provider_types',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(length=120), nullable=False),
        sa.Column('slug', sa.String(length=140), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('sort_order', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.UniqueConstraint('slug', name='uq_provider_types_slug'),
    )
    op.create_index('ix_provider_types_is_active', 'provider_types', ['is_active'], unique=False)
    op.create_index('ix_provider_types_sort_order', 'provider_types', ['sort_order'], unique=False)

    op.create_table(
        'service_categories',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(length=120), nullable=False),
        sa.Column('slug', sa.String(length=140), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('sort_order', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.UniqueConstraint('slug', name='uq_service_categories_slug'),
    )
    op.create_index('ix_service_categories_is_active', 'service_categories', ['is_active'], unique=False)
    op.create_index('ix_service_categories_sort_order', 'service_categories', ['sort_order'], unique=False)

    op.create_table(
        'providers',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('slug', sa.String(length=240), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('email', sa.String(length=254), nullable=True),
        sa.Column('phone', sa.String(length=40), nullable=True),
        sa.Column('status', sa.String(length=40), nullable=False, server_default='DRAFT'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.UniqueConstraint('slug', name='uq_providers_slug'),
    )
    op.create_index('ix_providers_is_active', 'providers', ['is_active'], unique=False)

    op.create_table(
        'provider_type_assignments',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('provider_id', sa.Integer(), nullable=False),
        sa.Column('provider_type_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['provider_id'], ['providers.id']),
        sa.ForeignKeyConstraint(['provider_type_id'], ['provider_types.id']),
        sa.UniqueConstraint('provider_id', 'provider_type_id', name='uq_provider_type_assignment'),
    )
    op.create_index('ix_provider_type_assignments_provider_id', 'provider_type_assignments', ['provider_id'], unique=False)
    op.create_index('ix_provider_type_assignments_provider_type_id', 'provider_type_assignments', ['provider_type_id'], unique=False)

    op.create_table(
        'services',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('provider_id', sa.Integer(), nullable=False),
        sa.Column('category_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('slug', sa.String(length=240), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=40), nullable=False, server_default='DRAFT'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['provider_id'], ['providers.id']),
        sa.ForeignKeyConstraint(['category_id'], ['service_categories.id']),
        sa.UniqueConstraint('provider_id', 'slug', name='uq_service_provider_slug'),
    )
    op.create_index('ix_services_provider_id', 'services', ['provider_id'], unique=False)
    op.create_index('ix_services_category_id', 'services', ['category_id'], unique=False)
    op.create_index('ix_services_status', 'services', ['status'], unique=False)


def upgrade() -> None:
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    existing = {table for table in MARKETPLACE_TABLES if _table_exists(inspector, table)}

    if not existing:
        _create_fresh_schema()
    elif existing == set(MARKETPLACE_TABLES):
        _assert_empty_tables(connection, inspector)
        _validate_known_pre_alembic_schema(inspector)
        _reconcile_server_defaults(connection)
        _reconcile_uniqueness(connection, inspector)
    else:
        missing = sorted(set(MARKETPLACE_TABLES) - existing)
        present = sorted(existing)
        raise RuntimeError(
            'Partial pre-existing Phase A marketplace schema detected. '
            f'Present: {present}; missing: {missing}. Refusing to guess.'
        )

    _seed_taxonomy(connection)


def downgrade() -> None:
    op.drop_index('ix_services_status', table_name='services', if_exists=True)
    op.drop_index('ix_services_category_id', table_name='services', if_exists=True)
    op.drop_index('ix_services_provider_id', table_name='services', if_exists=True)
    op.drop_table('services', if_exists=True)

    op.drop_index('ix_provider_type_assignments_provider_type_id', table_name='provider_type_assignments', if_exists=True)
    op.drop_index('ix_provider_type_assignments_provider_id', table_name='provider_type_assignments', if_exists=True)
    op.drop_table('provider_type_assignments', if_exists=True)

    op.drop_index('ix_providers_is_active', table_name='providers', if_exists=True)
    op.drop_table('providers', if_exists=True)

    op.drop_index('ix_service_categories_sort_order', table_name='service_categories', if_exists=True)
    op.drop_index('ix_service_categories_is_active', table_name='service_categories', if_exists=True)
    op.drop_table('service_categories', if_exists=True)

    op.drop_index('ix_provider_types_sort_order', table_name='provider_types', if_exists=True)
    op.drop_index('ix_provider_types_is_active', table_name='provider_types', if_exists=True)
    op.drop_table('provider_types', if_exists=True)
