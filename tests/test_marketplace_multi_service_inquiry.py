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
        from app import limiter

        limiter.reset()
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
            response = self.client.post('/marketplace/inquiries', data=self._payload(provider), follow_redirects=True)
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
                follow_redirects=True,
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

    def test_oversized_selection_is_rejected_before_service_lookup(self):
        provider, _, _ = self._seed()
        cases = (
            ([str(i) for i in range(101)], 'application/x-www-form-urlencoded'),
            ([str(i) for i in range(20000)], 'application/x-www-form-urlencoded'),
            (['1'] * 101, 'application/x-www-form-urlencoded'),
            (['invalid'] * 101, 'application/x-www-form-urlencoded'),
            ([str(i) for i in range(101)], 'multipart/form-data'),
        )
        for selection, content_type in cases:
            with self.subTest(count=len(selection), value=selection[0], content_type=content_type):
                with patch.object(self.Service, 'query') as service_query, patch(
                    'marketplace_inquiries.dispatch_notification_outbox'
                ) as dispatch:
                    response = self.client.post(
                        '/marketplace/inquiries',
                        data=self._payload(provider, service_ids=selection),
                        content_type=content_type,
                    )
                self.assertEqual(response.status_code, 302)
                self.assertIn('/marketplace/providers/', response.headers['Location'])
                service_query.filter.assert_not_called()
                self.assertEqual(self.MarketplaceInquiry.query.count(), 0)
                self.assertEqual(self.NotificationOutbox.query.count(), 0)
                dispatch.assert_not_called()
                with self.client.session_transaction() as browser_session:
                    self.assertIn('no more than 100 services', browser_session['_flashes'][-1][1])

    def test_selection_preserves_first_occurrence_order_and_integer_parsing(self):
        provider, service_one, service_two = self._seed()
        selection = [str(service_two.id), 'invalid', f'0{service_two.id}',
                     str(service_one.id), str(service_two.id)]
        with patch('marketplace_inquiries.dispatch_notification_outbox'):
            response = self.client.post(
                '/marketplace/inquiries', data=self._payload(provider, service_ids=selection),
            )
        self.assertEqual(response.status_code, 303)
        inquiry = self.MarketplaceInquiry.query.one()
        self.assertEqual(inquiry.selected_service_ids, [service_two.id, service_one.id])
        self.assertEqual(inquiry.service_id, service_two.id)

    def test_exact_selection_limit_accepts_valid_services(self):
        from marketplace_inquiries import MAX_SELECTED_SERVICES

        provider, service_one, service_two = self._seed()
        services = [service_one, service_two]
        for index in range(MAX_SELECTED_SERVICES - len(services)):
            services.append(self.Service(
                provider=provider, service_category=service_one.service_category,
                name=f'Service {index}', slug=f'service-{index}',
                status='PUBLISHED', is_active=True,
            ))
        self.db.session.add_all(services)
        self.db.session.commit()
        selected_ids = [service.id for service in reversed(services)]
        with patch('marketplace_inquiries.dispatch_notification_outbox'):
            response = self.client.post(
                '/marketplace/inquiries',
                data=self._payload(provider, service_ids=[str(i) for i in selected_ids]),
            )
        self.assertEqual(response.status_code, 303)
        self.assertEqual(self.MarketplaceInquiry.query.one().selected_service_ids, selected_ids)

    def test_unavailable_selection_rejects_entire_enquiry(self):
        provider, service_one, service_two = self._seed()
        for unavailable in ('missing', 'unpublished', 'other_provider'):
            with self.subTest(unavailable=unavailable):
                service_two.status = 'PUBLISHED'
                service_two.provider_id = provider.id
                invalid_id = service_two.id
                if unavailable == 'missing':
                    invalid_id += 1000
                elif unavailable == 'unpublished':
                    service_two.status = 'DRAFT'
                else:
                    other = self.Provider(name='Other', slug='other', status='APPROVED', is_active=True)
                    self.db.session.add(other)
                    self.db.session.flush()
                    service_two.provider_id = other.id
                self.db.session.commit()
                with patch('marketplace_inquiries.dispatch_notification_outbox') as dispatch:
                    response = self.client.post(
                        '/marketplace/inquiries',
                        data=self._payload(provider, service_ids=[str(service_one.id), str(invalid_id)]),
                    )
                self.assertEqual(response.status_code, 302)
                self.assertEqual(self.MarketplaceInquiry.query.count(), 0)
                self.assertEqual(self.NotificationOutbox.query.count(), 0)
                dispatch.assert_not_called()


if __name__ == '__main__':
    unittest.main()
