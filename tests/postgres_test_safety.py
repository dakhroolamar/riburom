"""Safety guard for destructive PostgreSQL integration tests."""

from urllib.parse import urlparse


SAFE_HOSTS = {'127.0.0.1', 'localhost', '::1'}


def assert_disposable_postgres_url(database_url):
    """Reject URLs that do not clearly identify a local disposable test DB."""
    if not database_url:
        return

    parsed = urlparse(database_url)
    hostname = parsed.hostname
    database_name = (parsed.path or '').strip('/').lower()
    scheme = (parsed.scheme or '').lower()

    if not scheme.startswith('postgresql'):
        raise RuntimeError(
            'Destructive PostgreSQL tests require a PostgreSQL test database URL.'
        )
    if hostname not in SAFE_HOSTS:
        raise RuntimeError(
            'Refusing destructive PostgreSQL tests against a non-local database host.'
        )
    if 'test' not in database_name:
        raise RuntimeError(
            'Refusing destructive PostgreSQL tests unless the database name contains "test".'
        )
