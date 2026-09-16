import unittest

from tests.postgres_test_safety import assert_disposable_postgres_url


class PostgresTestSafetyTests(unittest.TestCase):
    def test_local_test_database_is_allowed(self):
        assert_disposable_postgres_url(
            'postgresql+psycopg2://ci:password@127.0.0.1:5432/riburom_test'
        )

    def test_remote_database_is_rejected(self):
        with self.assertRaises(RuntimeError):
            assert_disposable_postgres_url(
                'postgresql://user:password@production.example.com:5432/riburom_test'
            )

    def test_local_non_test_database_is_rejected(self):
        with self.assertRaises(RuntimeError):
            assert_disposable_postgres_url(
                'postgresql://user:password@localhost:5432/riburom'
            )


if __name__ == '__main__':
    unittest.main()
