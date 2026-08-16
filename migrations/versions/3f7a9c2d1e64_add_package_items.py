"""Add the Phase B PackageItem marketplace bridge.

Revision ID: 3f7a9c2d1e64
Revises: 8d1f2c4a9b01
Create Date: 2026-08-17
"""
from alembic import op
import sqlalchemy as sa


revision = '3f7a9c2d1e64'
down_revision = '8d1f2c4a9b01'
branch_labels = None
depends_on = None


TABLE_NAME = 'package_items'
EXPECTED_COLUMNS = {
    'id',
    'package_id',
    'service_id',
    'sort_order',
    'created_at',
    'updated_at',
}
EXPECTED_INDEXES = {
    ('ix_package_items_package_sort', ('package_id', 'sort_order'), False),
    ('ix_package_items_service_id', ('service_id',), False),
}


def _validate_existing_package_items(connection, inspector):
    row_count = connection.execute(sa.text('SELECT COUNT(*) FROM package_items')).scalar_one()
    if row_count != 0:
        raise RuntimeError(
            'Unexpected pre-existing package_items rows; migration requires an empty known baseline.'
        )

    columns = inspector.get_columns(TABLE_NAME)
    column_names = {column['name'] for column in columns}
    if column_names != EXPECTED_COLUMNS:
        raise RuntimeError(
            f'Unexpected package_items schema: columns={sorted(column_names)!r}; '
            f'expected={sorted(EXPECTED_COLUMNS)!r}.'
        )

    expected_nullability = {
        'id': False,
        'package_id': False,
        'service_id': False,
        'sort_order': False,
        'created_at': False,
        'updated_at': False,
    }
    for column in columns:
        if column['nullable'] != expected_nullability[column['name']]:
            raise RuntimeError(
                f"Unexpected nullability for package_items.{column['name']}: "
                f"{column['nullable']!r}."
            )

    pk_columns = inspector.get_pk_constraint(TABLE_NAME).get('constrained_columns') or []
    if pk_columns != ['id']:
        raise RuntimeError(
            f'Unexpected package_items primary key: {pk_columns!r}.'
        )

    foreign_keys = {
        (
            fk.get('constrained_columns', [None])[0],
            fk.get('referred_table'),
            (fk.get('options') or {}).get('ondelete'),
        )
        for fk in inspector.get_foreign_keys(TABLE_NAME)
    }
    expected_fks = {
        ('package_id', 'packages', 'CASCADE'),
        ('service_id', 'services', 'RESTRICT'),
    }
    normalized_fks = {
        (column, table, (ondelete or '').upper() or None)
        for column, table, ondelete in foreign_keys
    }
    if normalized_fks != expected_fks:
        raise RuntimeError(
            f'Unexpected package_items foreign keys: {sorted(normalized_fks)!r}; '
            f'expected={sorted(expected_fks)!r}.'
        )

    unique_constraints = {
        (
            constraint['name'],
            tuple(constraint.get('column_names') or []),
        )
        for constraint in inspector.get_unique_constraints(TABLE_NAME)
    }
    if ('uq_package_item_package_service', ('package_id', 'service_id')) not in unique_constraints:
        raise RuntimeError(
            'Expected uq_package_item_package_service uniqueness constraint is missing.'
        )
    unexpected_uniques = {
        columns
        for name, columns in unique_constraints
        if name != 'uq_package_item_package_service'
    }
    if unexpected_uniques:
        raise RuntimeError(
            f'Unexpected package_items uniqueness definitions: {sorted(unexpected_uniques)!r}.'
        )

    indexes = {
        (
            index['name'],
            tuple(index.get('column_names') or []),
            bool(index.get('unique')),
        )
        for index in inspector.get_indexes(TABLE_NAME)
    }
    if indexes != EXPECTED_INDEXES:
        raise RuntimeError(
            f'Unexpected package_items indexes: {sorted(indexes)!r}; '
            f'expected={sorted(EXPECTED_INDEXES)!r}.'
        )


def _create_package_items():
    op.create_table(
        TABLE_NAME,
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column(
            'package_id',
            sa.Integer(),
            sa.ForeignKey('packages.id', ondelete='CASCADE'),
            nullable=False,
        ),
        sa.Column(
            'service_id',
            sa.Integer(),
            sa.ForeignKey('services.id', ondelete='RESTRICT'),
            nullable=False,
        ),
        sa.Column('sort_order', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.UniqueConstraint(
            'package_id',
            'service_id',
            name='uq_package_item_package_service',
        ),
    )
    op.create_index(
        'ix_package_items_package_sort',
        TABLE_NAME,
        ['package_id', 'sort_order'],
        unique=False,
    )
    op.create_index(
        'ix_package_items_service_id',
        TABLE_NAME,
        ['service_id'],
        unique=False,
    )


def upgrade():
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    tables = set(inspector.get_table_names())

    if 'packages' not in tables:
        raise RuntimeError(
            'Cannot create package_items: the existing Package table is required.'
        )
    if 'services' not in tables:
        raise RuntimeError(
            'Cannot create package_items: the Phase A Service table is required.'
        )

    if TABLE_NAME in tables:
        _validate_existing_package_items(connection, inspector)
        return

    _create_package_items()


def downgrade():
    inspector = sa.inspect(op.get_bind())
    if TABLE_NAME not in inspector.get_table_names():
        return
    op.drop_index('ix_package_items_service_id', table_name=TABLE_NAME)
    op.drop_index('ix_package_items_package_sort', table_name=TABLE_NAME)
    op.drop_table(TABLE_NAME)
