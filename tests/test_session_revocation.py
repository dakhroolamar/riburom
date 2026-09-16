import os
import unittest

from tests.test_bootstrap import configure_isolated_sqlite


class SessionRevocationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db_path = configure_isolated_sqlite('session_revocation')
        import wsgi
        from app import app, db, run_deploy_bootstrap
        from models import User
        from werkzeug.security import generate_password_hash

        cls.app = app
        cls.db = db
        cls.User = User
        cls.app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
        run_deploy_bootstrap()
        cls.context = app.app_context()
        cls.context.push()

        cls.user = User(
            username='session-user',
            full_name='Session User',
            email='session@example.com',
            password_hash=generate_password_hash('correct-password-123'),
            role='enquiries',
            is_active=True,
        )
        db.session.add(cls.user)
        db.session.commit()
        cls.user_id = cls.user.id

    @classmethod
    def tearDownClass(cls):
        cls.db.session.remove()
        cls.db.engine.dispose()
        cls.context.pop()
        try:
            os.remove(cls.db_path)
        except FileNotFoundError:
            pass

    def setUp(self):
        self.db.session.rollback()
        user = self.db.session.get(self.User, self.user_id)
        user.is_active = True
        user.role = 'enquiries'
        user.permissions_json = None
        user.session_version = 0
        self.db.session.commit()
        self.client = self.app.test_client()

    def _login(self):
        response = self.client.post('/admin/login', data={
            'username': 'session-user',
            'password': 'correct-password-123',
        })
        self.assertEqual(response.status_code, 302)

    def test_login_records_session_version(self):
        self._login()
        with self.client.session_transaction() as browser_session:
            self.assertEqual(browser_session['user_id'], self.user_id)
            self.assertEqual(browser_session['session_version'], 0)

    def test_server_side_version_change_revokes_existing_session(self):
        self._login()
        user = self.db.session.get(self.User, self.user_id)
        user.session_version += 1
        self.db.session.commit()

        response = self.client.get('/admin', follow_redirects=False)
        self.assertEqual(response.status_code, 302)
        self.assertIn('/admin/login', response.headers['Location'])
        with self.client.session_transaction() as browser_session:
            self.assertNotIn('user_id', browser_session)

    def test_inactive_user_session_is_revoked(self):
        self._login()
        user = self.db.session.get(self.User, self.user_id)
        user.is_active = False
        user.session_version += 1
        self.db.session.commit()

        response = self.client.get('/admin', follow_redirects=False)
        self.assertEqual(response.status_code, 302)
        self.assertIn('/admin/login', response.headers['Location'])


if __name__ == '__main__':
    unittest.main()
