from logging.config import fileConfig

from alembic import context
from flask import current_app
import sqlalchemy as sa

# Alembic Config object, populated by Flask-Migrate when invoked through
# `flask db`. The application already configures the real database URL.
config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)


target_metadata = current_app.extensions['migrate'].db.metadata

LEGACY_MIGRATION_HEADS = {
    '3f7a9c2d1e64',
    '7e4c91d2ab30',
    '7f1c9e4a6b20',
}
LEGACY_BASE_REVISION = '2c8e4a7f1b90'
MERGED_REVISION = '9b2d4f6c8e10'


def get_url():
    return current_app.extensions['migrate'].db.engine.url.render_as_string(hide_password=False)


def _repair_legacy_marketplace_version_state(connection):
    """Repair the known Phase B multi-head state before Alembic walks it.

    A production database can contain the three historical Phase B heads because
    those migrations were deployed independently before the graph merge revision
    existed. Alembic can fail while deleting one of those heads during the merge.
    This narrowly-scoped repair only activates for that known state, verifies the
    Phase B schema objects already exist, applies the selected-services column if
    necessary, and stamps the database at the graph merge revision.
    """
    inspector = sa.inspect(connection)
    tables = set(inspector.get_table_names())
    if 'alembic_version' not in tables:
        return

    versions = {
        row[0]
        for row in connection.execute(
            sa.text('SELECT version_num FROM alembic_version')
        ).fetchall()
    }

    if MERGED_REVISION in versions:
        return

    allowed_legacy_versions = LEGACY_MIGRATION_HEADS | {LEGACY_BASE_REVISION}
    if not versions or not versions.issubset(allowed_legacy_versions):
        return
    if not LEGACY_MIGRATION_HEADS.issubset(versions):
        return

    required_tables = {'marketplace_inquiries', 'package_items', 'service_images'}
    if not required_tables.issubset(tables):
        return

    marketplace_columns = {
        column['name']
        for column in inspector.get_columns('marketplace_inquiries')
    }
    if 'selected_services_json' not in marketplace_columns:
        connection.execute(
            sa.text(
                'ALTER TABLE marketplace_inquiries '
                'ADD COLUMN selected_services_json TEXT'
            )
        )

    connection.execute(sa.text('DELETE FROM alembic_version'))
    connection.execute(
        sa.text(
            'INSERT INTO alembic_version (version_num) VALUES (:revision)'
        ),
        {'revision': MERGED_REVISION},
    )


def run_migrations_offline():
    context.configure(
        url=get_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={'paramstyle': 'named'},
        compare_type=True,
        render_as_batch=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    connectable = current_app.extensions['migrate'].db.engine

    with connectable.connect() as connection:
        _repair_legacy_marketplace_version_state(connection)

        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            render_as_batch=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
