import unittest

from flask import Flask
from sqlalchemy import event, text
from sqlalchemy.exc import IntegrityError

from models import Package, db
from marketplace_models import PackageItem, Provider, Service, ServiceCategory


class PackageItemModelTests(unittest.TestCase):
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
        with db.engine.begin() as connection:
            connection.execute(text('PRAGMA foreign_keys=ON'))
        db.create_all()

    @classmethod
    def tearDownClass(cls):
        db.session.remove()
        cls.app_context.pop()

    def setUp(self):
        db.session.rollback()

    def tearDown(self):
        db.session.rollback()
        for model in (PackageItem, Service, ServiceCategory, Provider, Package):
            db.session.query(model).delete()
        db.session.commit()

    def _service(self, slug='guide-service'):
        provider = Provider(name='Provider One', slug=f'provider-{slug}')
        category = ServiceCategory(name='Guiding', slug=f'guiding-{slug}')
        service = Service(
            provider=provider,
            service_category=category,
            name='Local Guide Service',
            slug=slug,
        )
        db.session.add_all([provider, category, service])
        db.session.flush()
        return service

    def _package(self, slug='package-one'):
        package = Package(
            title='Meghalaya Explorer',
            slug=slug,
            description='Existing package aggregate.',
            published=True,
        )
        db.session.add(package)
        db.session.flush()
        return package

    def test_package_item_creation_and_relationships(self):
        package = self._package()
        service = self._service()

        item = PackageItem(package=package, service=service, sort_order=1)
        db.session.add(item)
        db.session.commit()

        self.assertEqual(package.package_items, [item])
        self.assertEqual(service.package_items, [item])
        self.assertIs(item.package, package)
        self.assertIs(item.service, service)
        self.assertEqual(item.sort_order, 1)

    def test_service_can_be_reused_across_multiple_packages(self):
        service = self._service()
        package_one = self._package('package-one')
        package_two = self._package('package-two')

        db.session.add_all([
            PackageItem(package=package_one, service=service, sort_order=1),
            PackageItem(package=package_two, service=service, sort_order=2),
        ])
        db.session.commit()

        self.assertEqual(len(service.package_items), 2)
        self.assertEqual({item.package.slug for item in service.package_items}, {'package-one', 'package-two'})

    def test_duplicate_service_in_same_package_is_rejected(self):
        package = self._package()
        service = self._service()
        db.session.add(PackageItem(package=package, service=service, sort_order=1))
        db.session.commit()

        db.session.add(PackageItem(package=package, service=service, sort_order=2))
        with self.assertRaises(IntegrityError):
            db.session.commit()
        db.session.rollback()

    def test_package_items_are_ordered_by_sort_order_then_id(self):
        package = self._package()
        service_one = self._service('service-one')
        service_two = self._service('service-two')

        later = PackageItem(package=package, service=service_one, sort_order=2)
        earlier = PackageItem(package=package, service=service_two, sort_order=1)
        db.session.add_all([later, earlier])
        db.session.commit()
        db.session.expire(package, ['package_items'])

        self.assertEqual([item.sort_order for item in package.package_items], [1, 2])

    def test_existing_package_loads_with_zero_package_items(self):
        package = self._package()
        loaded = db.session.get(Package, package.id)

        self.assertEqual(loaded.slug, 'package-one')
        self.assertEqual(loaded.package_items, [])

    def test_deleting_package_removes_package_items_but_not_service(self):
        package = self._package()
        service = self._service()
        item = PackageItem(package=package, service=service)
        db.session.add(item)
        db.session.commit()

        db.session.delete(package)
        db.session.commit()

        self.assertIsNone(db.session.get(PackageItem, item.id))
        self.assertIsNotNone(db.session.get(Service, service.id))

    def test_deleting_package_item_does_not_delete_service(self):
        package = self._package()
        service = self._service()
        item = PackageItem(package=package, service=service)
        db.session.add(item)
        db.session.commit()

        db.session.delete(item)
        db.session.commit()

        self.assertIsNotNone(db.session.get(Service, service.id))


if __name__ == '__main__':
    unittest.main()
