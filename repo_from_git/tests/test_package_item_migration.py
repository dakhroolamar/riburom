import unittest

from flask import Flask
from flask_migrate import Migrate, upgrade
from sqlalchemy import inspect, text

from models import Package, db
import marketplace_models  # noqa: F401 - register PackageItem metadata


PHASE_B_REVISION = '3f7a9c2d1e64'


class PackageItemMigrationTests(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.config.update(
            SQLALCHEMY_DATABASE_URI='sqlite:///:memory:',
            SQLALCHEMY_TRACK_MODIFICATIONS=False,
            TESTING=True,
        )
        db.init_app(self.app)
        Migrate(self.app, db, directory='migrations')
        self.context = self.app.app_context()
        self.context.push()

    def tearDown(self):
        db.session.remove()
        db.engine.dispose()
        self.context.pop()

    def _create_legacy_packages(self):
        Package.__table__.create(bind=db.engine)
        db.session.add(Package(
            title='Existing Meghalaya Package',
            slug='existing-meghalaya-package',
            description='Legacy package data must remain unchanged.',
            location='Meghalaya',
            published=True,
        ))
        db.session.commit()

    def test_fresh_migration_creates_package_items_without_populating_it(self):
        self._create_legacy_packages()

        upgrade(directory='migrations', revision=PHASE_B_REVISION)

        inspector = inspect(db.engine)
        self.assertIn('package_items', inspector.get_table_names())
        self.assertEqual(db.session.query(Package).count(), 1)
        self.assertEqual(db.session.query(Package).filter_by(slug='existing-meghalaya-package').count(), 1)
        self.assertEqual(db.session.execute(text('SELECT COUNT(*) FROM package_items')).scalar_one(), 0)

        foreign_keys = db.session.execute(text(
            """
            SELECT table_name, column_name, foreign_table_name
            FROM (
                SELECT
                    tc.table_name,
                    kcu.column_name,
                    ccu.table_name AS foreign_table_name
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu
                  ON tc.constraint_name = kcu.constraint_name
                 AND tc.table_schema = kcu.table_schema
                JOIN information_schema.constraint_column_usage ccu
                  ON ccu.constraint_name = tc.constraint_name
                 AND ccu.table_schema = tc.table_schema
                WHERE tc.constraint_type = 'FOREIGN KEY'
            ) fk
            WHERE table_name = 'package_items'
            """
        )) if db.engine.dialect.name == 'postgresql' else None

        if foreign_keys is not None:
            pairs = {(row[0], row[1], row[2]) for row in foreign_keys}
            self.assertIn(('package_items', 'package_id', 'packages'), pairs)
            self.assertIn(('package_items', 'service_id', 'services'), pairs)

        unique_constraints = inspect(db.engine).get_unique_constraints('package_items')
        self.assertIn(
            ('package_id', 'service_id'),
            [tuple(constraint['column_names']) for constraint in unique_constraints],
        )

    def test_existing_phase_a_state_remains_compatible_with_package_items_migration(self):
        self._create_legacy_packages()
        upgrade(directory='migrations', revision='8d1f2c4a9b01')

        self.assertEqual(db.session.execute(text('SELECT COUNT(*) FROM provider_types')).scalar_one(), 8)
        self.assertEqual(db.session.execute(text('SELECT COUNT(*) FROM service_categories')).scalar_one(), 9)
        self.assertEqual(db.session.execute(text('SELECT COUNT(*) FROM providers')).scalar_one(), 0)
        self.assertEqual(db.session.execute(text('SELECT COUNT(*) FROM services')).scalar_one(), 0)

        upgrade(directory='migrations', revision=PHASE_B_REVISION)

        self.assertEqual(db.session.execute(text('SELECT COUNT(*) FROM package_items')).scalar_one(), 0)
        self.assertEqual(db.session.execute(text('SELECT COUNT(*) FROM packages')).scalar_one(), 1)
        self.assertEqual(
            db.session.execute(text('SELECT version_num FROM alembic_version')).scalar_one(),
            PHASE_B_REVISION,
        )

    def test_package_item_migration_requires_existing_packages_table(self):
        with self.assertRaises(SystemExit):
            upgrade(directory='migrations', revision=PHASE_B_REVISION)


if __name__ == '__main__':
    unittest.main()
