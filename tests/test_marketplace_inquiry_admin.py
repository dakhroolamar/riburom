import os
import unittest

from tests.test_bootstrap import configure_isolated_sqlite


class MarketplaceInquiryAdminTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db_path = configure_isolated_sqlite('marketplace_inquiry_admin')
        import wsgi
        from app import app, db
        from marketplace_models import INQUIRY_STATUSES
        from models import User

        cls.app = app
        cls.db = db
        cls.User = User
        cls.statuses = INQUIRY_STATUSES
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

    def test_inquiry_admin_routes_are_registered(self):
        rules = {rule.endpoint: rule.rule for rule in self.app.url_map.iter_rules()}
        self.assertEqual(rules['workspace_marketplace_inquiries'], '/workspace/marketplace/inquiries')
        self.assertEqual(rules['workspace_marketplace_inquiry_detail'], '/workspace/marketplace/inquiries/<int:id>')
        self.assertEqual(rules['marketplace_inquiry_status_update'], '/workspace/marketplace/inquiries/<int:id>/status')

    def test_status_workflow_contains_expected_operational_states(self):
        expected = {'NEW', 'CONTACTED', 'IN_PROGRESS', 'QUOTED', 'CONFIRMED', 'DECLINED', 'CLOSED'}
        self.assertTrue(expected.issubset(self.statuses))

    def test_inquiry_model_has_operational_fields(self):
        from marketplace_models import MarketplaceInquiry

        for field in ('provider_name', 'service_name', 'category_name', 'name', 'email', 'requirements', 'status', 'created_at', 'updated_at'):
            self.assertIsNotNone(getattr(MarketplaceInquiry, field))

    def test_enquiries_role_has_marketplace_pii_permissions(self):
        from models import ROLE_PERMISSIONS

        self.assertIn('view_marketplace_inquiries', ROLE_PERMISSIONS['enquiries'])
        self.assertIn('manage_marketplace_inquiries', ROLE_PERMISSIONS['enquiries'])
        self.assertNotIn('view_marketplace_inquiries', ROLE_PERMISSIONS['content_manager'])

    def test_catalogue_only_permission_cannot_view_traveller_inquiries(self):
        user = self.User(
            username='catalogue-only-test',
            full_name='Catalogue Only',
            email='catalogue-only@example.com',
            password_hash='unused',
            role='custom',
            permissions_json='["view_marketplace"]',
            is_active=True,
        )
        self.db.session.add(user)
        self.db.session.commit()
        try:
            with self.client.session_transaction() as session:
                session.clear()
                session['user_id'] = user.id
                session['session_version'] = user.session_version
            response = self.client.get('/workspace/marketplace/inquiries')
            self.assertEqual(response.status_code, 403)
        finally:
            self.db.session.delete(user)
            self.db.session.commit()


if __name__ == '__main__':
    unittest.main()
