"""Add Provider and Service image URLs.

Revision ID: 6a4b7c9e2d10
Revises: 3f7a9c2d1e64
Create Date: 2026-08-17
"""
from alembic import op
import sqlalchemy as sa


revision = '6a4b7c9e2d10'
down_revision = '3f7a9c2d1e64'
branch_labels = None
depends_on = None



def _validate_existing_image_column(inspector, table_name):
    columns = inspector.get_columns(table_name)
    image_columns = [column for column in columns if column['name'] == 'image_url']

    if not image_columns:
        return False

    column = image_columns[0]

    if column['nullable'] is not True:
        raise RuntimeError(
            f'Unexpected nullability for {table_name}.image_url: '
            f'{column["nullable"]!r}; expected nullable=True.'
        )

    if column['type']._type_affinity is not sa.String:
        raise RuntimeError(
            f'Unexpected type for {table_name}.image_url: '
            f'{column["type"]!r}; expected String affinity.'
        )

    return True


def _add_image_column(inspector, table_name):
    if _validate_existing_image_column(inspector, table_name):
        return

    op.add_column(
        table_name,
        sa.Column('image_url', sa.String(length=500), nullable=True),
    )


def upgrade():
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    tables = set(inspector.get_table_names())

    missing = {'providers', 'services'} - tables
    if missing:
        raise RuntimeError(
            'Cannot add marketplace image URLs; required tables are missing: '
            f'{sorted(missing)!r}.'
        )

    _add_image_column(inspector, 'providers')

    inspector = sa.inspect(connection)
    _add_image_column(inspector, 'services')


def downgrade():
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    tables = set(inspector.get_table_names())

    if 'services' in tables:
        service_columns = {
            column['name']
            for column in inspector.get_columns('services')
        }
        if 'image_url' in service_columns:
            with op.batch_alter_table('services') as batch_op:
                batch_op.drop_column('image_url')

    inspector = sa.inspect(connection)
    tables = set(inspector.get_table_names())

    if 'providers' in tables:
        provider_columns = {
            column['name']
            for column in inspector.get_columns('providers')
        }
        if 'image_url' in provider_columns:
            with op.batch_alter_table('providers') as batch_op:
                batch_op.drop_column('image_url')