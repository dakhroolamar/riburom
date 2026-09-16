"""Optimistic concurrency helpers for the JSON-backed public CMS configuration."""

import hashlib
import hmac


def public_config_token(settings):
    raw = (settings.public_config_json or '').encode('utf-8')
    return hashlib.sha256(raw).hexdigest()


def public_config_token_matches(settings, submitted_token):
    submitted = (submitted_token or '').strip()
    return bool(submitted) and hmac.compare_digest(
        submitted,
        public_config_token(settings),
    )
