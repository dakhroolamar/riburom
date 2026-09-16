"""Durable outbound notifications for RI BUROM enquiries.

Enquiries are committed together with one or more NotificationOutbox rows.
Delivery is then attempted asynchronously by exact outbox ID. If a worker exits
before delivery, the durable row remains PENDING/FAILED and can be retried by
later enquiries or by scripts/process_notification_outbox.py.
"""

import base64
import json
import os
from datetime import datetime
from threading import Thread
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from uuid import uuid4

from flask import current_app, has_app_context

from models import NotificationOutbox, db


BREVO_EMAIL_API_URL = 'https://api.brevo.com/v3/smtp/email'
OUTBOX_MAX_ATTEMPTS = 5
OUTBOX_RETRY_BATCH = 25


def _is_production():
    app_env = (os.environ.get('APP_ENV') or os.environ.get('ENVIRONMENT') or 'production').strip().lower()
    return app_env not in {'development', 'dev', 'testing', 'test'}


def _recipient_email(fallback=''):
    override = (os.environ.get('NOTIFICATION_EMAIL') or '').strip()
    owner = (os.environ.get('INITIAL_OWNER_EMAIL') or '').strip()
    if _is_production():
        # Public CMS contact fields are presentation content, not privileged
        # operational routing controls.
        return override or owner
    return override or (fallback or '').strip() or owner


def _recipient_phone(fallback=''):
    override = (os.environ.get('NOTIFICATION_PHONE') or '').strip()
    owner = (os.environ.get('WHATSAPP_PHONE') or '').strip()
    if _is_production():
        return override or owner
    return override or (fallback or '').strip() or owner


def _brevo_missing_config():
    required = {
        'BREVO_API_KEY': os.environ.get('BREVO_API_KEY'),
        'BREVO_SENDER_EMAIL': os.environ.get('BREVO_SENDER_EMAIL'),
    }
    return [name for name, value in required.items() if not (value or '').strip()]


def _brevo_send(subject, body, recipient):
    if not recipient:
        return False

    if _brevo_missing_config():
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


def _messaging_configured():
    return bool(
        (os.environ.get('TWILIO_ACCOUNT_SID') or '').strip()
        and (os.environ.get('TWILIO_AUTH_TOKEN') or '').strip()
        and (
            (os.environ.get('TWILIO_WHATSAPP_FROM') or '').strip()
            or (os.environ.get('TWILIO_FROM_NUMBER') or '').strip()
        )
    )


def _send_messaging_to(body, recipient_phone):
    if not recipient_phone:
        return False

    whatsapp_from = (os.environ.get('TWILIO_WHATSAPP_FROM') or '').strip()
    if whatsapp_from:
        target = (
            recipient_phone
            if recipient_phone.startswith('whatsapp:')
            else f'whatsapp:{recipient_phone}'
        )
        return _twilio_send(whatsapp_from, body, target)

    sms_from = (os.environ.get('TWILIO_FROM_NUMBER') or '').strip()
    if sms_from:
        return _twilio_send(sms_from, body, recipient_phone)
    return False


def _send_messaging(body, recipient_phone):
    """Compatibility helper that resolves an operational recipient first."""
    return _send_messaging_to(body, _recipient_phone(recipient_phone))


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


def enqueue_new_enquiry(data, *, source_type, source_id):
    """Add durable notification rows to the caller's current DB transaction.

    The caller owns the transaction and must commit the enquiry and returned
    outbox rows together. No network request is made here.
    """
    source_id = str(source_id)
    event_type = 'new_enquiry'
    subject = f"New RI BUROM enquiry — {data.get('name', 'Visitor')}"
    body = _format_enquiry(data)

    existing = {
        row.channel: row
        for row in NotificationOutbox.query.filter_by(
            source_type=source_type,
            source_id=source_id,
            event_type=event_type,
        ).all()
    }
    rows = list(existing.values())

    recipient_email = _recipient_email(data.get('notification_email', ''))
    if recipient_email and 'email' not in existing:
        row = NotificationOutbox(
            source_type=source_type,
            source_id=source_id,
            event_type=event_type,
            channel='email',
            recipient=recipient_email,
            subject=subject,
            body=body,
            status='PENDING',
        )
        db.session.add(row)
        rows.append(row)

    recipient_phone = _recipient_phone(data.get('notification_phone', ''))
    if recipient_phone and _messaging_configured() and 'messaging' not in existing:
        row = NotificationOutbox(
            source_type=source_type,
            source_id=source_id,
            event_type=event_type,
            channel='messaging',
            recipient=recipient_phone,
            subject=None,
            body=body,
            status='PENDING',
        )
        db.session.add(row)
        rows.append(row)

    db.session.flush()
    return [row.id for row in rows]


