import os
import unittest
from unittest.mock import patch

import migrate_to_postgres
from scripts import prepare_production_migrations


class LegacyMaintenanceScriptGuardTests(unittest.TestCase):
    def test_migration_state_repair_requires_explicit_opt_in(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(SystemExit):
                prepare_production_migrations.require_explicit_legacy_mutation_opt_in()

    def test_postgres_copy_requires_explicit_opt_in(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(SystemExit):
                migrate_to_postgres.require_explicit_legacy_mutation_opt_in()

    def test_nonproduction_ack_is_sufficient(self):
        env = {
            'APP_ENV': 'development',
            'RI_BUROM_ALLOW_LEGACY_DB_MUTATION': 'YES',
        }
        with patch.dict(os.environ, env, clear=True):
            prepare_production_migrations.require_explicit_legacy_mutation_opt_in()
            migrate_to_postgres.require_explicit_legacy_mutation_opt_in()

    def test_production_requires_backup_acknowledgement(self):
        env = {
            'APP_ENV': 'production',
            'RI_BUROM_ALLOW_LEGACY_DB_MUTATION': 'YES',
        }
        with patch.dict(os.environ, env, clear=True):
            with self.assertRaises(SystemExit):
                prepare_production_migrations.require_explicit_legacy_mutation_opt_in()
            with self.assertRaises(SystemExit):
                migrate_to_postgres.require_explicit_legacy_mutation_opt_in()

    def test_production_allows_double_acknowledgement(self):
        env = {
            'APP_ENV': 'production',
            'RI_BUROM_ALLOW_LEGACY_DB_MUTATION': 'YES',
            'RI_BUROM_ALLOW_PRODUCTION_LEGACY_DB_MUTATION': 'YES_I_HAVE_A_BACKUP',
        }
        with patch.dict(os.environ, env, clear=True):
            prepare_production_migrations.require_explicit_legacy_mutation_opt_in()
            migrate_to_postgres.require_explicit_legacy_mutation_opt_in()


if __name__ == '__main__':
    unittest.main()
