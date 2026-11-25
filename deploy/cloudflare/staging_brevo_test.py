"""Narrow, one-off Brevo acceptance probe for isolated RI BUROM staging.

Only the Basic-protected application staging Worker can invoke this handler.
Never processes customer mail or unrelated outbox rows. All responses are
sanitized; neither credentials nor the approved test recipient is returned.
"""
import os
from urllib.error import HTTPError


STAGING_HOST = "riburom-application-staging.dakhroo.workers.dev"
SYNTHETIC_SOURCE_ID = "cloudflare-brevo-auth-smoke-2026-11-25"


def is_staging_brevo_test_allowed(env):
    return (
        getattr(env, "RIBUROM_MODE", None) == "application"
        and getattr(env, "RIBUROM_HOST", None) == STAGING_HOST
        and getattr(env, "RIBUROM_STAGING_ACCESS_REQUIRED", None) == "true"
        and getattr(env, "RIBUROM_READ_ONLY", None) != "true"
        and getattr(env, "OUTBOX_SCHEDULED", None) == "false"
        and getattr(env, "CLOUDINARY_STAGING_FOLDER", None) == "riburom-cloudflare-staging"
    )


def run_staging_brevo_test(app, env, *, deliver=False):
    if not is_staging_brevo_test_allowed(env):
        return {"status": "unavailable"}, 404

    from models import NotificationOutbox, Package, User, db
    from notifications import (
        _brevo_authorization, _brevo_missing_config,
        _use_brevo_oauth, process_outbox_ids,
    )

    with app.app_context():
        # Fail closed if the bound database is missing its synthetic owner/tour.
        # No customer data is ever needed or returned.
        owner = User.query.filter_by(username="staging-owner", role="owner").first()
        demo = Package.query.filter_by(slug="staging-demo-jowai-heritage").first()
        if not (owner and demo and (demo.description or "").startswith("SYNTHETIC TEST TOUR")):
            return {"status": "staging_database_guard_failed"}, 409

        missing = _brevo_missing_config()
        if not os.environ.get("NOTIFICATION_EMAIL", "").strip():
            missing.append("NOTIFICATION_EMAIL")
        if missing:
            return {"status": "missing_configuration", "names": missing}, 503
        if not _use_brevo_oauth():
            return {"status": "oauth_credentials_required"}, 503

        try:
            token_headers = _brevo_authorization()
            if not (token_headers.get("Authorization") or "").startswith("Bearer "):
                return {"status": "oauth_token_not_received"}, 502
        except HTTPError as exc:
            return {"status": "oauth_rejected", "provider_http_status": int(exc.code)}, 502
        except Exception as exc:
            return {"status": "oauth_transport_error", "exception": type(exc).__name__}, 502

        if not deliver:
            return {"status": "oauth_authorized", "scope_requested": "transactional.email:write"}, 200

        # Exactly one synthetic record, sent only to the owner-configured
        # staging NOTIFICATION_EMAIL. No user-provided recipient or content.
        row = NotificationOutbox.query.filter_by(
            source_type="staging_brevo_smoke",
            source_id=SYNTHETIC_SOURCE_ID,
            event_type="staging_email_test",
            channel="email",
        ).first()
        if not row:
            row = NotificationOutbox(
                source_type="staging_brevo_smoke",
                source_id=SYNTHETIC_SOURCE_ID,
                event_type="staging_email_test",
                channel="email",
                recipient=os.environ["NOTIFICATION_EMAIL"].strip(),
                subject="[RI BUROM STAGING] Brevo delivery acceptance test",
                body=(
                    "This is one synthetic test notification from the isolated "
                    "RI BUROM Cloudflare staging website. No customer enquiry "
                    "or live booking is involved. Production remains on Render."
                ),
                status="PENDING",
            )
            db.session.add(row)
            db.session.commit()
        elif row.status == "SENT":
            return {"status": "already_sent", "attempts": row.attempts}, 200

        summary = process_outbox_ids([row.id])
        db.session.expire_all()
        result = db.session.get(NotificationOutbox, row.id)
        outcome = result.status.lower()
        # Explicitly do not expose recipients, payloads, provider tokens or raw errors.
        return {
            "status": outcome,
            "attempts": result.attempts,
            "sent": summary["sent"],
            "failed": summary["failed"],
            "skipped": summary["skipped"],
            "failure_category": result.last_error if result.last_error in (
                "delivery not confirmed", "missing Brevo configuration",
                "delivery disabled by owner",
            ) else None,
        }, 200 if outcome == "sent" else 502
