import os
import unittest

from flask import Flask
from flask_migrate import Migrate, upgrade
from sqlalchemy import text

from models import db
import marketplace_models  # noqa: F401 - register PackageItem metadata


DATABASE_URL = os.environ.get('MARKETPLACE_TEST_DATABASE_URL')


@unittest.skipUnless(
    DATABASE_URL,
    'MARKETPLACE_TEST_DATABASE_URL is required for PostgreSQL integration tests',
)
class PackageItemPostgresMigrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = Flask(__name__)
        cls.app.config.update(
            SQLALCHEMY_DATABASE_URI=DATABASE_URL,
            SQLALCHEMY_TRACK_MODIFICATIONS=False,
            TESTING=True,
        )
        db.init_app(cls.app)
        Migrate(cls.app, db, directory='migrations')
        cls.context = cls.app.app_context()
        cls.context.push()

    @classmethod
    def tearDownClass(cls):
        db.session.remove()
        cls.context.pop()

    def reset_database(self):
        with db.engine.begin() as connection:
            connection.execute(text(
                'DROP TABLE IF EXISTS package_items, services, provider_type_assignments, '
                'providers, service_categories, provider_types, packages, alembic_version CASCADE'
            ))

    def test_fresh_phase_b_migration_preserves_packages_and_phase_a(self):
        self.reset_database()

        upgrade(directory='migrations', revision='8d1f2c4a9b01')

        with db.engine.begin() as connection:
            connection.execute(text(
                'CREATE TABLE packages ('
                'id SERIAL PRIMARY KEY, '
                'title VARCHAR(200) NOT NULL, '
                'slug VARCHAR(240) NOT NULL UNIQUE, '
                'description TEXT NOT NULL)'
            ))
            connection.execute(text(
                "INSERT INTO packages (title, slug, description) "
                "VALUES ('Existing Package', 'existing-package', 'Legacy package remains.')"
            ))

            provider_id = connection.execute(text(
                "INSERT INTO providers (name, slug, status, is_active, created_at, updated_at) "
                "VALUES ('Guide Co', 'guide-co', 'DRAFT', TRUE, NOW(), NOW()) "
                "RETURNING id"
            )).scalar_one()
            category_id = connection.execute(text(
                "SELECT id FROM service_categories ORDER BY id LIMIT 1"
            )).scalar_one()
            connection.execute(text(
                "INSERT INTO services "
                "(provider_id, category_id, name, slug, status, is_active, created_at, updated_at) "
                "VALUES (:provider_id, :category_id, 'Local Guide', 'local-guide', 'DRAFT', TRUE, NOW(), NOW())"
            ), {'provider_id': provider_id, 'category_id': category_id})

        upgrade(directory='migrations', revision='head')

        with db.engine.connect() as connection:
            self.assertEqual(connection.execute(text('SELECT COUNT(*) FROM packages')).scalar_one(), 1)
            self.assertEqual(connection.execute(text('SELECT COUNT(*) FROM package_items')).scalar_one(), 0)
            self.assertEqual(connection.execute(text('SELECT COUNT(*) FROM providers')).scalar_one(), 1)
            self.assertEqual(connection.execute(text('SELECT COUNT(*) FROM services')).scalar_one(), 1)
            self.assertEqual(
                connection.execute(text('SELECT version_num FROM alembic_version')).scalar_one(),
                '3f7a9c2d1e64',
            )

            fks = connection.execute(text(
                """
                SELECT kcu.column_name, ccu.table_name, ccu.column_name
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu
                  ON tc.constraint_name = kcu.constraint_name
                 AND tc.table_schema = kcu.table_schema
                JOIN information_schema.constraint_column_usage ccu
                  ON ccu.constraint_name = tc.constraint_name
                 AND ccu.table_schema = tc.table_schema
                WHERE tc.table_schema = 'public'
                  AND tc.table_name = 'package_items'
                  AND tc.constraint_type = 'FOREIGN KEY'
                """
            )).all()
            self.assertEqual(
                {(row[0], row[1], row[2]) for row in fks},
                {('package_id', 'packages', 'id'), ('service_id', 'services', 'id')},
            )

            unique = connection.execute(text(
                """
                SELECT kcu.column_name
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu
                  ON tc.constraint_name = kcu.constraint_name
                 AND tc.table_schema = kcu.table_schema
                WHERE tc.table_schema = 'public'
                  AND tc.table_name = 'package_items'
                  AND tc.constraint_name = 'uq_package_item_package_service'
                ORDER BY kcu.ordinal_position
                """
            )).scalars().all()
            self.assertEqual(unique, ['package_id', 'service_id'])

            package_sort_index = connection.execute(text(
                "SELECT indexname FROM pg_indexes "
                "WHERE schemaname='public' AND indexname='ix_package_items_package_sort'"
            )).scalar_one_or_none()
            service_index = connection.execute(text(
                "SELECT indexname FROM pg_indexes "
                "WHERE schemaname='public' AND indexname='ix_package_items_service_id'"
            )).scalar_one_or_none()
            self.assertEqual(package_sort_index, 'ix_package_items_package_sort')
            self.assertEqual(service_index, 'ix_package_items_service_id')

    def test_package_item_does_not_cascade_delete_service(self):
        self.reset_database()
        upgrade(directory='migrations', revision='8d1f2c4a9b01')

        with db.engine.begin() as connection:
            connection.execute(text(
                'CREATE TABLE packages ('
                'id SERIAL PRIMARY KEY, title VARCHAR(200) NOT NULL, '
                'slug VARCHAR(240) NOT NULL UNIQUE, description TEXT NOT NULL)'
            ))
            package_id = connection.execute(text(
                "INSERT INTO packages (title, slug, description) "
                "VALUES ('Package', 'package', 'Package') RETURNING id"
            )).scalar_one()
            provider_id = connection.execute(text(
                "INSERT INTO providers (name, slug, status, is_active, created_at, updated_at) "
                "VALUES ('Provider', 'provider', 'DRAFT', TRUE, NOW(), NOW()) RETURNING id"
            )).scalar_one()
            category_id = connection.execute(text('SELECT id FROM service_categories ORDER BY id LIMIT 1')).scalar_one()
            service_id = connection.execute(text(
                "INSERT INTO services "
                "(provider_id, category_id, name, slug, status, is_active, created_at, updated_at) "
                "VALUES (:provider_id, :category_id, 'Service', 'service', 'DRAFT', TRUE, NOW(), NOW()) RETURNING id"
            ), {'provider_id': provider_id, 'category_id': category_id}).scalar_one()

        upgrade(directory='migrations', revision='head')

        with db.engine.begin() as connection:
            connection.execute(text(
                'INSERT INTO package_items (package_id, service_id, sort_order, created_at, updated_at) '
                'VALUES (:package_id, :service_id, 1, NOW(), NOW())'
            ), {'package_id': package_id, 'service_id': service_id})
            connection.execute(text('DELETE FROM package_items WHERE package_id = :package_id'), {'package_id': package_id})

            self.assertEqual(
                connection.execute(text('SELECT COUNT(*) FROM services WHERE id = :service_id'), {'service_id': service_id}).scalar_one(),
                1,
            )


if __name__ == '__main__':
    unittest.main()
