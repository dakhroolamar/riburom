import os
import tempfile
import unittest

from flask import Flask
from flask_migrate import Migrate, upgrade
from sqlalchemy import inspect, text

from models import db
import models as legacy_models
from migrate_to_postgres import create_legacy_tables
import marketplace_models  # noqa: F401 - register Phase A metadata


MARKETPLACE_TABLES = {
    'provider_types',
    'service_categories',
    'providers',
    'provider_type_assignments',
    'services',
}


class MarketplaceMigrationTests(unittest.TestCase):
    def make_app(self, path):
        app = Flask(__name__)
        app.config.update(
            SQLALCHEMY_DATABASE_URI=f'sqlite:///{path}',
            SQLALCHEMY_TRACK_MODIFICATIONS=False,
            TESTING=True,
        )
        db.init_app(app)
        Migrate(app, db, directory='migrations')
        return app

    def test_legacy_schema_preparation_does_not_create_marketplace_tables(self):
        fd, path = tempfile.mkstemp(suffix='.db')
        os.close(fd)
        try:
            app = self.make_app(path)
            with app.app_context():
                original_create_all = db.create_all

                def fail_if_called(*args, **kwargs):
                    raise AssertionError('migrate_to_postgres must not call db.create_all()')

                db.create_all = fail_if_called
                try:
                    create_legacy_tables(db, legacy_models)
                finally:
                    db.create_all = original_create_all

                tables = set(inspect(db.engine).get_table_names())
                self.assertTrue(tables.intersection({
                    'packages',
                    'about_content',
                    'about_sections',
                    'site_settings',
                    'team_members',
                    'messages',
                    'users',
                    'audit_logs',
                }))
                self.assertTrue(MARKETPLACE_TABLES.isdisjoint(tables))

                upgrade(directory='migrations', revision='head')

                tables = set(inspect(db.engine).get_table_names())
                self.assertTrue(MARKETPLACE_TABLES.issubset(tables))
                self.assertEqual(
                    db.session.execute(text('SELECT COUNT(*) FROM provider_types')).scalar_one(),
                    8,
                )
                self.assertEqual(
                    db.session.execute(text('SELECT COUNT(*) FROM service_categories')).scalar_one(),
                    9,
                )
        finally:
            try:
                os.remove(path)
            except FileNotFoundError:
                pass

    def test_phase_a_migration_preserves_legacy_tables_and_data(self):
        fd, path = tempfile.mkstemp(suffix='.db')
        os.close(fd)
        try:
            app = self.make_app(path)

            with app.app_context():
                with db.engine.begin() as connection:
                    connection.execute(text(
                        'CREATE TABLE packages ('
                        'id INTEGER PRIMARY KEY, '
                        'title VARCHAR(200) NOT NULL, '
                        'slug VARCHAR(240) NOT NULL, '
                        'description TEXT NOT NULL)'
                    ))
                    connection.execute(text(
                        "INSERT INTO packages (id, title, slug, description) "
                        "VALUES (1, 'Legacy Tour', 'legacy-tour', 'Legacy data')"
                    ))
                    connection.execute(text(
                        'CREATE TABLE messages ('
                        'id INTEGER PRIMARY KEY, '
                        'email VARCHAR(254) NOT NULL, '
                        'message TEXT NOT NULL)'
                    ))
                    connection.execute(text(
                        "INSERT INTO messages (id, email, message) "
                        "VALUES (1, 'traveller@example.com', 'Existing enquiry')"
                    ))
                    connection.execute(text(
                        'CREATE TABLE users ('
                        'id INTEGER PRIMARY KEY, '
                        'username VARCHAR(80) NOT NULL)'
                    ))
                    connection.execute(text(
                        "INSERT INTO users (id, username) VALUES (1, 'owner')"
                    ))

                upgrade(directory='migrations', revision='head')

                inspector = inspect(db.engine)
                tables = set(inspector.get_table_names())
                for table in MARKETPLACE_TABLES:
                    self.assertIn(table, tables)

                for table in ('packages', 'messages', 'users'):
                    self.assertIn(table, tables)

                package = db.session.execute(
                    text("SELECT title, slug FROM packages WHERE id = 1")
                ).one()
                message = db.session.execute(
                    text("SELECT email, message FROM messages WHERE id = 1")
                ).one()
                user = db.session.execute(
                    text("SELECT username FROM users WHERE id = 1")
                ).one()
                self.assertEqual(tuple(package), ('Legacy Tour', 'legacy-tour'))
                self.assertEqual(tuple(message), ('traveller@example.com', 'Existing enquiry'))
                self.assertEqual(tuple(user), ('owner',))

                provider_types = db.session.execute(
                    text('SELECT COUNT(*) FROM provider_types')
                ).scalar_one()
                service_categories = db.session.execute(
                    text('SELECT COUNT(*) FROM service_categories')
                ).scalar_one()
                self.assertEqual(provider_types, 8)
                self.assertEqual(service_categories, 9)
        finally:
            try:
                os.remove(path)
            except FileNotFoundError:
                pass


if __name__ == '__main__':
    unittest.main()
