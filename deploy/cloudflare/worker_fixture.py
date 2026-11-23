"""Synthetic preview data and notification transport for staging."""

from datetime import datetime
from unittest.mock import patch


def setup_fixture(app):
    from models import db, seed_defaults

    with app.app_context():
        db.create_all()
        seed_defaults()

    @app.after_request
    def exclude_preview_from_index(response):
        response.headers["X-Robots-Tag"] = "noindex, nofollow"
        return response


def outbox_status(sql):
    sql.exec(
        "CREATE TABLE IF NOT EXISTS outbox_fixture "
        "(id INTEGER PRIMARY KEY, attempts INTEGER NOT NULL, status TEXT NOT NULL, retry_at TEXT)"
    )
    rows = sql.exec("SELECT attempts, status, retry_at FROM outbox_fixture WHERE id = 1").toArray()
    if not len(rows):
        return {"attempts": 0, "status": "PENDING"}
    row = rows[0]
    return {"attempts": row.attempts, "status": row.status, "retry_at": row.retry_at}


def process_fixture_outbox(sql):
    from models import db, NotificationOutbox
    from notifications import process_pending_notifications

    saved = outbox_status(sql)
    if saved["status"] == "SENT":
        return {"sent": 0, "failed": 0, "skipped": 1}
    row = NotificationOutbox.query.filter_by(source_type="cloudflare_fixture").first()
    if row is None:
        row = NotificationOutbox(
            source_type="cloudflare_fixture", source_id="1", channel="email",
            recipient="fixture@example.invalid", body="Synthetic email retry",
        )
        db.session.add(row)
    row.attempts = saved["attempts"]
    row.status = saved["status"]
    row.next_attempt_at = datetime.fromisoformat(saved["retry_at"]) if saved.get("retry_at") else None
    db.session.commit()
    with patch("notifications._brevo_missing_config", return_value=[]), patch(
        "notifications._brevo_send", return_value=saved["attempts"] > 0
    ):
        result = process_pending_notifications(limit=1)
    sql.exec(
        "INSERT OR REPLACE INTO outbox_fixture (id, attempts, status, retry_at) VALUES (1, ?, ?, ?)",
        row.attempts, row.status, row.next_attempt_at.isoformat() if row.next_attempt_at else None,
    )
    return result
