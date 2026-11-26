import json
import os
import unittest
from urllib.parse import parse_qs
from unittest.mock import patch

import notifications


class _FakeResponse:
    def __init__(self, status=201, body=b''):
        self.status = status
        self.body = body

    def read(self, limit):
        return self.body[:limit]

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
        for key in ('BREVO_CLIENT_ID', 'BREVO_CLIENT_SECRET', 'SMTP_HOST', 'SMTP_PORT',
                    'SMTP_USERNAME', 'SMTP_PASSWORD', 'SMTP_FROM', 'SMTP_USE_TLS'):
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

    def test_brevo_oauth_requests_a_scoped_token_and_uses_it_for_delivery(self):
        with patch.dict(os.environ, {'BREVO_CLIENT_ID': 'test-client', 'BREVO_CLIENT_SECRET': 'test-secret'}), \
                patch.object(notifications, 'urlopen', side_effect=[
                    _FakeResponse(200, b'{"access_token":"test-token"}'), _FakeResponse(201),
                ]) as api:
            self.assertTrue(notifications._brevo_send('Test', 'Café', 'visitor@example.com'))

        token_request, email_request = (call.args[0] for call in api.call_args_list)
        self.assertEqual(token_request.full_url, notifications.BREVO_TOKEN_API_URL)
        self.assertEqual(parse_qs(token_request.data.decode('ascii')), {
            'client_id': ['test-client'], 'client_secret': ['test-secret'],
            'grant_type': ['client_credentials'], 'scope': ['transactional.email:write'],
        })
        self.assertEqual(email_request.full_url, notifications.BREVO_EMAIL_API_URL)
        self.assertEqual(email_request.get_header('Authorization'), 'Bearer test-token')
        self.assertIsNone(email_request.get_header('Api-key'))
        self.assertEqual(json.loads(email_request.data)['textContent'], 'Café')

    def test_partial_oauth_config_does_not_fall_back_to_api(self):
        with patch.dict(os.environ, {'BREVO_CLIENT_ID': 'test-client'}), \
                patch.object(notifications, 'urlopen') as api:
            self.assertEqual(notifications._brevo_missing_config(), ['BREVO_CLIENT_SECRET'])
            self.assertFalse(notifications._brevo_send('Test', 'Body', 'visitor@example.com'))
            api.assert_not_called()

    def test_brevo_oauth_failure_retains_only_allowlisted_provider_code(self):
        for body, expected in (
            (b'{"error":"invalid_client","error_description":"private details"}', 'invalid_client'),
            (b'{"error":"private details"}', None),
        ):
            with self.subTest(expected=expected), patch.dict(os.environ, {
                'BREVO_CLIENT_ID': 'test-client', 'BREVO_CLIENT_SECRET': 'test-secret',
            }), patch.object(notifications, '_brevo_http', return_value=(401, body)) as transport:
                with self.assertRaises(notifications.BrevoOAuthError) as failure:
                    notifications._brevo_send('Test', 'Body', 'visitor@example.com')
                self.assertEqual(failure.exception.code, 401)
                self.assertEqual(failure.exception.provider_code, expected)
                self.assertNotIn('private details', str(failure.exception))
                transport.assert_called_once()

    def test_recipient_fallback_is_preserved(self):
        os.environ['INITIAL_OWNER_EMAIL'] = 'owner@example.com'
        os.environ.pop('NOTIFICATION_EMAIL', None)
        self.assertEqual(notifications._recipient_email(''), 'owner@example.com')

    def test_production_ignores_cms_recipient_fallback(self):
        with patch.dict(os.environ, {
            'APP_ENV': 'production',
            'NOTIFICATION_EMAIL': 'operations@example.com',
        }, clear=False):
            self.assertEqual(
                notifications._recipient_email('cms-editor@example.com'),
                'operations@example.com',
            )

        with patch.dict(os.environ, {
            'APP_ENV': 'production',
            'INITIAL_OWNER_EMAIL': 'owner@example.com',
        }, clear=False):
            os.environ.pop('NOTIFICATION_EMAIL', None)
            self.assertEqual(
                notifications._recipient_email('cms-editor@example.com'),
                'owner@example.com',
            )


if __name__ == '__main__':
    unittest.main()
