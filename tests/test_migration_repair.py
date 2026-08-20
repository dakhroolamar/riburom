import unittest
from unittest.mock import Mock

from migrations.env import (
    LEGACY_BASE_REVISION,
    LEGACY_MIGRATION_HEADS,
    MERGED_REVISION,
    _repair_legacy_marketplace_version_state,
)


class MigrationRepairTests(unittest.TestCase):
    def test_repairs_known_legacy_head_state(self):
        connection = Mock()
        inspector = Mock()
        connection.inspect = inspector
        inspector.get_table_names.return_value = [
            'alembic_version',
            'marketplace_inquiries',
            'package_items',
            'service_images',
        ]
        inspector.get_columns.return_value = [
            {'name': 'id'},
            {'name': 'selected_services_json'},
        ]
        connection.execute.side_effect = [
            Mock(fetchall=lambda: [(LEGACY_BASE_REVISION,), ('3f7a9c2d1e64',), ('7f1c9e4a6b20',)]),
        ]

        _repair_legacy_marketplace_version_state(connection)

        self.assertGreaterEqual(connection.execute.call_count, 2)

    def test_ignores_unrelated_revision_state(self):
        connection = Mock()
        inspector = Mock()
        inspector.get_table_names.return_value = ['alembic_version']
        connection.execute.return_value = Mock(fetchall=lambda: [('8d1f2c4a9b01',)])
        with unittest.mock.patch('migrations.env.sa.inspect', return_value=inspector):
            _repair_legacy_marketplace_version_state(connection)
        self.assertEqual(connection.execute.call_count, 1)


if __name__ == '__main__':
    unittest.main()
