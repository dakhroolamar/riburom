import importlib.util
import os
import tempfile
import unittest

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect, text


MIGRATION_PATH = os.path.join(
    os.path.dirname(__file__), '..', 'migrations', 'versions',
    'b4c7d9e1f203_add_hero_animation_video.py',
)


def load_migration():
    spec = importlib.util.spec_from_file_location('hero_video_migration', MIGRATION_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class HeroAnimationMigrationTests(unittest.TestCase):
    def test_revision_is_linear_after_current_marketplace_head(self):
        migration = load_migration()
        self.assertEqual(migration.revision, 'b4c7d9e1f203')
        self.assertEqual(migration.down_revision, '9b2d4f6c8e10')

    def test_upgrade_adds_nullable_video_column_to_existing_site_settings(self):
        engine = create_engine('sqlite+pysqlite:///:memory:')
        with engine.begin() as connection:
            connection.execute(text('CREATE TABLE site_settings (id INTEGER PRIMARY KEY)'))
            context = MigrationContext.configure(connection)
            operations = Operations(context)
            migration = load_migration()
            migration.op = operations
            migration.upgrade()
            columns = {column['name']: column for column in inspect(connection).get_columns('site_settings')}
            self.assertIn('hero_animation_video', columns)
            self.assertTrue(columns['hero_animation_video']['nullable'])

    def test_downgrade_removes_video_column(self):
        engine = create_engine('sqlite+pysqlite:///:memory:')
        with engine.begin() as connection:
            connection.execute(text('CREATE TABLE site_settings (id INTEGER PRIMARY KEY)'))
            context = MigrationContext.configure(connection)
            operations = Operations(context)
            migration = load_migration()
            migration.op = operations
            migration.upgrade()
            migration.downgrade()
            columns = {column['name'] for column in inspect(connection).get_columns('site_settings')}
            self.assertNotIn('hero_animation_video', columns)


if __name__ == '__main__':
    unittest.main()
