import os
import unittest

from tests.test_bootstrap import configure_isolated_sqlite


class SecurityHardeningTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db_path = configure_isolated_sqlite('security_hardening')
        import wsgi
        from app import app, db, run_deploy_bootstrap

        cls.app = app
        cls.db = db
        cls.app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
        run_deploy_bootstrap()
        cls.context = app.app_context()
        cls.context.push()
        cls.client = app.test_client()

    @classmethod
    def tearDownClass(cls):
        cls.db.session.remove()
        cls.db.engine.dispose()
        cls.context.pop()
        try:
            os.remove(cls.db_path)
        except FileNotFoundError:
            pass

    def test_responses_include_security_and_request_id_headers(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers['X-Content-Type-Options'], 'nosniff')
        self.assertEqual(response.headers['X-Frame-Options'], 'SAMEORIGIN')
        self.assertEqual(response.headers['Referrer-Policy'], 'strict-origin-when-cross-origin')
        self.assertTrue(response.headers.get('X-Request-ID'))

    def test_500_handler_is_database_independent(self):
        from app import server_error

        with self.app.test_request_context('/boom'):
            response = server_error(RuntimeError('synthetic test error'))
            self.assertEqual(response.status_code, 500)
            self.assertIn(b'Something went wrong', response.data)


if __name__ == '__main__':
    unittest.main()
