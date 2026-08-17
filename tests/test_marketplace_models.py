import unittest

from flask import Flask
from sqlalchemy.exc import IntegrityError

from models import db, Package
from marketplace_models import (
    Provider,
    ProviderType,
    ProviderTypeAssignment,
    Service,
    ServiceCategory,
    PROVIDER_STATUSES,
    SERVICE_STATUSES,
)


class MarketplaceModelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = Flask(__name__)
        cls.app.config.update(
            SQLALCHEMY_DATABASE_URI='sqlite:///:memory:',
            SQLALCHEMY_TRACK_MODIFICATIONS=False,
            TESTING=True,
        )
        db.init_app(cls.app)
        cls.app_context = cls.app.app_context()
        cls.app_context.push()
        db.create_all()

    @classmethod
    def tearDownClass(cls):
        db.session.remove()
        db.engine.dispose()
        cls.app_context.pop()

    def setUp(self):
        db.session.rollback()

    def tearDown(self):
        db.session.rollback()
        for model in (
            Service,
            ProviderTypeAssignment,
            Provider,
            ServiceCategory,
            ProviderType,
            Package,
        ):
            db.session.query(model).delete()
        db.session.commit()

    def test_provider_type_creation_and_unique_slug(self):
        first = ProviderType(name='Guide', slug='guide')
        db.session.add(first)
        db.session.commit()

        duplicate = ProviderType(name='Another Guide', slug='guide')
        db.session.add(duplicate)
        with self.assertRaises(IntegrityError):
            db.session.commit()

    def test_service_category_creation_and_unique_slug(self):
        db.session.add(ServiceCategory(name='Guiding', slug='guiding'))
        db.session.commit()

        db.session.add(ServiceCategory(name='Another Guiding', slug='guiding'))
        with self.assertRaises(IntegrityError):
            db.session.commit()

    def test_provider_creation_and_unique_slug(self):
        db.session.add(Provider(name='John Doe', slug='john-doe'))
        db.session.commit()

        db.session.add(Provider(name='Another John', slug='john-doe'))
        with self.assertRaises(IntegrityError):
            db.session.commit()

    def test_provider_lifecycle_validation(self):
        for status in PROVIDER_STATUSES:
            provider = Provider(name=f'Provider {status}', slug=f'provider-{status.lower()}', status=status)
            db.session.add(provider)
        db.session.commit()

        with self.assertRaises(ValueError):
            Provider(name='Invalid', slug='invalid', status='NOT_A_PROVIDER_STATUS')

    def test_service_lifecycle_validation(self):
        for status in SERVICE_STATUSES:
            provider = Provider(name=f'Provider {status}', slug=f'service-status-{status.lower()}')
            db.session.add(provider)
        db.session.commit()

        with self.assertRaises(ValueError):
            Service(name='Invalid', slug='invalid', status='NOT_A_SERVICE_STATUS')

    def test_provider_type_assignment_relationship_and_duplicate_rejection(self):
        provider = Provider(name='John Doe', slug='john-doe')
        provider_type = ProviderType(name='Guide', slug='guide')
        db.session.add_all([provider, provider_type])
        db.session.commit()

        assignment = ProviderTypeAssignment(provider=provider, provider_type=provider_type)
        db.session.add(assignment)
        db.session.commit()

        self.assertEqual(provider.provider_type_assignments, [assignment])
        self.assertEqual(provider_type.provider_assignments, [assignment])
        self.assertIs(assignment.provider, provider)
        self.assertIs(assignment.provider_type, provider_type)

        duplicate = ProviderTypeAssignment(provider=provider, provider_type=provider_type)
        db.session.add(duplicate)
        with self.assertRaises(IntegrityError):
            db.session.commit()

    def test_provider_can_have_multiple_provider_types(self):
        provider = Provider(name='John Doe', slug='john-doe')
        guide = ProviderType(name='Guide', slug='guide')
        driver = ProviderType(name='Driver', slug='driver')
        db.session.add_all([provider, guide, driver])
        db.session.commit()

        db.session.add_all([
            ProviderTypeAssignment(provider=provider, provider_type=guide),
            ProviderTypeAssignment(provider=provider, provider_type=driver),
        ])
        db.session.commit()

        self.assertEqual({item.provider_type.slug for item in provider.provider_type_assignments}, {'guide', 'driver'})

    def test_provider_can_have_multiple_services_and_service_category(self):
        provider = Provider(name='John Doe', slug='john-doe')
        guiding = ServiceCategory(name='Guiding', slug='guiding')
        transport = ServiceCategory(name='Transportation', slug='transportation')
        db.session.add_all([provider, guiding, transport])
        db.session.commit()

        guide_service = Service(
            provider=provider,
            service_category=guiding,
            name='Jaintia Hills Cultural Guide',
            slug='jaintia-hills-cultural-guide',
        )
        driver_service = Service(
            provider=provider,
            service_category=transport,
            name='SUV + Driver',
            slug='suv-driver',
        )
        db.session.add_all([guide_service, driver_service])
        db.session.commit()

        self.assertEqual(len(provider.services), 2)
        self.assertIs(guide_service.provider, provider)
        self.assertIs(guide_service.service_category, guiding)
        self.assertIs(driver_service.service_category, transport)

    def test_service_slug_is_unique_per_provider_not_globally(self):
        category = ServiceCategory(name='Guiding', slug='guiding')
        provider_a = Provider(name='Provider A', slug='provider-a')
        provider_b = Provider(name='Provider B', slug='provider-b')
        db.session.add_all([category, provider_a, provider_b])
        db.session.commit()

        db.session.add_all([
            Service(provider=provider_a, service_category=category, name='Full-Day Local Guide', slug='full-day-local-guide'),
            Service(provider=provider_b, service_category=category, name='Full-Day Local Guide', slug='full-day-local-guide'),
        ])
        db.session.commit()

        self.assertEqual(Service.query.count(), 2)

        db.session.add(
            Service(provider=provider_a, service_category=category, name='Duplicate', slug='full-day-local-guide')
        )
        with self.assertRaises(IntegrityError):
            db.session.commit()

    def test_existing_package_model_remains_loadable(self):
        package = Package(
            title='Existing Experience',
            slug='existing-experience',
            description='Existing package data remains independent from Phase A.',
            published=True,
        )
        db.session.add(package)
        db.session.commit()

        loaded = db.session.get(Package, package.id)
        self.assertEqual(loaded.slug, 'existing-experience')
        self.assertEqual(loaded.title, 'Existing Experience')


if __name__ == '__main__':
    unittest.main()
