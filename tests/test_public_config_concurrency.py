import json
import os
import unittest

from tests.test_bootstrap import configure_isolated_sqlite


class PublicConfigConcurrencyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db_path = configure_isolated_sqlite('public_config_concurrency')
        import wsgi
        from app import app, db, run_deploy_bootstrap
        from config_concurrency import public_config_token
        from models import SiteSettings, User

        cls.app = app
        cls.db = db
        cls.SiteSettings = SiteSettings
        cls.User = User
        cls.public_config_token = staticmethod(public_config_token)
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

    def setUp(self):
        settings = self.db.session.get(self.SiteSettings, 1)
        self._original_public_config_json = settings.public_config_json
        with self.client.session_transaction() as session:
            session.clear()
            session['user_id'] = self.owner.id
            session['session_version'] = self.owner.session_version

    def tearDown(self):
        self.db.session.rollback()
        settings = self.db.session.get(self.SiteSettings, 1)
        settings.public_config_json = self._original_public_config_json
        self.db.session.commit()

    def test_cms_form_contains_public_config_token(self):
        response = self.client.get('/workspace/cms/advanced')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'name="public_config_token"', response.data)

    def test_stale_public_config_submission_is_rejected(self):
        settings = self.db.session.get(self.SiteSettings, 1)
        stale_token = self.public_config_token(settings)

        concurrent = json.loads(settings.public_config_json or '{}')
        concurrent.setdefault('content', {})['site_title'] = 'Concurrent editor value'
        settings.public_config_json = json.dumps(concurrent)
        self.db.session.commit()

        response = self.client.post('/workspace/cms/save-content', data={
            'public_config_token': stale_token,
            'site_title': 'Stale editor value',
        })
        self.assertEqual(response.status_code, 302)

        self.db.session.expire_all()
        settings = self.db.session.get(self.SiteSettings, 1)
        stored = json.loads(settings.public_config_json or '{}')
        self.assertEqual(stored['content']['site_title'], 'Concurrent editor value')

    def test_current_public_config_submission_is_saved(self):
        settings = self.db.session.get(self.SiteSettings, 1)
        token = self.public_config_token(settings)

        response = self.client.post('/workspace/cms/save-content', data={
            'public_config_token': token,
            'site_title': 'Fresh editor value',
        })
        self.assertEqual(response.status_code, 302)

        self.db.session.expire_all()
        settings = self.db.session.get(self.SiteSettings, 1)
        stored = json.loads(settings.public_config_json or '{}')
        self.assertEqual(stored['content']['site_title'], 'Fresh editor value')


if __name__ == '__main__':
    unittest.main()
