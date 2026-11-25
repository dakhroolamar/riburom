"""Staging mail acceptance must fail closed outside the isolated Worker."""
from types import SimpleNamespace
import unittest

from deploy.cloudflare.staging_brevo_test import is_staging_brevo_test_allowed


class StagingBrevoPolicyTests(unittest.TestCase):
    def env(self, **overrides):
        defaults = dict(
            RIBUROM_MODE="application",
            RIBUROM_HOST="riburom-application-staging.dakhroo.workers.dev",
            RIBUROM_STAGING_ACCESS_REQUIRED="true",
            RIBUROM_READ_ONLY="false",
            OUTBOX_SCHEDULED="false",
            CLOUDINARY_STAGING_FOLDER="riburom-cloudflare-staging",
        )
        defaults.update(overrides)
        return SimpleNamespace(**defaults)

    def test_protected_staging_is_eligible_for_one_off_test(self):
        self.assertTrue(is_staging_brevo_test_allowed(self.env()))

    def test_production_mirror_fixture_and_scheduler_are_ineligible(self):
        scenarios = [
            dict(RIBUROM_HOST="riburomtours.com"),
            dict(RIBUROM_HOST="riburom-parallel-comparison.dakhroo.workers.dev"),
            dict(RIBUROM_MODE="fixture"),
            dict(RIBUROM_STAGING_ACCESS_REQUIRED="false"),
            dict(RIBUROM_READ_ONLY="true"),
            dict(OUTBOX_SCHEDULED="true"),
            dict(CLOUDINARY_STAGING_FOLDER="riburom"),
        ]
        for scenario in scenarios:
            with self.subTest(scenario=scenario):
                self.assertFalse(is_staging_brevo_test_allowed(self.env(**scenario)))


if __name__ == "__main__":
    unittest.main()
