"""Fail-closed notification scheduler policy for Cloudflare Workers.

Fixture-mode probes retain their synthetic schedule. A production consumer
requires an explicit owner-approved handoff, correct host, and no staging or
read-only protection. Never use this policy to start production mail during
parallel Render/Cloudflare comparisons.
"""


def scheduled_outbox_allowed(env):
    def setting(name):
        return getattr(env, name, None)

    if setting("OUTBOX_SCHEDULED") != "true":
        return False

    if setting("RIBUROM_MODE") == "fixture":
        # Only test state, no real Brevo or production database.
        return True

    return (
        setting("RIBUROM_MODE") == "application"
        and setting("RIBUROM_HOST") == "riburomtours.com"
        and setting("RIBUROM_LIVE_OUTBOX_APPROVED") == "true"
        and setting("RIBUROM_READ_ONLY") != "true"
        and setting("RIBUROM_STAGING_ACCESS_REQUIRED") != "true"
    )
