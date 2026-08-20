import os
import unittest

from tests.test_bootstrap import configure_isolated_sqlite


class MarketplaceAppearanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db_path = configure_isolated_sqlite('marketplace_appearance')

        import wsgi
        from app import app, db

        cls.app = app
        cls.db = db
        cls.app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
        cls.context = cls.app.app_context()
        cls.context.push()
        db.create_all()
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

    def test_appearance_routes_are_registered(self):
        endpoints = {rule.endpoint for rule in self.app.url_map.iter_rules()}
        self.assertIn('workspace_cms_marketplace_appearance', endpoints)
        self.assertIn('workspace_cms_save_marketplace_appearance', endpoints)
        self.assertIn('workspace_marketplace_appearance', endpoints)
        self.assertIn('workspace_marketplace_save_appearance', endpoints)

    def test_cms_appearance_requires_authentication(self):
        response = self.client.get('/workspace/cms/marketplace-appearance')
        self.assertEqual(response.status_code, 302)

    def test_public_marketplace_theme_tokens_are_rendered(self):
        response = self.client.get('/marketplace')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'--rb-marketplace-heading', response.data)
        self.assertIn(b'--rb-marketplace-input-border', response.data)
        self.assertIn(b'marketplaceInquiryModal', response.data)


if __name__ == '__main__':
    unittest.main()
