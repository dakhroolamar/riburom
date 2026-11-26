"""Send one authorized synthetic notification without touching the live outbox."""

from hmac import compare_digest
import os
from time import time
from urllib.error import HTTPError

from outbox_handoff import PRODUCTION_CANDIDATE_HOST


PRODUCTION_BREVO_PATH = "/__candidate/brevo-delivery"
PROBE_ID = "production-brevo-2026-11-26"
EXPECTED_SENDER = "info@riburomtours.com"


def probe_allowed(env, request):
    if not (
        getattr(env, "RIBUROM_HOST", None) == PRODUCTION_CANDIDATE_HOST
        and getattr(env, "RIBUROM_MODE", None) == "application"
        and getattr(env, "RIBUROM_STAGING_ACCESS_REQUIRED", None) == "true"
        and getattr(env, "RIBUROM_READ_ONLY", None) != "true"
        and getattr(env, "OUTBOX_SCHEDULED", None) == "false"
        and getattr(env, "RIBUROM_LIVE_OUTBOX_APPROVED", None) == "false"
        and request.method == "POST"
    ):
        return False
    token, _, expiry = (getattr(env, "RIBUROM_BREVO_PROBE_AUTH", None) or "").partition(":")
    supplied = request.headers.get("X-Riburom-Brevo-Probe") or ""
    return (
        len(token) >= 32 and expiry.isascii() and expiry.isdecimal()
        and len(expiry) == 10 and time() < int(expiry)
        and compare_digest(token.encode(), supplied.encode())
    )


def run_probe(app, sql):
    from notifications import _brevo_missing_config, _brevo_send, _use_brevo_oauth

    recipient = os.environ.get("NOTIFICATION_EMAIL", "").strip()
    if (not _use_brevo_oauth() or _brevo_missing_config() or not recipient
            or os.environ.get("BREVO_SENDER_EMAIL", "").strip().casefold() != EXPECTED_SENDER):
        return {"status": "production_oauth_configuration_incomplete"}, 503

    sql.exec("CREATE TABLE IF NOT EXISTS acceptance_probes (id TEXT PRIMARY KEY, status TEXT NOT NULL)")
    claim = sql.exec("INSERT OR IGNORE INTO acceptance_probes (id, status) VALUES (?, 'attempted')", PROBE_ID)
    if not claim.rowsWritten:
        previous = sql.exec("SELECT status FROM acceptance_probes WHERE id = ?", PROBE_ID).one().status
        if previous == "accepted":
            return {"status": "already_accepted"}, 200
        return {"status": "previous_attempt_needs_reconciliation"}, 409

    try:
        with app.app_context():
            accepted = _brevo_send(
                "[RI BUROM] Cloudflare production delivery check",
                "One authorized synthetic test from the protected Cloudflare candidate. "
                "No customer or booking data is included. Reference: " + PROBE_ID,
                recipient,
            )
    except HTTPError as exc:
        # The Worker transport returns send failures as status codes. An HTTPError
        # here identifies a failed OAuth token exchange before message submission.
        return {"status": "oauth_rejected", "provider_http_status": int(exc.code)}, 502
    except Exception:
        return {"status": "delivery_outcome_unknown"}, 502
    if not accepted:
        return {"status": "delivery_not_accepted"}, 502
    sql.exec("UPDATE acceptance_probes SET status = 'accepted' WHERE id = ?", PROBE_ID)
    return {"status": "accepted", "oauth_scope": "transactional.email:write"}, 200
