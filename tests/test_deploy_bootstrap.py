import os
import subprocess
import sys
import tempfile
import textwrap
import unittest


class DeployBootstrapIsolationTests(unittest.TestCase):
    def _run_python(self, source, *, admin_hash=None):
        with tempfile.TemporaryDirectory(prefix='riburom_deploy_bootstrap_') as tmp:
            database_path = os.path.join(tmp, 'bootstrap.db')
            env = os.environ.copy()
            env.update({
                'APP_ENV': 'testing',
                'TESTING': '1',
                'SECRET_KEY': 'deploy-bootstrap-test-secret',
                'ADMIN_PASSWORD': 'deploy-bootstrap-test-password',
                'DATABASE_URL': f'sqlite:///{database_path}',
            })
            if admin_hash is not None:
                env['ADMIN_PASSWORD_HASH'] = admin_hash
            else:
                env.pop('ADMIN_PASSWORD_HASH', None)

            completed = subprocess.run(
                [sys.executable, '-c', textwrap.dedent(source)],
                cwd=os.path.dirname(os.path.dirname(__file__)),
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            if completed.returncode != 0:
                self.fail(
                    'Subprocess failed.\n'
                    f'STDOUT:\n{completed.stdout}\n'
                    f'STDERR:\n{completed.stderr}'
                )

    def test_import_app_does_not_create_database(self):
        self._run_python(
            """
            import os
            import app

            database_path = app.app.config['SQLALCHEMY_DATABASE_URI'].removeprefix('sqlite:///')
            assert not os.path.exists(database_path), (
                'Importing app.py must not create or mutate the configured database'
            )
            """
        )

    def test_explicit_bootstrap_creates_initial_owner_once(self):
        self._run_python(
            """
            from app import app, db, initial_owner_username, run_deploy_bootstrap
            from models import User

            first = run_deploy_bootstrap()
            second = run_deploy_bootstrap()

            with app.app_context():
                assert first['initial_owner_created'] is True
                assert second['initial_owner_created'] is False
                assert User.query.count() == 1
                owner = User.query.one()
                assert owner.username == initial_owner_username
                assert owner.role == 'owner'
                assert owner.is_active is True
            """
        )

    def test_existing_user_prevents_bootstrap_owner_recreation_after_rename(self):
        self._run_python(
            """
            from app import app, db, initial_owner_username, run_deploy_bootstrap
            from models import User

            run_deploy_bootstrap()

            with app.app_context():
                owner = User.query.one()
                owner.username = 'renamed-owner'
                owner.full_name = 'Administratively Renamed'
                owner.email = 'renamed@example.com'
                owner.role = 'enquiries'
                owner.is_active = False
                preserved_hash = owner.password_hash
                db.session.commit()

            result = run_deploy_bootstrap()

            with app.app_context():
                assert result['initial_owner_created'] is False
                assert User.query.count() == 1
                assert User.query.filter_by(username=initial_owner_username).first() is None
                owner = User.query.one()
                assert owner.username == 'renamed-owner'
                assert owner.full_name == 'Administratively Renamed'
                assert owner.email == 'renamed@example.com'
                assert owner.role == 'enquiries'
                assert owner.is_active is False
                assert owner.password_hash == preserved_hash
            """
        )

    def test_existing_user_skips_malformed_bootstrap_hash_validation(self):
        self._run_python(
            """
            from app import app, db, run_deploy_bootstrap
            from models import User
            from werkzeug.security import generate_password_hash

            with app.app_context():
                db.create_all()
                db.session.add(User(
                    username='existing-admin',
                    full_name='Existing Admin',
                    email='existing@example.com',
                    password_hash=generate_password_hash('existing-password'),
                    role='owner',
                    is_active=True,
                ))
                db.session.commit()

            # ADMIN_PASSWORD_HASH is malformed in the environment for this
            # subprocess. Existing account state must not be changed or blocked.
            result = run_deploy_bootstrap()
            assert result['initial_owner_created'] is False
            """,
            admin_hash='not-a-valid-werkzeug-hash',
        )

    def test_legacy_bootstrap_refuses_alembic_managed_database(self):
        self._run_python(
            """
            from unittest.mock import patch
            from app import run_deploy_bootstrap

            with patch('app.inspect') as mocked_inspect:
                mocked_inspect.return_value.has_table.return_value = True
                try:
                    run_deploy_bootstrap()
                except RuntimeError as exc:
                    assert 'not allowed after Alembic adoption' in str(exc)
                else:
                    raise AssertionError('Expected Alembic-managed bootstrap refusal')
            """
        )

    def test_post_migration_bootstrap_does_not_create_schema(self):
        self._run_python(
            """
            from app import app, db, run_post_migration_bootstrap
            from sqlalchemy import inspect

            with app.app_context():
                assert inspect(db.engine).get_table_names() == []

            try:
                run_post_migration_bootstrap()
            except Exception:
                pass

            with app.app_context():
                assert inspect(db.engine).get_table_names() == []
            """
        )


if __name__ == '__main__':
    unittest.main()
