"""Durable outbound notifications for RI BUROM enquiries.

Enquiries are committed together with one or more NotificationOutbox rows.
Delivery runs in a periodic worker with exclusive leases and retry backoff.
Records survive worker restarts and can also be processed by the CLI worker.
"""

import base64
import json
import os
from datetime import datetime, timedelta
from threading import Thread, Event, Lock
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from uuid import uuid4

from flask import current_app, has_app_context

from models import NotificationOutbox, db
from sqlalchemy import and_, or_, update


BREVO_EMAIL_API_URL = 'https://api.brevo.com/v3/smtp/email'
OUTBOX_MAX_ATTEMPTS = 5
OUTBOX_RETRY_BATCH = 25
OUTBOX_LEASE_SECONDS = 120
_worker_lock = Lock()


def delivery_preferences():
    from control_room_models import ControlPreference
    preference = db.session.get(ControlPreference, 'delivery')
    return json.loads(preference.value_json) if preference else {}


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
    preferences = delivery_preferences()

    recipient_email = _recipient_email(data.get('notification_email', ''))
    if recipient_email and preferences.get('email', True) and 'email' not in existing:
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
    if recipient_phone and preferences.get('messaging', True) and _messaging_configured() and 'messaging' not in existing:
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
    if row.channel == 'indexnow':
        from indexnow import submit_indexnow_urls, get_indexnow_key
        if not get_indexnow_key():
            row.last_error = 'missing IndexNow configuration'
            return False
        return submit_indexnow_urls(json.loads(row.body), timeout=3).get('ok', False)
    if row.channel in ('email', 'messaging') and not delivery_preferences().get(row.channel, True):
        row.last_error = 'delivery disabled by owner'
        return False
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


def _eligible_delivery(now):
    return and_(NotificationOutbox.attempts < OUTBOX_MAX_ATTEMPTS, or_(
        and_(NotificationOutbox.status.in_(['PENDING', 'FAILED']),
             or_(NotificationOutbox.next_attempt_at.is_(None), NotificationOutbox.next_attempt_at <= now)),
        and_(NotificationOutbox.status == 'PROCESSING', NotificationOutbox.next_attempt_at <= now)))


def process_outbox_ids(outbox_ids):
    """Attempt exact durable records and return a small delivery summary."""
    summary = {'sent': 0, 'failed': 0, 'skipped': 0}
    for outbox_id in [int(value) for value in outbox_ids if value is not None]:
        now = datetime.utcnow()
        token = uuid4().hex
        claim = db.session.execute(update(NotificationOutbox).where(
            NotificationOutbox.id == outbox_id, _eligible_delivery(now)
        ).values(status='PROCESSING', claim_token=token,
                 attempts=NotificationOutbox.attempts + 1, updated_at=now,
                 next_attempt_at=now + timedelta(seconds=OUTBOX_LEASE_SECONDS)),
            execution_options={'synchronize_session': False})
        db.session.commit()
        if claim.rowcount != 1:
            summary['skipped'] += 1
            continue
        row = db.session.get(NotificationOutbox, outbox_id, populate_existing=True)
        disabled = row.channel in ('email', 'messaging') and not delivery_preferences().get(row.channel, True)
        try:
            sent = False if disabled else _deliver_outbox_row(row)
        except Exception as exc:
            sent = False
            row.last_error = _delivery_error(exc)

        if disabled:
            values = dict(status='CANCELLED', last_error='delivery disabled by owner', next_attempt_at=None)
            summary['skipped'] += 1
        elif sent:
            values = dict(status='SENT', sent_at=datetime.utcnow(), last_error=None, next_attempt_at=None)
            summary['sent'] += 1
        else:
            if not row.last_error:
                row.last_error = 'delivery not confirmed'
            values = dict(status='FAILED', last_error=row.last_error,
                          next_attempt_at=datetime.utcnow() + timedelta(seconds=min(3600, 30 * 2 ** (row.attempts - 1))))
            summary['failed'] += 1
        # Do not let a late worker overwrite a result after its lease was taken.
        db.session.rollback()
        db.session.execute(update(NotificationOutbox).where(
            NotificationOutbox.id == outbox_id, NotificationOutbox.claim_token == token
        ).values(**values, claim_token=None, updated_at=datetime.utcnow()),
            execution_options={'synchronize_session': False})
        db.session.commit()
    return summary


def process_pending_notifications(limit=OUTBOX_RETRY_BATCH, exclude_ids=None):
    now = datetime.utcnow()
    db.session.execute(update(NotificationOutbox).where(
        NotificationOutbox.status == 'PROCESSING', NotificationOutbox.attempts >= OUTBOX_MAX_ATTEMPTS,
        NotificationOutbox.next_attempt_at <= now
    ).values(status='FAILED', claim_token=None, last_error='delivery lease expired after final attempt'),
        execution_options={'synchronize_session': False})
    db.session.commit()
    query = NotificationOutbox.query.filter(_eligible_delivery(datetime.utcnow()))
    excluded = [int(value) for value in (exclude_ids or []) if value is not None]
    if excluded:
        query = query.filter(NotificationOutbox.id.notin_(excluded))
    rows = (
        query
        .order_by(NotificationOutbox.created_at.asc(), NotificationOutbox.id.asc())
        .limit(max(1, min(int(limit), 100)))
        .all()
    )
    return process_outbox_ids([row.id for row in rows])


def dispatch_notification_outbox(outbox_ids):
    """Attempt committed outbox rows without blocking the public response."""
    ids = [int(value) for value in outbox_ids if value is not None]
    if not ids or not has_app_context():
        return
    flask_app = current_app._get_current_object()
    if getattr(flask_app, '_outbox_wakeup', None):
        flask_app._outbox_wakeup.set()
    elif not flask_app.config.get('TESTING') and _is_production() and os.getenv('OUTBOX_WORKER_ENABLED', 'true').lower() not in ('0', 'false', 'no'):
        # Registration starts one worker per process; do not create one thread
        # per incoming enquiry.
        start_outbox_worker(flask_app)
        flask_app._outbox_wakeup.set()


def start_outbox_worker(flask_app):
    with _worker_lock:
        if getattr(flask_app, '_outbox_wakeup', None):
            return
        wakeup = Event()
        flask_app._outbox_wakeup = wakeup
        def run():
            while True:
                wakeup.wait(30)
                wakeup.clear()
                try:
                    with flask_app.app_context():
                        process_pending_notifications()
                except Exception:
                    flask_app.logger.exception('Durable outbox worker failed; retrying on next interval')
        Thread(target=run, daemon=True, name='riburom-outbox').start()


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
    @flask_app.before_request
    def ensure_outbox_worker():
        # Keep app/build imports side-effect free. Schema migrations complete
        # before Gunicorn serves the first request.
        if not flask_app.config.get('TESTING') and _is_production() and os.getenv('OUTBOX_WORKER_ENABLED', 'true').lower() not in ('0', 'false', 'no'):
            start_outbox_worker(flask_app)
