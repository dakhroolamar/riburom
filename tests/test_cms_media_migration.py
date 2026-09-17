"""Exercise additive migration and downgrade against SQLite and disposable PostgreSQL."""
import os
import unittest
from flask import Flask
from flask_migrate import Migrate, upgrade, downgrade, stamp
from sqlalchemy import inspect, text
from models import db, SiteSettings, Package
from tests.postgres_test_safety import assert_disposable_postgres_url


class CmsMigrationTests(unittest.TestCase):
    url = 'sqlite://'

    def test_upgrade_preserves_legacy_and_registers_images(self):
        app = Flask(__name__)
        app.config.update(SQLALCHEMY_DATABASE_URI=self.url, SQLALCHEMY_TRACK_MODIFICATIONS=False)
        db.init_app(app); Migrate(app, db, directory='migrations')
        with app.app_context():
            # In PostgreSQL the URL guard below only permits a local test database.
            if self.url.startswith('postgresql'):
                with db.engine.begin() as connection:
                    connection.execute(text('DROP SCHEMA public CASCADE'))
                    connection.execute(text('CREATE SCHEMA public'))
            legacy = [table for table in db.metadata.sorted_tables if not table.name.startswith('cms_')]
            db.metadata.create_all(db.engine, tables=legacy)
            settings = SiteSettings(id=1, hero_logo='uploads/legacy-logo.png',
                public_config_json='{"theme":{"galleries":{"home_gallery":["uploads/river.jpg"]}}}')
            package = Package(title='Legacy tour', slug='legacy-tour', description='Keep this', image_file='uploads/cover.jpg')
            db.session.add_all([settings,package]); db.session.commit()
            stamp(directory='migrations',revision='d5e8f0a2b341')
            upgrade(directory='migrations',revision='e6f7a8b9c012')
            rows = db.session.execute(text('SELECT path FROM cms_media_assets')).scalars().all()
            self.assertEqual(set(rows), {'uploads/legacy-logo.png','uploads/river.jpg','uploads/cover.jpg'})
            self.assertEqual(db.session.get(Package, package.id).description, 'Keep this')
            db.session.commit()  # Release PostgreSQL read locks before Alembic DDL.
            downgrade(directory='migrations',revision='d5e8f0a2b341')
            self.assertNotIn('cms_media_assets', inspect(db.engine).get_table_names())
            self.assertEqual(db.session.get(SiteSettings, 1).hero_logo, 'uploads/legacy-logo.png')
            db.session.remove(); db.engine.dispose()


postgres_url = os.environ.get('CMS_TEST_DATABASE_URL')
assert_disposable_postgres_url(postgres_url)


@unittest.skipUnless(postgres_url, 'CMS_TEST_DATABASE_URL is required for PostgreSQL migration QA')
class CmsPostgresMigrationTests(CmsMigrationTests):
    url = postgres_url
