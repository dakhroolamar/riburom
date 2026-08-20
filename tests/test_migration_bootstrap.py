from __future__ import annotations

import unittest

from sqlalchemy import create_engine, text

from scripts.prepare_production_migrations import (
    BASE_REVISION,
    repair_legacy_migration_state,
)


class MigrationBootstrapTests(unittest.TestCase):
    def _database(self):
        engine = create_engine("sqlite+pysqlite:///:memory:")
        with engine.begin() as connection:
            connection.execute(text("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)"))
            connection.execute(text("CREATE TABLE packages (id INTEGER PRIMARY KEY)"))
            connection.execute(text("CREATE TABLE services (id INTEGER PRIMARY KEY)"))
            connection.execute(text("CREATE TABLE package_items (id INTEGER PRIMARY KEY)"))
        return engine

    def test_repairs_known_dirty_version_state(self):
        engine = self._database()
        with engine.begin() as connection:
            connection.execute(
                text("INSERT INTO alembic_version (version_num) VALUES (:revision)"),
                {"revision": BASE_REVISION},
            )
            connection.execute(
                text("INSERT INTO alembic_version (version_num) VALUES (:revision)"),
                {"revision": "7f1c9e4a6b20"},
            )

            self.assertTrue(repair_legacy_migration_state(connection))
            versions = {
                row[0]
                for row in connection.execute(
                    text("SELECT version_num FROM alembic_version")
                ).fetchall()
            }
            self.assertEqual(versions, {BASE_REVISION})

    def test_unrelated_state_is_left_untouched(self):
        engine = self._database()
        with engine.begin() as connection:
            connection.execute(
                text("INSERT INTO alembic_version (version_num) VALUES (:revision)"),
                {"revision": "8d1f2c4a9b01"},
            )

            self.assertFalse(repair_legacy_migration_state(connection))
            versions = {
                row[0]
                for row in connection.execute(
                    text("SELECT version_num FROM alembic_version")
                ).fetchall()
            }
            self.assertEqual(versions, {"8d1f2c4a9b01"})

    def test_known_dirty_state_requires_phase_b_baseline(self):
        engine = create_engine("sqlite+pysqlite:///:memory:")
        with engine.begin() as connection:
            connection.execute(text("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)"))
            connection.execute(text("INSERT INTO alembic_version (version_num) VALUES ('3f7a9c2d1e64')"))
            connection.execute(text("INSERT INTO alembic_version (version_num) VALUES ('7f1c9e4a6b20')"))
            connection.execute(text("CREATE TABLE packages (id INTEGER PRIMARY KEY)"))
            connection.execute(text("CREATE TABLE services (id INTEGER PRIMARY KEY)"))

            with self.assertRaises(RuntimeError):
                repair_legacy_migration_state(connection)


if __name__ == "__main__":
    unittest.main()
