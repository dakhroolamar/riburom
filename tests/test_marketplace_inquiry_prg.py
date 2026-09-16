import os
import unittest
from unittest.mock import patch

from tests.test_bootstrap import configure_isolated_sqlite


class MarketplaceInquiryPrgTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db_path = configure_isolated_sqlite('marketplace_prg')
        import wsgi
        from app import app, db
        from marketplace_models import MarketplaceInquiry, Provider

        cls.app = app
        cls.db = db
        cls.MarketplaceInquiry = MarketplaceInquiry
        cls.Provider = Provider
        cls.app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
        cls.context = app.app_context()
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

    def setUp(self):
        self.db.session.rollback()
        self.db.session.query(self.MarketplaceInquiry).delete()
        self.db.session.query(self.Provider).delete()
        self.db.session.commit()

    def test_success_uses_post_redirect_get_without_duplicate_write(self):
        provider = self.Provider(
            name='PRG Provider',
            slug='prg-provider',
            status='APPROVED',
            is_active=True,
        )
        self.db.session.add(provider)
        self.db.session.commit()

        with patch('marketplace_inquiries.dispatch_notification_outbox'):
            response = self.client.post('/marketplace/inquiries', data={
                'provider_id': str(provider.id),
                'name': 'PRG Traveller',
                'email': 'prg@example.com',
            })

        self.assertEqual(response.status_code, 303)
        self.assertIn('/marketplace/inquiries/success/', response.headers['Location'])
        self.assertEqual(self.MarketplaceInquiry.query.count(), 1)

        success = self.client.get(response.headers['Location'])
        self.assertEqual(success.status_code, 200)
        self.assertIn(b'Your enquiry has been received', success.data)

        refreshed = self.client.get(response.headers['Location'])
        self.assertEqual(refreshed.status_code, 200)
        self.assertEqual(self.MarketplaceInquiry.query.count(), 1)

    def test_unowned_success_token_is_not_public(self):
        response = self.client.get('/marketplace/inquiries/success/not-a-valid-token')
        self.assertEqual(response.status_code, 404)


if __name__ == '__main__':
    unittest.main()