def _delivery_error(exc):
    if isinstance(exc, HTTPError):
        return f'HTTP {exc.code}'
    if isinstance(exc, URLError):
        return 'network error'
    if isinstance(exc, TimeoutError):
        return 'timeout'
    return type(exc).__name__


def _deliver_outbox_row(row):
    if row.channel == 'email':
        if _brevo_missing_config():
            row.last_error = 'missing Brevo configuration'
            return False
        return _brevo_send(row.subject or 'RI BUROM notification', row.body, row.recipient)
    if row.channel == 'messaging':
        if not _messaging_configured():
            row.last_error = 'missing Twilio configuration'
            return False
        return _send_messaging_to(row.body, row.recipient)
    row.last_error = 'unsupported notification channel'
    return False


def process_outbox_ids(outbox_ids):
    """Attempt exact durable records and return a small delivery summary."""
    summary = {'sent': 0, 'failed': 0, 'skipped': 0}
    for outbox_id in [int(value) for value in outbox_ids if value is not None]:
        row = db.session.get(NotificationOutbox, outbox_id)
        if row is None or row.status == 'SENT':
            summary['skipped'] += 1
            continue
        if row.attempts >= OUTBOX_MAX_ATTEMPTS:
            summary['skipped'] += 1
            continue

        row.attempts += 1
        row.updated_at = datetime.utcnow()
        try:
            sent = _deliver_outbox_row(row)
        except Exception as exc:
            sent = False
            row.last_error = _delivery_error(exc)

        if sent:
            row.status = 'SENT'
            row.sent_at = datetime.utcnow()
            row.last_error = None
            summary['sent'] += 1
        else:
            row.status = 'FAILED'
            if not row.last_error:
                row.last_error = 'delivery not confirmed'
            summary['failed'] += 1
        db.session.commit()
    return summary


def process_pending_notifications(limit=OUTBOX_RETRY_BATCH):
    rows = (
        NotificationOutbox.query
        .filter(
            NotificationOutbox.status.in_(['PENDING', 'FAILED']),
            NotificationOutbox.attempts < OUTBOX_MAX_ATTEMPTS,
        )
        .order_by(NotificationOutbox.created_at.asc(), NotificationOutbox.id.asc())
        .limit(max(1, min(int(limit), 100)))
        .all()
    )
    return process_outbox_ids([row.id for row in rows])


def _dispatch_worker(flask_app, outbox_ids):
    with flask_app.app_context():
        summary = process_outbox_ids(outbox_ids)
        # Opportunistically retry a bounded backlog. This is not a replacement
        # for a scheduled worker, but it guarantees failed rows remain durable
        # and gives them another chance on later enquiry traffic.
        backlog = process_pending_notifications()
        print(
            '[RI BUROM notifications] '
            f"requested_sent={summary['sent']} requested_failed={summary['failed']} "
            f"backlog_sent={backlog['sent']} backlog_failed={backlog['failed']}",
            flush=True,
        )


def dispatch_notification_outbox(outbox_ids):
    """Attempt committed outbox rows without blocking the public response."""
    ids = [int(value) for value in outbox_ids if value is not None]
    if not ids or not has_app_context():
        return
    flask_app = current_app._get_current_object()
    Thread(target=_dispatch_worker, args=(flask_app, ids), daemon=True).start()


def notify_new_enquiry(data):
    """Compatibility API for callers not yet using transaction-owned outbox rows."""
    if not has_app_context():
        raise RuntimeError('notify_new_enquiry requires a Flask application context')
    ids = enqueue_new_enquiry(
        data,
        source_type='legacy_notification',
        source_id=uuid4().hex,
    )
    db.session.commit()
    dispatch_notification_outbox(ids)


def register_notifications(flask_app):
    """Mark the notification extension registered.

    Notification creation now occurs at the exact persistence sites, so the
    former count/newest-row response wrapper is intentionally gone.
    """
    if getattr(flask_app, '_ri_burom_notifications_registered', False):
        return
    flask_app._ri_burom_notifications_registered = True
