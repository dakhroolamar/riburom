"""Production candidate configuration and entry-point checks using synthetic bindings."""
import asyncio
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from deploy.cloudflare import outbox_handoff


ROOT = Path(__file__).resolve().parents[1]
CLOUDFLARE = ROOT / "deploy" / "cloudflare"
HOST = "riburom-production.dakhroo.workers.dev"


class ProductionCandidateTests(unittest.TestCase):
    def test_profile_is_private_and_unscheduled(self):
        with TemporaryDirectory() as directory:
            env = {**os.environ, "RIBUROM_PRODUCTION_HYPERDRIVE_ID": "d" * 32,
                   "RIBUROM_STAGING_HYPERDRIVE_ID": "a" * 32, "RIBUROM_PARALLEL_HYPERDRIVE_ID": "b" * 32}
            command = [sys.executable, str(CLOUDFLARE / "build.py"), "--production-candidate",
                       "--output", directory]
            subprocess.run(command, env=env, check=True, capture_output=True)
            config = json.loads((Path(directory) / "wrangler.jsonc").read_text())
            self.assertEqual(config["name"], "riburom-production")
            self.assertEqual(config["vars"]["RIBUROM_HOST"], HOST)
            self.assertEqual(config["vars"]["RIBUROM_STAGING_ACCESS_REQUIRED"], "true")
            self.assertEqual(config["vars"]["PUBLIC_BASE_URL"], "https://riburomtours.com")
            self.assertEqual(config["hyperdrive"][0]["id"], "d" * 32)
            self.assertTrue(config["assets"]["run_worker_first"])
            self.assertFalse(config["preview_urls"])
            self.assertFalse(config.get("routes") or config.get("route"))
            self.assertEqual(config["triggers"]["crons"], [])
            self.assertFalse(outbox_handoff.scheduled_outbox_allowed(SimpleNamespace(**config["vars"])))
            for value in ("", "a" * 32, "b" * 32, "malformed"):
                with self.subTest(binding=value):
                    result = subprocess.run(command, env={**env, "RIBUROM_PRODUCTION_HYPERDRIVE_ID": value},
                                            capture_output=True, text=True)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn("Hyperdrive", result.stderr)

    def test_preview_rejects_submissions_and_unprotected_requests_before_flask(self):
        def response(body, *, status, headers=None):
            return SimpleNamespace(status=status)

        worker_api = SimpleNamespace(DurableObject=object, WorkerEntrypoint=object,
                                     Response=response, wsgi=None)
        spec = importlib.util.spec_from_file_location("candidate_test_worker", CLOUDFLARE / "worker.py")
        module = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {"workers": worker_api, "outbox_handoff": outbox_handoff}):
            spec.loader.exec_module(module)
        worker = module.Default()
        worker.env = SimpleNamespace(RIBUROM_MODE="application", RIBUROM_HOST=HOST,
                                     RIBUROM_STAGING_ACCESS_REQUIRED="true", RIBUROM_STAGING_ACCESS_TOKEN="demo")
        for method, path, status in (
            ("GET", "/workspace", 401), ("GET", "/static/logo.png", 401),
            ("POST", "/admin/login", 401), ("POST", "/contact", 405),
            ("POST", "/control-room/invoices", 405), ("POST", "/__staging/bootstrap", 404),
            ("POST", "/__staging/brevo-send", 404),
        ):
            with self.subTest(path=path):
                req = SimpleNamespace(method=method, url=f"https://{HOST}{path}", headers={})
                self.assertEqual(asyncio.run(worker.fetch(req)).status, status)
        worker.env.RIBUROM_STAGING_ACCESS_REQUIRED = "false"
        req = SimpleNamespace(method="GET", url=f"https://{HOST}/", headers={})
        self.assertEqual(asyncio.run(worker.fetch(req)).status, 404)
