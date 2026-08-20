import os
import unittest

from tests.test_bootstrap import configure_isolated_sqlite


class MarketplacePublicTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db_path = configure_isolated_sqlite('marketplace_public')

        import wsgi
        from app import app, db
        from marketplace_models import (
            Provider,
            ProviderType,
            Service,
            ServiceCategory,
            ServiceImage,
        )

        cls.app = app
        cls.db = db
        cls.Provider = Provider
        cls.ProviderType = ProviderType
        cls.Service = Service
        cls.ServiceCategory = ServiceCategory
        cls.ServiceImage = ServiceImage

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
        self.db.session.query(self.ServiceImage).delete()
        self.db.session.query(self.Service).delete()
        self.db.session.query(self.Provider).delete()
        self.db.session.query(self.ServiceCategory).delete()
        self.db.session.query(self.ProviderType).delete()
        self.db.session.commit()

    def _seed(self):
        provider_type = self.ProviderType(
            name='Guide',
            slug='guide-public-test',
            is_active=True,
            sort_order=1,
        )
        category = self.ServiceCategory(
            name='Guiding',
            slug='guiding-public-test',
            is_active=True,
            sort_order=1,
        )

        public_provider = self.Provider(
            name='Public Guide',
            slug='public-guide',
            description='Public provider',
            status='APPROVED',
            is_active=True,
        )
        hidden_provider = self.Provider(
            name='Hidden Guide',
            slug='hidden-guide',
            description='Hidden provider',
            status='DRAFT',
            is_active=True,
        )

        self.db.session.add_all([
            provider_type,
            category,
            public_provider,
            hidden_provider,
        ])
        self.db.session.commit()

        public_service = self.Service(
            provider=public_provider,
            service_category=category,
            name='Public Service',
            slug='public-service',
            description='Public service',
            status='PUBLISHED',
            is_active=True,
        )
        self.db.session.add_all([
            public_service,
            self.Service(
                provider=public_provider,
                service_category=category,
                name='Hidden Service',
                slug='hidden-service',
                description='Hidden service',
                status='DRAFT',
                is_active=True,
            ),
            self.Service(
                provider=hidden_provider,
                service_category=category,
                name='Hidden Provider Service',
                slug='hidden-provider-service',
                description='Should never be public',
                status='PUBLISHED',
                is_active=True,
            ),
        ])
        self.db.session.flush()
        self.db.session.add(
            self.ServiceImage(
                service_id=public_service.id,
                image_url='/static/service-test-1.jpg',
                alt_text='Public service test image',
                sort_order=0,
            )
        )
        self.db.session.commit()

    def test_public_marketplace_lists_only_public_providers(self):
        self._seed()

        response = self.client.get('/marketplace')

        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Public Guide', response.data)
        self.assertNotIn(b'Hidden Guide', response.data)
        self.assertIn(b'Public Service', response.data)
        self.assertNotIn(b'Hidden Service', response.data)
        self.assertNotIn(b'Hidden Provider Service', response.data)

    def test_public_marketplace_has_provider_service_view_switch_and_category_filter(self):
        self._seed()

        response = self.client.get('/marketplace')

        self.assertEqual(response.status_code, 200)
        self.assertIn(b'id="marketplace-category"', response.data)
        self.assertIn(b'id="marketplace-view-providers"', response.data)
        self.assertIn(b'id="marketplace-view-services"', response.data)
        self.assertIn(b'Browse individual services', response.data)

    def test_public_marketplace_service_selection_includes_gallery(self):
        self._seed()

        response = self.client.get('/marketplace')

        self.assertEqual(response.status_code, 200)
        self.assertIn(b'data-service-open="1"', response.data)
        self.assertIn(b'data-gallery-main="1"', response.data)
        self.assertIn(b'Public service test image', response.data)

    def test_public_provider_detail_shows_only_public_services(self):
        self._seed()

        response = self.client.get('/marketplace/providers/public-guide')

        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Public Guide', response.data)
        self.assertIn(b'Public Service', response.data)
        self.assertNotIn(b'Hidden Service', response.data)

    def test_public_provider_detail_has_provider_level_enquiry_ui(self):
        self._seed()

        response = self.client.get('/marketplace/providers/public-guide')

        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Enquire with this provider', response.data)
        self.assertIn(b'name="service_id"', response.data)
        self.assertIn(b'Public Service', response.data)
        self.assertIn(b'Anything else we should know?', response.data)
        self.assertIn(b'Independent marketplace enquiry', response.data)
        self.assertNotIn(b'Request this service', response.data)
        self.assertNotIn(b'Plan Your Journey', response.data)
        self.assertIn(b'action="/marketplace/inquiries"', response.data)

    def test_hidden_provider_detail_returns_404(self):
        self._seed()

        response = self.client.get('/marketplace/providers/hidden-guide')

        self.assertEqual(response.status_code, 404)

    def test_missing_provider_detail_returns_404(self):
        response = self.client.get('/marketplace/providers/does-not-exist')

        self.assertEqual(response.status_code, 404)


if __name__ == '__main__':
    unittest.main()
