"""Guard against two live RI BUROM notification consumers after migration."""
from types import SimpleNamespace
import unittest

from deploy.cloudflare.outbox_handoff import scheduled_outbox_allowed


class CloudflareOutboxHandoffTests(unittest.TestCase):
    def make_env(self, **changes):
        variables = dict(
            OUTBOX_SCHEDULED="true",
            RIBUROM_MODE="application",
            RIBUROM_HOST="riburomtours.com",
            RIBUROM_LIVE_OUTBOX_APPROVED="true",
            RIBUROM_READ_ONLY="false",
            RIBUROM_STAGING_ACCESS_REQUIRED="false",
        )
        variables.update(changes)
        return SimpleNamespace(**variables)

    def test_real_production_requires_explicit_owner_handoff(self):
        self.assertTrue(scheduled_outbox_allowed(self.make_env()))
        self.assertFalse(scheduled_outbox_allowed(
            self.make_env(RIBUROM_LIVE_OUTBOX_APPROVED="false")))
        self.assertFalse(scheduled_outbox_allowed(
            self.make_env(RIBUROM_LIVE_OUTBOX_APPROVED=None)))

    def test_staging_and_production_comparison_cannot_send_mail(self):
        for changes in [
            dict(RIBUROM_STAGING_ACCESS_REQUIRED="true"),
            dict(RIBUROM_READ_ONLY="true"),
            dict(RIBUROM_HOST="riburom-application-staging.dakhroo.workers.dev"),
            dict(RIBUROM_HOST="riburom-parallel-comparison.dakhroo.workers.dev"),
            dict(OUTBOX_SCHEDULED="false"),
            dict(RIBUROM_MODE="unknown"),
        ]:
            with self.subTest(changes=changes):
                self.assertFalse(scheduled_outbox_allowed(self.make_env(**changes)))

    def test_synthetic_compatibility_probe_keeps_its_nonproduction_schedule(self):
        self.assertTrue(scheduled_outbox_allowed(
            self.make_env(RIBUROM_MODE="fixture", RIBUROM_HOST=None)))
        self.assertFalse(scheduled_outbox_allowed(
            self.make_env(RIBUROM_MODE="fixture", OUTBOX_SCHEDULED="false")))


if __name__ == "__main__":
    unittest.main()
