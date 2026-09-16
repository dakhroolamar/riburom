import os
import subprocess
import sys
import tempfile
import textwrap
import unittest


class NotificationOutboxIntegrationTests(unittest.TestCase):
    def _run(self, source):
        with tempfile.TemporaryDirectory(prefix='riburom_outbox_') as tmp:
            database_path = os.path.join(tmp, 'outbox.db')
            env = os.environ.copy()
            env.update({
                'APP_ENV': 'testing',
                'TESTING': '1',
                'SECRET_KEY': 'outbox-test-secret',
                'ADMIN_PASSWORD': 'outbox-test-password',
                'DATABASE_URL': f'sqlite:///{database_path}',
                'NOTIFICATION_EMAIL': 'operations@example.com',
            })
            for key in (
                'TWILIO_ACCOUNT_SID',
                'TWILIO_AUTH_TOKEN',
                'TWILIO_FROM_NUMBER',
                'TWILIO_WHATSAPP_FROM',
            ):
                env.pop(key, None)

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

    def test_general_enquiry_and_outbox_commit_together(self):
        self._run(
            """
            from unittest.mock import patch

            import wsgi
            from app import app, db, run_deploy_bootstrap
            from models import Message, NotificationOutbox

            app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
            run_deploy_bootstrap()
            client = app.test_client()

            with patch('notifications.dispatch_notification_outbox') as dispatch:
                response = client.post('/send_message', data={
                    'name': 'Outbox Visitor',
                    'email': 'visitor@example.com',
                    'phone': '+911234567890',
                    'travellers': '2',
                    'message': 'Please help plan this trip.',
                })

            assert response.status_code == 302
            with app.app_context():
                message = Message.query.one()
                outbox = NotificationOutbox.query.one()
                assert outbox.source_type == 'general_message'
                assert outbox.source_id == str(message.id)
                assert outbox.channel == 'email'
                assert outbox.recipient == 'operations@example.com'
                assert outbox.status == 'PENDING'
                assert 'Outbox Visitor' in outbox.body
            dispatch.assert_called_once()
            """
        )

    def test_outbox_delivery_updates_exact_record(self):
        self._run(
            """
            from unittest.mock import patch

            from app import app, db, run_deploy_bootstrap
            from models import NotificationOutbox
            import notifications

            run_deploy_bootstrap()
            with app.app_context():
                row = NotificationOutbox(
                    source_type='test',
                    source_id='1',
                    event_type='new_enquiry',
                    channel='email',
                    recipient='operations@example.com',
                    subject='Test',
                    body='Exact row',
                )
                db.session.add(row)
                db.session.commit()
                row_id = row.id

                with patch.object(notifications, '_brevo_send', return_value=True):
                    summary = notifications.process_outbox_ids([row_id])

                delivered = db.session.get(NotificationOutbox, row_id)
                assert summary['sent'] == 1
                assert delivered.status == 'SENT'
                assert delivered.attempts == 1
                assert delivered.sent_at is not None
            """
        )


if __name__ == '__main__':
    unittest.main()
