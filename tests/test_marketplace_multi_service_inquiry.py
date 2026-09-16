import json
import os
import unittest
from unittest.mock import patch

from tests.test_bootstrap import configure_isolated_sqlite


class MarketplaceMultiServiceInquiryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db_path = configure_isolated_sqlite('marketplace_multi_service')
        import wsgi
        from app import app, db
        from marketplace_models import Provider, ProviderType, Service, ServiceCategory, MarketplaceInquiry
        from models import NotificationOutbox

        cls.app = app
        cls.db = db
        cls.Provider = Provider
        cls.ProviderType = ProviderType
        cls.Service = Service
        cls.ServiceCategory = ServiceCategory
        cls.MarketplaceInquiry = MarketplaceInquiry
        cls.NotificationOutbox = NotificationOutbox
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
        self.db.session.query(self.NotificationOutbox).delete()
        self.db.session.query(self.MarketplaceInquiry).delete()
        self.db.session.query(self.Service).delete()
        self.db.session.query(self.Provider).delete()
        self.db.session.query(self.ServiceCategory).delete()
        self.db.session.query(self.ProviderType).delete()
        self.db.session.commit()

    def _seed(self):
        provider = self.Provider(
            name='Multi Service Provider', slug='multi-service-provider',
            status='APPROVED', is_active=True,
        )
        category = self.ServiceCategory(
            name='Guiding', slug='guiding', is_active=True, sort_order=1,
        )
        category_two = self.ServiceCategory(
            name='Transport', slug='transport', is_active=True, sort_order=2,
        )
        self.db.session.add_all([provider, category, category_two])
        self.db.session.commit()
        service_one = self.Service(
            provider=provider, service_category=category, name='Guided Walk',
            slug='guided-walk', description='Walk', status='PUBLISHED', is_active=True,
        )
        service_two = self.Service(
            provider=provider, service_category=category_two, name='Local Driver',
            slug='local-driver', description='Transport', status='PUBLISHED', is_active=True,
        )
        self.db.session.add_all([service_one, service_two])
        self.db.session.commit()
        return provider, service_one, service_two

    def _payload(self, provider, **extra):
        payload = {
            'provider_id': str(provider.id),
            'name': 'Traveller Example',
            'email': 'traveller@example.com',
            'phone': '+918888888888',
            'travellers': '2',
            'requirements': 'Need flexible timing',
        }
        payload.update(extra)
        return payload

    def test_general_provider_enquiry_is_accepted(self):
        provider, _, _ = self._seed()
        with patch('marketplace_inquiries.dispatch_notification_outbox') as dispatch:
            response = self.client.post('/marketplace/inquiries', data=self._payload(provider))
        self.assertEqual(response.status_code, 200)
        inquiry = self.MarketplaceInquiry.query.one()
        self.assertIsNone(inquiry.service_id)
        self.assertEqual(inquiry.service_name, 'General provider enquiry')
        self.assertEqual(json.loads(inquiry.selected_services_json), [])
        self.assertIn(b'Your enquiry has been received', response.data)
        self.assertIn(b'Continue browsing', response.data)
        self.assertIn(b'General provider enquiry', response.data)
        dispatch.assert_called_once()

    def test_multiple_services_are_persisted_and_notified(self):
        provider, service_one, service_two = self._seed()
        with patch('marketplace_inquiries.dispatch_notification_outbox') as dispatch:
            response = self.client.post(
                '/marketplace/inquiries',
                data=self._payload(provider, service_ids=[str(service_one.id), str(service_two.id)]),
            )
        self.assertEqual(response.status_code, 200)
        inquiry = self.MarketplaceInquiry.query.one()
        selected = json.loads(inquiry.selected_services_json)
        self.assertEqual([item['id'] for item in selected], [service_one.id, service_two.id])
        self.assertEqual(inquiry.service_id, service_one.id)
        self.assertEqual(inquiry.selected_service_ids, [service_one.id, service_two.id])
        self.assertEqual(
            [item['name'] for item in inquiry.selected_services],
            ['Guided Walk', 'Local Driver'],
        )
        outbox = self.NotificationOutbox.query.one()
        self.assertEqual(outbox.source_type, 'marketplace_inquiry')
        self.assertEqual(outbox.source_id, str(inquiry.id))
        self.assertIn('Guided Walk', outbox.body)
        self.assertIn('Local Driver', outbox.body)
        self.assertIn(b'Your enquiry has been received', response.data)
        self.assertIn(b'Guided Walk + 1 more', response.data)
        self.assertIn(b'Continue browsing', response.data)
        dispatch.assert_called_once()


if __name__ == '__main__':
    unittest.main()
