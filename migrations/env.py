from logging.config import fileConfig

from alembic import context
from flask import current_app

# Alembic Config object, populated by Flask-Migrate when invoked through
# `flask db`. The application already configures the real database URL.
config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)


target_metadata = current_app.extensions['migrate'].db.metadata


def get_url():
    return current_app.extensions['migrate'].db.engine.url.render_as_string(hide_password=False)


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
    connection = config.attributes.get('connection')
    if connection is not None:
        run_on_connection(connection)
    else:
        with current_app.extensions['migrate'].db.engine.connect() as connection:
            run_on_connection(connection)


def run_on_connection(connection):
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
