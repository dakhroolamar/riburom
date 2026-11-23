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


def fixture_status(sql):
    sql.exec("CREATE TABLE IF NOT EXISTS database_fixture (id INTEGER PRIMARY KEY CHECK (id = 1))")
    result = outbox_status(sql)
    result["postgres_verified"] = bool(sql.exec("SELECT count(*) AS count FROM database_fixture").one().count)
    return result


def check_fixture_database(sql, connection):
    from sqlalchemy import create_engine, text
    from sqlalchemy.pool import NullPool
    from worker_runtime import hyperdrive_url

    if fixture_status(sql)["postgres_verified"]:
        return
    engine = create_engine(
        hyperdrive_url(connection), poolclass=NullPool, hide_parameters=True,
        connect_args={"ssl_context": False, "timeout": 5},
    )
    with engine.connect() as db_connection:
        if db_connection.execute(text("SELECT 1")).scalar_one() != 1:
            raise RuntimeError("Unexpected staging PostgreSQL readiness result")
    sql.exec("INSERT OR IGNORE INTO database_fixture (id) VALUES (1)")
    print("Isolated PostgreSQL readiness check passed")


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
