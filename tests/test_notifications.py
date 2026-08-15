import json
import os
import unittest
from unittest.mock import patch

import notifications


class _FakeResponse:
    def __init__(self, status=201):
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False


class BrevoTransportTests(unittest.TestCase):
    def setUp(self):
        self.env = {
            'BREVO_API_KEY': 'test-api-key',
            'BREVO_SENDER_EMAIL': 'verified@example.com',
            'BREVO_SENDER_NAME': 'RI BUROM',
        }
        self.patcher = patch.dict(os.environ, self.env, clear=False)
        self.patcher.start()
        for key in ('SMTP_HOST', 'SMTP_PORT', 'SMTP_USERNAME', 'SMTP_PASSWORD', 'SMTP_FROM', 'SMTP_USE_TLS'):
            os.environ.pop(key, None)

    def tearDown(self):
        self.patcher.stop()

    def test_missing_brevo_config_disables_email(self):
        os.environ.pop('BREVO_API_KEY')
        self.assertEqual(notifications._brevo_missing_config(), ['BREVO_API_KEY'])
        with patch.object(notifications, 'urlopen') as mock_urlopen:
            self.assertFalse(notifications._brevo_send('Subject', 'Body', 'visitor@example.com'))
            mock_urlopen.assert_not_called()

    def test_brevo_send_uses_https_json_api(self):
        captured = {}

        def fake_urlopen(request, timeout):
            captured['url'] = request.full_url
            captured['method'] = request.method
            captured['headers'] = dict(request.header_items())
            captured['body'] = json.loads(request.data.decode('utf-8'))
            captured['timeout'] = timeout
            return _FakeResponse(201)

        with patch.object(notifications, 'urlopen', side_effect=fake_urlopen):
            sent = notifications._brevo_send(
                'New enquiry',
                'Name: Test Visitor',
                'visitor@example.com',
            )

        self.assertTrue(sent)
        self.assertEqual(captured['url'], notifications.BREVO_EMAIL_API_URL)
        self.assertEqual(captured['method'], 'POST')
        self.assertEqual(captured['headers']['Api-key'], 'test-api-key')
        self.assertEqual(captured['headers']['Content-type'], 'application/json')
        self.assertEqual(captured['body']['sender']['email'], 'verified@example.com')
        self.assertEqual(captured['body']['sender']['name'], 'RI BUROM')
        self.assertEqual(captured['body']['to'], [{'email': 'visitor@example.com'}])
        self.assertEqual(captured['body']['subject'], 'New enquiry')
        self.assertEqual(captured['body']['textContent'], 'Name: Test Visitor')
        self.assertEqual(captured['timeout'], 10)

    def test_non_success_brevo_response_is_not_reported_as_sent(self):
        with patch.object(notifications, 'urlopen', return_value=_FakeResponse(500)):
            self.assertFalse(notifications._brevo_send('Subject', 'Body', 'visitor@example.com'))

    def test_recipient_fallback_is_preserved(self):
        os.environ['INITIAL_OWNER_EMAIL'] = 'owner@example.com'
        os.environ.pop('NOTIFICATION_EMAIL', None)
        self.assertEqual(notifications._recipient_email(''), 'owner@example.com')


if __name__ == '__main__':
    unittest.main()
