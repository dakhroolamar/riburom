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

        cls.app = app
        cls.db = db
        cls.statuses = INQUIRY_STATUSES
        cls.context = app.app_context()
        cls.context.push()
        db.create_all()

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


if __name__ == '__main__':
    unittest.main()
