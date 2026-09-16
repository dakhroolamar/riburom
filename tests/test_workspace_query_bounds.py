import os
import unittest

from tests.test_bootstrap import configure_isolated_sqlite


class WorkspaceQueryBoundTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db_path = configure_isolated_sqlite('workspace_query_bounds')
        import wsgi
        from app import app, db, run_deploy_bootstrap
        from models import Message, User

        cls.app = app
        cls.db = db
        cls.Message = Message
        cls.User = User
        cls.app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
        run_deploy_bootstrap()
        cls.context = app.app_context()
        cls.context.push()
        cls.client = app.test_client()
        cls.owner = User.query.filter_by(role='owner').first()
        cls.owner.permissions_json = None
        db.session.commit()

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
        self.db.session.query(self.Message).delete()
        for index in range(75):
            self.db.session.add(self.Message(
                name=f'Customer {index:02d}',
                email=f'customer{index:02d}@example.com',
                message=f'Enquiry {index:02d}',
                is_read=False,
            ))
        self.db.session.commit()

        with self.client.session_transaction() as session:
            session.clear()
            session['user_id'] = self.owner.id
            session['session_version'] = self.owner.session_version

    def tearDown(self):
        self.db.session.query(self.Message).delete()
        self.db.session.commit()

    def test_operations_inbox_is_paginated(self):
        page_one = self.client.get('/workspace')
        self.assertEqual(page_one.status_code, 200)
        body_one = page_one.get_data(as_text=True)
        self.assertIn('75 total', body_one)
        self.assertIn('Page 1 of 2', body_one)
        self.assertIn('Enquiry 74', body_one)
        self.assertNotIn('Enquiry 00', body_one)

        page_two = self.client.get('/workspace?message_page=2')
        self.assertEqual(page_two.status_code, 200)
        body_two = page_two.get_data(as_text=True)
        self.assertIn('Page 2 of 2', body_two)
        self.assertIn('Enquiry 00', body_two)


if __name__ == '__main__':
    unittest.main()
