import os
import unittest
from unittest.mock import patch

from tests.test_bootstrap import configure_isolated_sqlite


class MarketplaceNotificationRoutingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db_path = configure_isolated_sqlite('marketplace_notification_routing')

        import wsgi
        from app import app, db
        from marketplace_models import Provider, Service, ServiceCategory
        from models import SiteSettings

        cls.app = app
        cls.db = db
        cls.Provider = Provider
        cls.Service = Service
        cls.ServiceCategory = ServiceCategory
        cls.SiteSettings = SiteSettings

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

    def setUp(self):
        self.db.session.rollback()
        self.db.session.query(self.Service).delete()
        self.db.session.query(self.Provider).delete()
        self.db.session.query(self.ServiceCategory).delete()
        settings = self.db.session.get(self.SiteSettings, 1)
        if settings is None:
            settings = self.SiteSettings(id=1)
            self.db.session.add(settings)
        settings.footer_email = 'business@example.com'
        self.db.session.commit()

    def test_marketplace_uses_general_contact_recipient(self):
        category = self.ServiceCategory(
            name='Guiding',
            slug='guiding-test-routing',
            is_active=True,
            sort_order=1,
        )
        provider = self.Provider(
            name='Provider Email Example',
            slug='provider-email-example',
            email='provider@example.com',
            phone='+919999999999',
            status='APPROVED',
            is_active=True,
        )
        self.db.session.add_all([category, provider])
        self.db.session.commit()

        service = self.Service(
            provider=provider,
            service_category=category,
            name='Guided Walk',
            slug='guided-walk',
            description='Test service',
            status='PUBLISHED',
            is_active=True,
        )
        self.db.session.add(service)
        self.db.session.commit()

        payload = {
            'provider_id': str(provider.id),
            'service_id': str(service.id),
            'name': 'Traveller Example',
            'email': 'traveller@example.com',
            'phone': '+918888888888',
            'travellers': '2',
            'requirements': 'Test notification routing',
        }

        with patch('marketplace_inquiries.notify_new_enquiry') as notify:
            response = self.client.post('/marketplace/inquiries', data=payload)

        self.assertEqual(response.status_code, 200)
        notify.assert_called_once()
        notification = notify.call_args.args[0]
        self.assertEqual(notification['notification_email'], 'business@example.com')
        self.assertNotEqual(notification['notification_email'], 'provider@example.com')
        self.assertIn('Provider Email Example', notification['message'])
        self.assertIn('Guided Walk', notification['message'])


if __name__ == '__main__':
    unittest.main()
