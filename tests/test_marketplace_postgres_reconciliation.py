import os
import unittest

from flask import Flask
from flask_migrate import Migrate, upgrade
from sqlalchemy import text

from models import db
import marketplace_models  # noqa: F401 - register Phase A metadata


DATABASE_URL = os.environ.get('MARKETPLACE_TEST_DATABASE_URL')


@unittest.skipUnless(
    DATABASE_URL,
    'MARKETPLACE_TEST_DATABASE_URL is required for PostgreSQL integration tests',
)
class MarketplacePostgresReconciliationTests(unittest.TestCase):
    def make_app(self):
        app = Flask(__name__)
        app.config.update(
            SQLALCHEMY_DATABASE_URI=DATABASE_URL,
            SQLALCHEMY_TRACK_MODIFICATIONS=False,
            TESTING=True,
        )
        db.init_app(app)
        Migrate(app, db, directory='migrations')
        return app

    def reset_database(self, connection):
        connection.execute(text(
            'DROP TABLE IF EXISTS services, provider_type_assignments, providers, '
            'service_categories, provider_types, packages, alembic_version CASCADE'
        ))

    def create_pre_alembic_schema(self, connection):
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
            'CREATE TABLE provider_types ('
            'id INTEGER PRIMARY KEY, '
            'name VARCHAR(120) NOT NULL, '
            'slug VARCHAR(140) NOT NULL, '
            'description TEXT, '
            'is_active BOOLEAN NOT NULL, '
            'sort_order INTEGER NOT NULL, '
            'created_at TIMESTAMP NOT NULL, '
            'updated_at TIMESTAMP NOT NULL)'
        ))
        connection.execute(text(
            'CREATE TABLE service_categories ('
            'id INTEGER PRIMARY KEY, '
            'name VARCHAR(120) NOT NULL, '
            'slug VARCHAR(140) NOT NULL, '
            'description TEXT, '
            'is_active BOOLEAN NOT NULL, '
            'sort_order INTEGER NOT NULL, '
            'created_at TIMESTAMP NOT NULL, '
            'updated_at TIMESTAMP NOT NULL)'
        ))
        connection.execute(text(
            'CREATE TABLE providers ('
            'id INTEGER PRIMARY KEY, '
            'name VARCHAR(200) NOT NULL, '
            'slug VARCHAR(240) NOT NULL, '
            'description TEXT, '
            'email VARCHAR(254), '
            'phone VARCHAR(40), '
            'status VARCHAR(40) NOT NULL, '
            'is_active BOOLEAN NOT NULL, '
            'created_at TIMESTAMP NOT NULL, '
            'updated_at TIMESTAMP NOT NULL)'
        ))
        connection.execute(text(
            'CREATE TABLE provider_type_assignments ('
            'id INTEGER PRIMARY KEY, '
            'provider_id INTEGER NOT NULL REFERENCES providers(id), '
            'provider_type_id INTEGER NOT NULL REFERENCES provider_types(id), '
            'created_at TIMESTAMP NOT NULL, '
            'CONSTRAINT uq_provider_type_assignment UNIQUE (provider_id, provider_type_id))'
        ))
        connection.execute(text(
            'CREATE TABLE services ('
            'id INTEGER PRIMARY KEY, '
            'provider_id INTEGER NOT NULL REFERENCES providers(id), '
            'category_id INTEGER NOT NULL REFERENCES service_categories(id), '
            'name VARCHAR(200) NOT NULL, '
            'slug VARCHAR(240) NOT NULL, '
            'description TEXT, '
            'status VARCHAR(40) NOT NULL, '
            'is_active BOOLEAN NOT NULL, '
            'created_at TIMESTAMP NOT NULL, '
            'updated_at TIMESTAMP NOT NULL, '
            'CONSTRAINT uq_service_provider_slug UNIQUE (provider_id, slug))'
        ))
        connection.execute(text('CREATE UNIQUE INDEX ix_provider_types_slug ON provider_types (slug)'))
        connection.execute(text('CREATE INDEX ix_provider_types_is_active ON provider_types (is_active)'))
        connection.execute(text('CREATE INDEX ix_provider_types_sort_order ON provider_types (sort_order)'))
        connection.execute(text('CREATE UNIQUE INDEX ix_service_categories_slug ON service_categories (slug)'))
        connection.execute(text('CREATE INDEX ix_service_categories_is_active ON service_categories (is_active)'))
        connection.execute(text('CREATE INDEX ix_service_categories_sort_order ON service_categories (sort_order)'))
        connection.execute(text('CREATE UNIQUE INDEX ix_providers_slug ON providers (slug)'))
        connection.execute(text('CREATE INDEX ix_providers_is_active ON providers (is_active)'))
        connection.execute(text('CREATE INDEX ix_provider_type_assignments_provider_id ON provider_type_assignments (provider_id)'))
        connection.execute(text('CREATE INDEX ix_provider_type_assignments_provider_type_id ON provider_type_assignments (provider_type_id)'))
        connection.execute(text('CREATE INDEX ix_services_provider_id ON services (provider_id)'))
        connection.execute(text('CREATE INDEX ix_services_category_id ON services (category_id)'))
        connection.execute(text('CREATE INDEX ix_services_status ON services (status)'))

    def test_fresh_postgresql_migration(self):
        app = self.make_app()
        with app.app_context():
            with db.engine.begin() as connection:
                self.reset_database(connection)
            upgrade(directory='migrations', revision='head')
            with db.engine.connect() as connection:
                self.assertEqual(connection.execute(text('SELECT COUNT(*) FROM provider_types')).scalar_one(), 8)
                self.assertEqual(connection.execute(text('SELECT COUNT(*) FROM service_categories')).scalar_one(), 9)
                self.assertEqual(connection.execute(text("SELECT column_default FROM information_schema.columns WHERE table_name='providers' AND column_name='status'")).scalar_one(), "'DRAFT'::character varying")
                self.assertIsNotNone(connection.execute(text("SELECT column_default FROM information_schema.columns WHERE table_name='providers' AND column_name='is_active'")).scalar_one())
                self.assertEqual(connection.execute(text('SELECT version_num FROM alembic_version')).scalar_one(), '8d1f2c4a9b01')

    def test_existing_empty_production_shape_is_reconciled_in_place(self):
        app = self.make_app()
        with app.app_context():
            with db.engine.begin() as connection:
                self.reset_database(connection)
                self.create_pre_alembic_schema(connection)
                table_oids = {
                    table: connection.execute(text(f"SELECT '{table}'::regclass::oid")).scalar_one()
                    for table in ('provider_types', 'service_categories', 'providers', 'provider_type_assignments', 'services')
                }

            upgrade(directory='migrations', revision='head')

            with db.engine.connect() as connection:
                self.assertEqual(
                    connection.execute(text("SELECT COUNT(*) FROM packages WHERE id=1")).scalar_one(),
                    1,
                )
                self.assertEqual(connection.execute(text('SELECT COUNT(*) FROM provider_types')).scalar_one(), 8)
                self.assertEqual(connection.execute(text('SELECT COUNT(*) FROM service_categories')).scalar_one(), 9)
                self.assertEqual(connection.execute(text('SELECT version_num FROM alembic_version')).scalar_one(), '8d1f2c4a9b01')
                for table, oid in table_oids.items():
                    self.assertEqual(
                        connection.execute(text(f"SELECT '{table}'::regclass::oid")).scalar_one(),
                        oid,
                    )
                defaults = connection.execute(text(
                    "SELECT table_name, column_name, column_default "
                    "FROM information_schema.columns "
                    "WHERE table_name IN ('provider_types','service_categories','providers','services') "
                    "AND column_name IN ('is_active','sort_order','status')"
                )).all()
                default_map = {(row[0], row[1]): row[2] for row in defaults}
                self.assertIsNotNone(default_map[('provider_types', 'is_active')])
                self.assertIsNotNone(default_map[('provider_types', 'sort_order')])
                self.assertIsNotNone(default_map[('service_categories', 'is_active')])
                self.assertIsNotNone(default_map[('service_categories', 'sort_order')])
                self.assertEqual(default_map[('providers', 'status')], "'DRAFT'::character varying")
                self.assertIsNotNone(default_map[('providers', 'is_active')])
                self.assertEqual(default_map[('services', 'status')], "'DRAFT'::character varying")
                self.assertIsNotNone(default_map[('services', 'is_active')])

                # The known pre-Alembic unique slug indexes are converted into
                # canonical unique constraints without weakening enforcement.
                constraints = connection.execute(text(
                    "SELECT conname FROM pg_constraint "
                    "WHERE conname IN ('uq_provider_types_slug', 'uq_service_categories_slug', 'uq_providers_slug')"
                )).scalars().all()
                self.assertEqual(set(constraints), {
                    'uq_provider_types_slug',
                    'uq_service_categories_slug',
                    'uq_providers_slug',
                })


if __name__ == '__main__':
    unittest.main()
