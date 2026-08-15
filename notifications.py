"""Outbound notifications for new public enquiries.

Notifications are deliberately optional: the enquiry is stored first and the
public confirmation flow does not depend on SMTP or a messaging provider.
Configure these Render environment variables to enable notifications:

Email:
  NOTIFICATION_EMAIL      recipient
  SMTP_HOST, SMTP_PORT
  SMTP_USERNAME, SMTP_PASSWORD
  SMTP_FROM               optional sender; defaults to SMTP_USERNAME
  SMTP_USE_TLS             optional, defaults to true for port 587

Twilio SMS / WhatsApp:
  NOTIFICATION_PHONE
  TWILIO_ACCOUNT_SID
  TWILIO_AUTH_TOKEN
  TWILIO_FROM_NUMBER       for SMS
  TWILIO_WHATSAPP_FROM     for WhatsApp, e.g. whatsapp:+14155238886

NOTIFICATION_PHONE falls back to WHATSAPP_PHONE when present so an existing
configured number can be reused deliberately.
"""

import base64
import json
import os
import smtplib
import ssl
from email.message import EmailMessage
from threading import Thread
from urllib.parse import urlencode
from urllib.request import Request, urlopen


def _recipient_email():
    return (os.environ.get('NOTIFICATION_EMAIL') or os.environ.get('INITIAL_OWNER_EMAIL') or '').strip()


def _recipient_phone():
    return (os.environ.get('NOTIFICATION_PHONE') or os.environ.get('WHATSAPP_PHONE') or '').strip()


def _smtp_send(subject, body):
    recipient = _recipient_email()
    host = (os.environ.get('SMTP_HOST') or '').strip()
    if not recipient or not host:
        return False

    port = int(os.environ.get('SMTP_PORT', '587'))
    username = (os.environ.get('SMTP_USERNAME') or '').strip()
    password = os.environ.get('SMTP_PASSWORD') or ''
    sender = (os.environ.get('SMTP_FROM') or username or recipient).strip()
    use_tls = (os.environ.get('SMTP_USE_TLS', 'true').strip().lower() not in {'0', 'false', 'no', 'off'})

    msg = EmailMessage()
    msg['Subject'] = subject
    msg['From'] = sender
    msg['To'] = recipient
    msg.set_content(body)

    if port == 465:
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(host, port, timeout=10, context=context) as server:
            if username:
                server.login(username, password)
            server.send_message(msg)
        return True

    with smtplib.SMTP(host, port, timeout=10) as server:
        if use_tls:
            server.starttls(context=ssl.create_default_context())
        if username:
            server.login(username, password)
        server.send_message(msg)
    return True


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


def _send_messaging(body):
    phone = _recipient_phone()
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
        if _smtp_send(subject, body):
            outcomes.append('email')
    except Exception as exc:
        outcomes.append(f'email-error:{exc}')

    try:
        if _send_messaging(body):
            outcomes.append('messaging')
    except Exception as exc:
        outcomes.append(f'messaging-error:{exc}')

    # Avoid importing Flask/app here. The worker is intentionally independent
    # of the request lifecycle so notification failure can never break a public
    # enquiry submission.
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

    original = flask_app.view_functions.get('send_message')
    if original is None:
        raise RuntimeError('send_message view must be registered before notifications')

    def wrapped(*args, **kwargs):
        before_count = Message.query.count()
        response = original(*args, **kwargs)
        after_count = Message.query.count()
        if after_count > before_count:
            message = Message.query.order_by(Message.id.desc()).first()
            if message is not None:
                notify_new_enquiry({
                    'name': message.name,
                    'email': message.email,
                    'phone': message.phone,
                    'travel_dates': message.travel_dates,
                    'travellers': message.travellers,
                    'tour_interest': message.tour_interest,
                    'message': message.message,
                })
        return response

    wrapped.__name__ = original.__name__
    wrapped.__doc__ = original.__doc__
    flask_app.view_functions['send_message'] = wrapped
