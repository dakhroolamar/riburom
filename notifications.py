"""Outbound notifications for new public enquiries.

Notifications are deliberately optional: the enquiry is stored first and the
public confirmation flow does not depend on an external messaging provider.
Email notifications use Brevo's HTTPS API so they work on Render Free without
SMTP egress. Configure these Render environment variables to enable email:

Email:
  BREVO_API_KEY         Brevo API key
  BREVO_SENDER_EMAIL    verified Brevo sender address
  BREVO_SENDER_NAME     optional sender display name
  NOTIFICATION_EMAIL    optional recipient override

Twilio SMS / WhatsApp:
  NOTIFICATION_PHONE       optional recipient override
  TWILIO_ACCOUNT_SID
  TWILIO_AUTH_TOKEN
  TWILIO_FROM_NUMBER       for SMS
  TWILIO_WHATSAPP_FROM     for WhatsApp, e.g. whatsapp:+14155238886

When overrides are absent, the wrapper uses the business email/phone already
stored in SiteSettings (footer_email/footer_phone), then INITIAL_OWNER_EMAIL
or WHATSAPP_PHONE as final fallbacks.
"""

import base64
import json
import os
from threading import Thread
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from urllib.parse import urlencode

BREVO_EMAIL_API_URL = 'https://api.brevo.com/v3/smtp/email'


def _recipient_email(fallback=''):
    return (os.environ.get('NOTIFICATION_EMAIL') or fallback or os.environ.get('INITIAL_OWNER_EMAIL') or '').strip()


def _recipient_phone(fallback=''):
    return (os.environ.get('NOTIFICATION_PHONE') or fallback or os.environ.get('WHATSAPP_PHONE') or '').strip()


def _brevo_missing_config():
    """Return required Brevo settings that are missing from the environment."""
    required = {
        'BREVO_API_KEY': os.environ.get('BREVO_API_KEY'),
        'BREVO_SENDER_EMAIL': os.environ.get('BREVO_SENDER_EMAIL'),
    }
    return [name for name, value in required.items() if not (value or '').strip()]


def _brevo_send(subject, body, recipient):
    """Send a transactional email through Brevo's HTTPS API.

    Returns True only after Brevo responds with a successful 2xx status.
    Missing configuration is treated as a disabled notification channel rather
    than an application error because enquiry persistence must remain primary.
    """
    if not recipient:
        return False

    missing = _brevo_missing_config()
    if missing:
        return False

    payload = {
        'sender': {
            'email': os.environ['BREVO_SENDER_EMAIL'].strip(),
            'name': (os.environ.get('BREVO_SENDER_NAME') or 'RI BUROM').strip(),
        },
        'to': [{'email': recipient}],
        'subject': subject,
        'textContent': body,
    }
    request = Request(
        BREVO_EMAIL_API_URL,
        data=json.dumps(payload, ensure_ascii=False).encode('utf-8'),
        headers={
            'accept': 'application/json',
            'api-key': os.environ['BREVO_API_KEY'].strip(),
            'content-type': 'application/json',
        },
        method='POST',
    )
    with urlopen(request, timeout=10) as response:
        return 200 <= response.status < 300


def _twilio_send(from_number, body, to_number):
    sid = (os.environ.get('TWILIO_ACCOUNT_SID') or '').strip()
    token = os.environ.get('TWILIO_AUTH_TOKEN') or ''
    if not sid or not token or not from_number or not to_number:
        return False

    encoded = urlencode({'From': from_number, 'To': to_number, 'Body': body}).encode('utf-8')
    auth = base64.b64encode(f'{sid}:{token}'.encode('utf-8')).decode('ascii')
    request = Request(
        f'https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json',
        data=encoded,
        headers={'Authorization': f'Basic {auth}', 'Content-Type': 'application/x-www-form-urlencoded'},
        method='POST',
    )
    with urlopen(request, timeout=10) as response:
        return 200 <= response.status < 300


def _send_messaging(body, recipient_phone):
    phone = _recipient_phone(recipient_phone)
    if not phone:
        return False

    whatsapp_from = (os.environ.get('TWILIO_WHATSAPP_FROM') or '').strip()
    if whatsapp_from:
        target = phone if phone.startswith('whatsapp:') else f'whatsapp:{phone}'
        return _twilio_send(whatsapp_from, body, target)

    sms_from = (os.environ.get('TWILIO_FROM_NUMBER') or '').strip()
    if sms_from:
        return _twilio_send(sms_from, body, phone)
    return False


def _format_enquiry(data):
    return (
        f"New RI BUROM enquiry\n\n"
        f"Name: {data.get('name', '')}\n"
        f"Email: {data.get('email', '')}\n"
        f"Phone / WhatsApp: {data.get('phone') or 'Not provided'}\n"
        f"Travel dates: {data.get('travel_dates') or 'Not provided'}\n"
        f"Travellers: {data.get('travellers') or 'Not provided'}\n"
        f"Experience: {data.get('tour_interest') or 'Not provided'}\n\n"
        f"Message:\n{data.get('message', '')}\n\n"
        f"Open the RI BUROM Operations workspace to review and respond."
    )


def _dispatch(data):
    subject = f"New RI BUROM enquiry — {data.get('name', 'Visitor')}"
    body = _format_enquiry(data)
    outcomes = []

    try:
        recipient_email = _recipient_email(data.get('notification_email', ''))
        if _brevo_send(subject, body, recipient_email):
            outcomes.append('email')
        elif _brevo_missing_config():
            outcomes.append('email-disabled:missing-brevo-config')
    except (HTTPError, URLError, TimeoutError, ValueError) as exc:
        outcomes.append(f'email-error:{exc}')
    except Exception as exc:
        outcomes.append(f'email-error:{exc}')

    try:
        if _send_messaging(body, data.get('notification_phone', '')):
            outcomes.append('messaging')
    except Exception as exc:
        outcomes.append(f'messaging-error:{exc}')

    print(f"[RI BUROM notifications] {json.dumps(outcomes, ensure_ascii=False)}")


def notify_new_enquiry(data):
    """Queue email/SMS/WhatsApp notifications without blocking the visitor."""
    Thread(target=_dispatch, args=(dict(data),), daemon=True).start()


def register_notifications(flask_app):
    """Wrap the existing public enquiry view and notify after persistence."""
    if getattr(flask_app, '_ri_burom_notifications_registered', False):
        return
    flask_app._ri_burom_notifications_registered = True

    from models import Message
    from app import get_site_settings

    original = flask_app.view_functions.get('send_message')
    if original is None:
        raise RuntimeError('send_message view must be registered before notifications')

    def wrapped(*args, **kwargs):
        before_count = Message.query.count()
        response = original(*args, **kwargs)
        after_count = Message.query.count()
        if after_count > before_count:
            message = Message.query.order_by(Message.id.desc()).first()
            settings = get_site_settings()
            if message is not None:
                notify_new_enquiry({
                    'name': message.name,
                    'email': message.email,
                    'phone': message.phone,
                    'travel_dates': message.travel_dates,
                    'travellers': message.travellers,
                    'tour_interest': message.tour_interest,
                    'message': message.message,
                    'notification_email': settings.footer_email,
                    'notification_phone': settings.footer_phone,
                })
        return response

    wrapped.__name__ = original.__name__
    wrapped.__doc__ = original.__doc__
    flask_app.view_functions['send_message'] = wrapped
