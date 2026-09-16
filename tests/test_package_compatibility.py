import os
import unittest

from tests.test_bootstrap import configure_isolated_sqlite

class PackageCompatibilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db_path = configure_isolated_sqlite('package_compatibility')

        from app import app, db, run_deploy_bootstrap
        from models import Package, User

        cls.app = app
        cls.db = db
        cls.Package = Package
        cls.User = User
        cls.app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
        run_deploy_bootstrap()
        cls.context = cls.app.app_context()
        cls.context.push()

        user = User(
            username='package-test-owner',
            full_name='Package Test Owner',
            email='package-test-owner@example.com',
            password_hash='not-used',
            role='owner',
            is_active=True,
        )
        db.session.add(user)
        db.session.commit()
        cls.user_id = user.id
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
        with self.client.session_transaction() as session:
            session.clear()
            session['user_id'] = self.user_id

    def tearDown(self):
        self.db.session.rollback()
        self.db.session.query(self.Package).delete()
        self.db.session.commit()

    def test_existing_public_package_routes_still_render(self):
        package = self.Package(
            title='Compatibility Experience',
            slug='compatibility-experience',
            description='Existing Package rendering must remain intact.',
            itinerary='Day 1: Explore.',
            included='Guide.',
            excluded='Flights.',
            published=True,
        )
        self.db.session.add(package)
        self.db.session.commit()

        all_tours = self.client.get('/all_tours')
        detail = self.client.get('/tours/compatibility-experience')

        self.assertEqual(all_tours.status_code, 200)
        self.assertIn(b'Compatibility Experience', all_tours.data)
        self.assertEqual(detail.status_code, 200)
        self.assertIn(b'Compatibility Experience', detail.data)
        self.assertIn(b'Day 1: Explore.', detail.data)
        self.assertIn(b'Guide.', detail.data)
        self.assertIn(b'Flights.', detail.data)

    def test_existing_package_creation_edit_and_delete_routes_still_work(self):
        create_response = self.client.post('/add_package', data={
            'title': 'Created Compatibility Package',
            'description': 'Created through the existing CMS route.',
            'location': 'Meghalaya',
            'duration': '5 days',
            'price': '10000',
            'category': 'Adventure',
            'best_season': 'October',
            'difficulty': 'Moderate',
            'itinerary': 'Day 1',
            'included': 'Guide',
            'excluded': 'Flights',
            'published': '1',
            'featured': '0',
            'sort_order': '1',
        }, follow_redirects=False)
        self.assertEqual(create_response.status_code, 302)

        package = self.Package.query.filter_by(title='Created Compatibility Package').first()
        self.assertIsNotNone(package)
        package_id = package.id

        edit_response = self.client.post(f'/edit_package/{package_id}', data={
            'title': 'Edited Compatibility Package',
            'description': 'Edited through the existing CMS route.',
            'published': '1',
            'featured': '1',
            'sort_order': '2',
        }, follow_redirects=False)
        self.assertEqual(edit_response.status_code, 302)

        edited = self.db.session.get(self.Package, package_id)
        self.assertEqual(edited.title, 'Edited Compatibility Package')
        self.assertEqual(edited.description, 'Edited through the existing CMS route.')

        delete_response = self.client.post(f'/delete_package/{package_id}', follow_redirects=False)
        self.assertEqual(delete_response.status_code, 302)
        self.assertIsNone(self.db.session.get(self.Package, package_id))

    def test_existing_package_can_have_zero_package_items(self):
        package = self.Package(
            title='Zero Item Package',
            slug='zero-item-package',
            description='An existing package can remain independent of marketplace services.',
            published=True,
        )
        self.db.session.add(package)
        self.db.session.commit()

        self.assertEqual(package.package_items, [])


if __name__ == '__main__':
    unittest.main()
