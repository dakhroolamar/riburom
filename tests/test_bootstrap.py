import os
import tempfile


def configure_isolated_sqlite(test_name):
    os.environ['APP_ENV'] = 'testing'
    os.environ['TESTING'] = '1'
    os.environ['SECRET_KEY'] = f'{test_name}-secret'
    os.environ['ADMIN_PASSWORD'] = f'{test_name}-password'

    db_file = tempfile.NamedTemporaryFile(
        prefix=f'{test_name}_',
        suffix='.db',
        delete=False,
    )
    db_file.close()

    database_url = f'sqlite:///{db_file.name}'
    os.environ['DATABASE_URL'] = database_url

    return db_file.name
