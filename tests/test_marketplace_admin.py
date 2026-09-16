import json
import os
import unittest

from sqlalchemy import text

from tests.test_bootstrap import configure_isolated_sqlite


class MarketplaceAdminAccessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db_path = configure_isolated_sqlite('marketplace_admin')

        import wsgi
        from app import app, db
        from models import AuditLog, Package, User
        from marketplace_models import (
            PackageItem,
            Provider,
            ProviderType,
            ProviderTypeAssignment,
            Service,
            ServiceCategory,
        )

        cls.app = app
        cls.db = db
        cls.User = User
        cls.Package = Package
        cls.AuditLog = AuditLog
        cls.Provider = Provider
        cls.ProviderType = ProviderType
        cls.PackageItem = PackageItem
        cls.ProviderTypeAssignment = ProviderTypeAssignment
        cls.Service = Service
        cls.ServiceCategory = ServiceCategory

        cls.app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
        cls.context = cls.app.app_context()
        cls.context.push()
        db.create_all()
        cls.client = cls.app.test_client()

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
        self.db.session.query(self.PackageItem).delete()
        self.db.session.query(self.Service).delete()
        self.db.session.query(self.ProviderTypeAssignment).delete()
        self.db.session.query(self.Provider).delete()
        self.db.session.query(self.ServiceCategory).delete()
        self.db.session.query(self.ProviderType).delete()
        self.db.session.query(self.Package).delete()
        self.db.session.query(self.User).delete()
        self.db.session.commit()

    def _create_user(self, username, permissions):
        user = self.User(
            username=username,
            full_name=username.replace('-', ' ').title(),
            email=f'{username}@example.com',
            password_hash='not-used',
            role='content_manager',
            permissions_json=json.dumps(permissions),
            is_active=True,
        )
        self.db.session.add(user)
        self.db.session.commit()
        return user

    def _login_as(self, user):
        with self.client.session_transaction() as session:
            session.clear()
            session['user_id'] = user.id
            session['session_version'] = user.session_version

    def _manager(self):
        user = self._create_user('marketplace-manager', ['manage_marketplace'])
        self._login_as(user)
        return user

    def _viewer(self):
        user = self._create_user('marketplace-viewer', ['view_marketplace'])
        self._login_as(user)
        return user

    def _seed_taxonomy(self):
        provider_type = self.ProviderType(name='Guide', slug='guide', is_active=True, sort_order=1)
        category = self.ServiceCategory(name='Guiding', slug='guiding', is_active=True, sort_order=1)
        self.db.session.add_all([provider_type, category])
        self.db.session.commit()
        return provider_type, category

    def _seed_provider(self):
        provider_type, category = self._seed_taxonomy()
        provider = self.Provider(
            name='Test Guide',
            slug='test-guide',
            description='Marketplace test provider',
            status='ACTIVE',
            is_active=True,
        )
        self.db.session.add(provider)
        self.db.session.flush()
        assignment = self.ProviderTypeAssignment(
            provider=provider,
            provider_type=provider_type,
        )
        self.db.session.add(assignment)
        self.db.session.commit()
        return provider, provider_type, category

    def test_unauthenticated_user_is_redirected_to_login(self):
        response = self.client.get('/workspace/marketplace')
        self.assertEqual(response.status_code, 302)
        self.assertIn('/admin/login', response.headers['Location'])

    def test_authenticated_user_without_marketplace_permission_gets_403(self):
        user = self._create_user('marketplace-no-access', [])
        self._login_as(user)

        response = self.client.get('/workspace/marketplace')
        self.assertEqual(response.status_code, 403)

    def test_view_marketplace_permission_can_render_page(self):
        self._viewer()
        provider, _, category = self._seed_provider()

        service = self.Service(
            provider=provider,
            service_category=category,
            name='Local Guide Service',
            slug='local-guide-service',
            status='ACTIVE',
            is_active=True,
        )
        self.db.session.add(service)
        self.db.session.commit()

        response = self.client.get('/workspace/marketplace')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Marketplace', response.data)
        self.assertIn(b'Test Guide', response.data)
        self.assertIn(b'Local Guide Service', response.data)
        self.assertNotIn(b'id="marketplace-gallery-manager"', response.data)

    def test_manage_marketplace_permission_can_render_page(self):
        self._manager()
        response = self.client.get('/workspace/marketplace')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'id="marketplace-gallery-manager"', response.data)

    def test_provider_create_update_assignment_and_delete(self):
        self._manager()
        provider_type, _ = self._seed_taxonomy()

        response = self.client.post('/workspace/marketplace/providers/create', data={
            'name': 'Shillong Guide Co',
            'email': 'guide@example.com',
            'status': 'ACTIVE',
            'is_active': '1',
            'provider_type_ids': str(provider_type.id),
        })
        self.assertEqual(response.status_code, 302)

        provider = self.Provider.query.filter_by(name='Shillong Guide Co').one()
        self.assertEqual(provider.slug, 'shillong-guide-co')
        self.assertEqual([x.provider_type_id for x in provider.provider_type_assignments], [provider_type.id])

        response = self.client.post(f'/workspace/marketplace/providers/{provider.id}/update', data={
            'name': 'Shillong Guide Company',
            'slug': 'shillong-guide-company',
            'status': 'VERIFIED',
            'is_active': '1',
            'provider_type_ids': str(provider_type.id),
        })
        self.assertEqual(response.status_code, 302)

        provider = self.db.session.get(self.Provider, provider.id)
        self.assertEqual(provider.name, 'Shillong Guide Company')
        self.assertEqual(provider.status, 'VERIFIED')

        response = self.client.post(f'/workspace/marketplace/providers/{provider.id}/delete')
        self.assertEqual(response.status_code, 302)
        self.assertIsNone(self.db.session.get(self.Provider, provider.id))

    def test_provider_cannot_be_deleted_with_services(self):
        self._manager()
        provider, _, category = self._seed_provider()

        service = self.Service(
            provider=provider,
            service_category=category,
            name='Protected Service',
            slug='protected-service',
        )
        self.db.session.add(service)
        self.db.session.commit()

        response = self.client.post(f'/workspace/marketplace/providers/{provider.id}/delete')
        self.assertEqual(response.status_code, 302)
        self.assertIsNotNone(self.db.session.get(self.Provider, provider.id))

    def test_provider_type_crud(self):
        self._manager()

        response = self.client.post('/workspace/marketplace/provider-types/create', data={
            'name': 'Transport Provider',
            'is_active': '1',
            'sort_order': '4',
        })
        self.assertEqual(response.status_code, 302)

        item = self.ProviderType.query.filter_by(name='Transport Provider').one()

        response = self.client.post(f'/workspace/marketplace/provider-types/{item.id}/update', data={
            'name': 'Transport Operator',
            'slug': 'transport-operator',
            'is_active': '1',
            'sort_order': '5',
        })
        self.assertEqual(response.status_code, 302)

        item = self.db.session.get(self.ProviderType, item.id)
        self.assertEqual(item.name, 'Transport Operator')

        response = self.client.post(f'/workspace/marketplace/provider-types/{item.id}/delete')
        self.assertEqual(response.status_code, 302)
        self.assertIsNone(self.db.session.get(self.ProviderType, item.id))

    def test_service_category_crud(self):
        self._manager()

        response = self.client.post('/workspace/marketplace/service-categories/create', data={
            'name': 'Adventure Services',
            'is_active': '1',
            'sort_order': '2',
        })
        self.assertEqual(response.status_code, 302)

        item = self.ServiceCategory.query.filter_by(name='Adventure Services').one()

        response = self.client.post(f'/workspace/marketplace/service-categories/{item.id}/update', data={
            'name': 'Adventure Experiences',
            'slug': 'adventure-experiences',
            'is_active': '1',
            'sort_order': '3',
        })
        self.assertEqual(response.status_code, 302)

        item = self.db.session.get(self.ServiceCategory, item.id)
        self.assertEqual(item.name, 'Adventure Experiences')

        response = self.client.post(f'/workspace/marketplace/service-categories/{item.id}/delete')
        self.assertEqual(response.status_code, 302)
        self.assertIsNone(self.db.session.get(self.ServiceCategory, item.id))

    def test_service_create_update_and_delete(self):
        self._manager()
        provider, _, category = self._seed_provider()

        response = self.client.post('/workspace/marketplace/services/create', data={
            'provider_id': str(provider.id),
            'category_id': str(category.id),
            'name': 'Full Day Guide',
            'status': 'ACTIVE',
            'is_active': '1',
        })
        self.assertEqual(response.status_code, 302)

        service = self.Service.query.filter_by(name='Full Day Guide').one()
        self.assertEqual(service.slug, 'full-day-guide')

        response = self.client.post(f'/workspace/marketplace/services/{service.id}/update', data={
            'provider_id': str(provider.id),
            'category_id': str(category.id),
            'name': 'Full Day Local Guide',
            'slug': 'full-day-local-guide',
            'status': 'PUBLISHED',
            'is_active': '1',
        })
        self.assertEqual(response.status_code, 302)

        service = self.db.session.get(self.Service, service.id)
        self.assertEqual(service.name, 'Full Day Local Guide')
        self.assertEqual(service.status, 'PUBLISHED')

        response = self.client.post(f'/workspace/marketplace/services/{service.id}/delete')
        self.assertEqual(response.status_code, 302)
        row_count = self.db.session.execute(
            text('SELECT COUNT(*) FROM services WHERE id = :id'),
            {'id': service.id},
        ).scalar_one()
        self.assertEqual(row_count, 0)

    def test_service_slug_is_unique_per_provider(self):
        self._manager()
        provider_a, _, category = self._seed_provider()

        provider_b = self.Provider(name='Second Guide', slug='second-guide')
        self.db.session.add(provider_b)
        self.db.session.commit()

        response = self.client.post('/workspace/marketplace/services/create', data={
            'provider_id': str(provider_a.id),
            'category_id': str(category.id),
            'name': 'Day Tour',
            'slug': 'day-tour',
            'is_active': '1',
        })
        self.assertEqual(response.status_code, 302)

        response = self.client.post('/workspace/marketplace/services/create', data={
            'provider_id': str(provider_b.id),
            'category_id': str(category.id),
            'name': 'Day Tour',
            'slug': 'day-tour',
            'is_active': '1',
        })
        self.assertEqual(response.status_code, 302)

        services = self.Service.query.filter_by(slug='day-tour').all()
        self.assertEqual(len(services), 2)

    def test_service_cannot_be_deleted_when_attached_to_package(self):
        self._manager()
        provider, _, category = self._seed_provider()
        service = self.Service(
            provider=provider,
            service_category=category,
            name='Package Service',
            slug='package-service',
        )
        self.db.session.add(service)
        self.db.session.flush()

        package = self.Package(
            title='Protected Package',
            slug='protected-package',
            description='Package using marketplace service',
            published=True,
        )
        self.db.session.add(package)
        self.db.session.flush()

        from marketplace_models import PackageItem
        self.db.session.add(PackageItem(package=package, service=service, sort_order=1))
        self.db.session.commit()

        response = self.client.post(f'/workspace/marketplace/services/{service.id}/delete')
        self.assertEqual(response.status_code, 302)
        self.assertIsNotNone(self.db.session.get(self.Service, service.id))

    def test_view_user_cannot_mutate_marketplace(self):
        self._viewer()
        response = self.client.post('/workspace/marketplace/providers/create', data={
            'name': 'Should Fail',
        })
        self.assertEqual(response.status_code, 403)

    def test_mutations_write_audit_log(self):
        self._manager()

        before = self.AuditLog.query.count()

        response = self.client.post('/workspace/marketplace/provider-types/create', data={
            'name': 'Audited Type',
        })
        self.assertEqual(response.status_code, 302)

        self.assertGreater(self.AuditLog.query.count(), before)


if __name__ == '__main__':
    unittest.main()