import os
import subprocess
import sys
import tempfile
import textwrap
import unittest


class ProductionConfigurationTests(unittest.TestCase):
    def _run(self, source, env_updates):
        env = os.environ.copy()
        for key in (
            'DATABASE_URL',
            'CLOUDINARY_URL',
            'CLOUDINARY_CLOUD_NAME',
            'CLOUDINARY_API_KEY',
            'CLOUDINARY_API_SECRET',
            'USE_CLOUDINARY',
        ):
            env.pop(key, None)
        env.update({
            'APP_ENV': 'production',
            'SECRET_KEY': 'production-config-test-secret',
            'ADMIN_PASSWORD_HASH': 'scrypt:32768:8:1$test$'
                                   '0000000000000000000000000000000000000000000000000000000000000000',
        })
        env.update(env_updates)
        completed = subprocess.run(
            [sys.executable, '-c', textwrap.dedent(source)],
            cwd=os.path.dirname(os.path.dirname(__file__)),
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )
        return completed

    def test_production_refuses_missing_database_url(self):
        completed = self._run(
            'import app',
            {
                'CLOUDINARY_CLOUD_NAME': 'test-cloud',
                'CLOUDINARY_API_KEY': 'test-key',
                'CLOUDINARY_API_SECRET': 'test-secret',
            },
        )
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn('DATABASE_URL must be configured in production', completed.stderr)

    def test_production_refuses_local_media_fallback(self):
        with tempfile.TemporaryDirectory(prefix='riburom_prod_config_') as tmp:
            completed = self._run(
                'import app',
                {'DATABASE_URL': f"sqlite:///{os.path.join(tmp, 'prod.db')}"},
            )
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn('Cloudinary must be configured in production', completed.stderr)

    def test_testing_environment_still_allows_local_storage(self):
        with tempfile.TemporaryDirectory(prefix='riburom_test_config_') as tmp:
            database = os.path.join(tmp, 'test.db')
            env = os.environ.copy()
            for key in (
                'CLOUDINARY_URL',
                'CLOUDINARY_CLOUD_NAME',
                'CLOUDINARY_API_KEY',
                'CLOUDINARY_API_SECRET',
                'USE_CLOUDINARY',
            ):
                env.pop(key, None)
            env.update({
                'APP_ENV': 'testing',
                'TESTING': '1',
                'SECRET_KEY': 'testing-secret',
                'ADMIN_PASSWORD': 'testing-password',
                'DATABASE_URL': f'sqlite:///{database}',
            })
            completed = subprocess.run(
                [sys.executable, '-c', 'import app; print(app.STORAGE_BACKEND)'],
                cwd=os.path.dirname(os.path.dirname(__file__)),
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn('Local disk', completed.stdout)


if __name__ == '__main__':
    unittest.main()
