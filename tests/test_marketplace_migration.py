import os
import tempfile
import unittest

from flask import Flask
from flask_migrate import Migrate, upgrade
from sqlalchemy import inspect, text

from models import db
import models as legacy_models
from migrate_to_postgres import create_legacy_tables
from marketplace_models import ProviderType
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

    def make_marketplace_tables(self):
        return [
            marketplace_models.ProviderType.__table__,
            marketplace_models.ServiceCategory.__table__,
            marketplace_models.Provider.__table__,
            marketplace_models.ProviderTypeAssignment.__table__,
            marketplace_models.Service.__table__,
        ]

    def create_pre_alembic_marketplace_schema(self, app):
        with app.app_context():
            statements = (
                """
                CREATE TABLE provider_types (
                    id INTEGER NOT NULL PRIMARY KEY,
                    name VARCHAR(120) NOT NULL,
                    slug VARCHAR(140) NOT NULL,
                    description TEXT,
                    is_active BOOLEAN NOT NULL,
                    sort_order INTEGER NOT NULL,
                    created_at DATETIME NOT NULL,
                    updated_at DATETIME NOT NULL,
                    CONSTRAINT uq_provider_types_slug UNIQUE (slug)
                )
                """,
                """
                CREATE TABLE service_categories (
                    id INTEGER NOT NULL PRIMARY KEY,
                    name VARCHAR(120) NOT NULL,
                    slug VARCHAR(140) NOT NULL,
                    description TEXT,
                    is_active BOOLEAN NOT NULL,
                    sort_order INTEGER NOT NULL,
                    created_at DATETIME NOT NULL,
                    updated_at DATETIME NOT NULL,
                    CONSTRAINT uq_service_categories_slug UNIQUE (slug)
                )
                """,
                """
                CREATE TABLE providers (
                    id INTEGER NOT NULL PRIMARY KEY,
                    name VARCHAR(200) NOT NULL,
                    slug VARCHAR(240) NOT NULL,
                    description TEXT,
                    email VARCHAR(254),
                    phone VARCHAR(40),
                    status VARCHAR(40) NOT NULL,
                    is_active BOOLEAN NOT NULL,
                    created_at DATETIME NOT NULL,
                    updated_at DATETIME NOT NULL,
                    CONSTRAINT uq_providers_slug UNIQUE (slug)
                )
                """,
                """
                CREATE TABLE provider_type_assignments (
                    id INTEGER NOT NULL PRIMARY KEY,
                    provider_id INTEGER NOT NULL,
                    provider_type_id INTEGER NOT NULL,
                    created_at DATETIME NOT NULL,
                    CONSTRAINT uq_provider_type_assignment
                        UNIQUE (provider_id, provider_type_id),
                    FOREIGN KEY(provider_id) REFERENCES providers (id),
                    FOREIGN KEY(provider_type_id) REFERENCES provider_types (id)
                )
                """,
                """
                CREATE TABLE services (
                    id INTEGER NOT NULL PRIMARY KEY,
                    provider_id INTEGER NOT NULL,
                    category_id INTEGER NOT NULL,
                    name VARCHAR(200) NOT NULL,
                    slug VARCHAR(240) NOT NULL,
                    description TEXT,
                    status VARCHAR(40) NOT NULL,
                    is_active BOOLEAN NOT NULL,
                    created_at DATETIME NOT NULL,
                    updated_at DATETIME NOT NULL,
                    CONSTRAINT uq_service_provider_slug
                        UNIQUE (provider_id, slug),
                    FOREIGN KEY(provider_id) REFERENCES providers (id),
                    FOREIGN KEY(category_id) REFERENCES service_categories (id)
                )
                """,
            )

            indexes = (
                "CREATE INDEX ix_provider_types_is_active ON provider_types (is_active)",
                "CREATE INDEX ix_provider_types_sort_order ON provider_types (sort_order)",
                "CREATE INDEX ix_service_categories_is_active ON service_categories (is_active)",
                "CREATE INDEX ix_service_categories_sort_order ON service_categories (sort_order)",
                "CREATE INDEX ix_providers_is_active ON providers (is_active)",
                "CREATE INDEX ix_provider_type_assignments_provider_id ON provider_type_assignments (provider_id)",
                "CREATE INDEX ix_provider_type_assignments_provider_type_id ON provider_type_assignments (provider_type_id)",
                "CREATE INDEX ix_services_provider_id ON services (provider_id)",
                "CREATE INDEX ix_services_category_id ON services (category_id)",
                "CREATE INDEX ix_services_status ON services (status)",
            )

            with db.engine.begin() as connection:
                for statement in statements:
                    connection.execute(text(statement))
                for statement in indexes:
                    connection.execute(text(statement))
    def test_fresh_database_creates_marketplace_schema_and_taxonomy(self):
        fd, path = tempfile.mkstemp(suffix='.db')
        os.close(fd)
        try:
            app = self.make_app(path)
            with app.app_context():
                upgrade(directory='migrations', revision='8d1f2c4a9b01')

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

                defaults = {
                    row['name']: row.get('default')
                    for row in inspect(db.engine).get_columns('providers')
                }
                self.assertIn("'DRAFT'", defaults['status'])
                self.assertIsNotNone(defaults['is_active'])

                version = db.session.execute(
                    text('SELECT version_num FROM alembic_version')
                ).scalar_one()
                self.assertEqual(version, '8d1f2c4a9b01')
        finally:
            try:
                with app.app_context():
                    db.session.remove()
                    db.engine.dispose()
                os.remove(path)
            except FileNotFoundError:
                pass

    def test_legacy_production_shaped_database_is_reconciled_in_place(self):
        fd, path = tempfile.mkstemp(suffix='.db')
        os.close(fd)
        try:
            app = self.make_app(path)
            with app.app_context():
                create_legacy_tables(db, legacy_models)
                self.create_pre_alembic_marketplace_schema(app)

                before_tables = set(inspect(db.engine).get_table_names())
                self.assertTrue(MARKETPLACE_TABLES.issubset(before_tables))
                for table in MARKETPLACE_TABLES:
                    self.assertEqual(
                        db.session.execute(text(f'SELECT COUNT(*) FROM "{table}"')).scalar_one(),
                        0,
                    )

                db.session.add(
                    legacy_models.Package(
                        id=1,
                        title='Legacy Tour',
                        slug='legacy-tour',
                        description='Legacy data',
                        published=False,
                        featured=False,
                        sort_order=1,
                    )
                )
                db.session.commit()

                upgrade(directory='migrations', revision='8d1f2c4a9b01')

                after_tables = set(inspect(db.engine).get_table_names())
                self.assertTrue(MARKETPLACE_TABLES.issubset(after_tables))
                self.assertEqual(
                    db.session.execute(
                        text("SELECT title, slug FROM packages WHERE id = 1")
                    ).one(),
                    ('Legacy Tour', 'legacy-tour'),
                )
                self.assertEqual(
                    db.session.execute(text('SELECT COUNT(*) FROM provider_types')).scalar_one(),
                    8,
                )
                self.assertEqual(
                    db.session.execute(text('SELECT COUNT(*) FROM service_categories')).scalar_one(),
                    9,
                )
                version = db.session.execute(
                    text('SELECT version_num FROM alembic_version')
                ).scalar_one()
                self.assertEqual(version, '8d1f2c4a9b01')
        finally:
            try:
                with app.app_context():
                    db.session.remove()
                    db.engine.dispose()
                os.remove(path)
            except FileNotFoundError:
                pass

    def test_existing_marketplace_table_with_rows_fails(self):
        fd, path = tempfile.mkstemp(suffix='.db')
        os.close(fd)
        try:
            app = self.make_app(path)
            with app.app_context():
                self.create_pre_alembic_marketplace_schema(app)
                db.session.execute(
                    ProviderType.__table__.insert().values(
                        name='Unexpected', slug='unexpected', is_active=True, sort_order=99
                    )
                )
                db.session.commit()

                with self.assertRaises(SystemExit):
                    upgrade(directory='migrations', revision='8d1f2c4a9b01')
        finally:
            try:
                with app.app_context():
                    db.session.remove()
                    db.engine.dispose()
                os.remove(path)
            except FileNotFoundError:
                pass

    def test_unexpected_schema_fails(self):
        fd, path = tempfile.mkstemp(suffix='.db')
        os.close(fd)
        try:
            app = self.make_app(path)
            with app.app_context():
                self.create_pre_alembic_marketplace_schema(app)
                with db.engine.begin() as connection:
                    connection.execute(text('ALTER TABLE provider_types ADD COLUMN unexpected_marker TEXT'))

                with self.assertRaises(SystemExit):
                    upgrade(directory='migrations', revision='8d1f2c4a9b01')
        finally:
            try:
                with app.app_context():
                    db.session.remove()
                    db.engine.dispose()
                os.remove(path)
            except FileNotFoundError:
                pass

    def test_missing_expected_foreign_key_fails(self):
        fd, path = tempfile.mkstemp(suffix='.db')
        os.close(fd)
        try:
            app = self.make_app(path)
            with app.app_context():
                tables = self.make_marketplace_tables()
                db.metadata.create_all(bind=db.engine, tables=tables)
                with db.engine.begin() as connection:
                    connection.execute(text('DROP TABLE provider_type_assignments'))
                    connection.execute(text(
                        'CREATE TABLE provider_type_assignments ('
                        'id INTEGER NOT NULL PRIMARY KEY, '
                        'provider_id INTEGER NOT NULL, '
                        'provider_type_id INTEGER NOT NULL, '
                        'created_at DATETIME NOT NULL, '
                        'CONSTRAINT uq_provider_type_assignment UNIQUE (provider_id, provider_type_id), '
                        'FOREIGN KEY(provider_id) REFERENCES providers (id)'
                        ')'
                    ))
                    connection.execute(text(
                        'CREATE INDEX ix_provider_type_assignments_provider_id '
                        'ON provider_type_assignments (provider_id)'
                    ))
                    connection.execute(text(
                        'CREATE INDEX ix_provider_type_assignments_provider_type_id '
                        'ON provider_type_assignments (provider_type_id)'
                    ))

                with self.assertRaises(SystemExit):
                    upgrade(directory='migrations', revision='8d1f2c4a9b01')
        finally:
            try:
                with app.app_context():
                    db.session.remove()
                    db.engine.dispose()
                os.remove(path)
            except FileNotFoundError:
                pass

    def test_unexpected_taxonomy_rows_fail(self):
        fd, path = tempfile.mkstemp(suffix='.db')
        os.close(fd)
        try:
            app = self.make_app(path)
            with app.app_context():
                self.create_pre_alembic_marketplace_schema(app)
                db.session.execute(
                    ProviderType.__table__.insert().values(
                        name='Unexpected', slug='unexpected', is_active=True, sort_order=99
                    )
                )
                db.session.commit()

                with self.assertRaises(SystemExit):
                    upgrade(directory='migrations', revision='8d1f2c4a9b01')
        finally:
            try:
                with app.app_context():
                    db.session.remove()
                    db.engine.dispose()
                os.remove(path)
            except FileNotFoundError:
                pass

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

                upgrade(directory='migrations', revision='8d1f2c4a9b01')

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
                with app.app_context():
                    db.session.remove()
                    db.engine.dispose()
                os.remove(path)
            except FileNotFoundError:
                pass


if __name__ == '__main__':
    unittest.main()
