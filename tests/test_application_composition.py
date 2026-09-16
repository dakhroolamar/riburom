import os
import subprocess
import sys
import tempfile
import textwrap
import unittest


class ApplicationCompositionTests(unittest.TestCase):
    def _run_python(self, source):
        with tempfile.TemporaryDirectory(prefix='riburom_application_composition_') as tmp:
            database_path = os.path.join(tmp, 'composition.db')
            env = os.environ.copy()
            env.update({
                'APP_ENV': 'testing',
                'TESTING': '1',
                'SECRET_KEY': 'application-composition-secret',
                'ADMIN_PASSWORD': 'application-composition-password',
                'DATABASE_URL': f'sqlite:///{database_path}',
            })
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

    def test_wsgI_composition_registers_workspace_once(self):
        self._run_python(
            """
            import wsgi
            from application_modules import register_application_modules
            from app import app, run_deploy_bootstrap

            run_deploy_bootstrap()
            before = sorted(str(rule) for rule in app.url_map.iter_rules())
            register_application_modules(app)
            after = sorted(str(rule) for rule in app.url_map.iter_rules())

            assert before == after
            rules = set(before)
            required = {
                '/workspace',
                '/workspace/cms',
                '/workspace/cms/media',
                '/workspace/cms/structure',
                '/workspace/marketplace',
                '/workspace/administration',
            }
            assert required.issubset(rules)
            """
        )

    def test_legacy_admin_redirects_to_workspace(self):
        self._run_python(
            """
            import wsgi
            from app import app, db, run_deploy_bootstrap
            from models import User

            run_deploy_bootstrap()
            app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
            client = app.test_client()

            with app.app_context():
                owner = User.query.filter_by(role='owner').one()
                owner_id = owner.id
                session_version = owner.session_version

            with client.session_transaction() as session:
                session['user_id'] = owner_id
                session['session_version'] = session_version

            response = client.get('/admin')
            assert response.status_code == 302
            assert response.headers['Location'] == '/workspace'
            """
        )


if __name__ == '__main__':
    unittest.main()
