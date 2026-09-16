import os
import unittest

from tests.test_bootstrap import configure_isolated_sqlite


class ApplicationCompositionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db_path = configure_isolated_sqlite('application_composition')
        import wsgi
        from app import app, db, run_deploy_bootstrap
        from models import User

        cls.app = app
        cls.db = db
        cls.User = User
        cls.app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
        run_deploy_bootstrap()
        cls.context = app.app_context()
        cls.context.push()
        cls.client = app.test_client()
        cls.owner = User.query.filter_by(role='owner').one()

    @classmethod
    def tearDownClass(cls):
        cls.db.session.remove()
        cls.db.engine.dispose()
        cls.context.pop()
        try:
            os.remove(cls.db_path)
        except FileNotFoundError:
            pass

    def _login(self):
        with self.client.session_transaction() as session:
            session.clear()
            session['user_id'] = self.owner.id
            session['session_version'] = self.owner.session_version

    def test_feature_registration_is_idempotent(self):
        from application_modules import register_application_modules
        before = sorted(str(rule) for rule in self.app.url_map.iter_rules())
        register_application_modules(self.app)
        after = sorted(str(rule) for rule in self.app.url_map.iter_rules())
        self.assertEqual(before, after)

    def test_legacy_admin_redirects_to_workspace(self):
        self._login()
        response = self.client.get('/admin')
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers['Location'], '/workspace')

    def test_workspace_routes_are_registered(self):
        rules = {rule.rule for rule in self.app.url_map.iter_rules()}
        for required in (
            '/workspace',
            '/workspace/cms',
            '/workspace/cms/media',
            '/workspace/cms/structure',
            '/workspace/marketplace',
            '/workspace/administration',
        ):
            self.assertIn(required, rules)


if __name__ == '__main__':
    unittest.main()
