"""Production candidate configuration and entry-point checks using synthetic bindings."""
import asyncio
from base64 import b64encode
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch

from deploy.cloudflare import outbox_handoff


ROOT = Path(__file__).resolve().parents[1]
CLOUDFLARE = ROOT / "deploy" / "cloudflare"
HOST = "riburom-production.dakhroo.workers.dev"


def load_worker_module(name):
    spec = importlib.util.spec_from_file_location(name, CLOUDFLARE / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ProductionCandidateTests(unittest.TestCase):
    def test_live_profile_is_public_only_on_custom_domains_and_unscheduled(self):
        with TemporaryDirectory() as directory:
            env = {**os.environ, "RIBUROM_PRODUCTION_HYPERDRIVE_ID": "d" * 32,
                   "RIBUROM_STAGING_HYPERDRIVE_ID": "a" * 32, "RIBUROM_PARALLEL_HYPERDRIVE_ID": "b" * 32}
            subprocess.run([sys.executable, str(CLOUDFLARE / "build.py"), "--production-live",
                            "--output", directory], env=env, check=True, capture_output=True)
            config = json.loads((Path(directory) / "wrangler.jsonc").read_text())
            self.assertEqual(config["name"], "riburom-production")
            self.assertFalse(config["workers_dev"])
            self.assertFalse(config["preview_urls"])
            self.assertEqual(config["routes"], [
                {"pattern": "riburomtours.com", "custom_domain": True},
                {"pattern": "www.riburomtours.com", "custom_domain": True},
            ])
            self.assertEqual(config["vars"]["RIBUROM_HOST"], "riburomtours.com")
            self.assertEqual(config["vars"]["RIBUROM_STAGING_ACCESS_REQUIRED"], "false")
            self.assertEqual(config["vars"]["RIBUROM_READ_ONLY"], "false")
            self.assertEqual(config["hyperdrive"][0]["id"], "d" * 32)
            self.assertEqual(config["triggers"]["crons"], [])
            self.assertFalse(outbox_handoff.scheduled_outbox_allowed(SimpleNamespace(**config["vars"])))

    def test_approved_live_outbox_preserves_domains_schedule_and_observability(self):
        with TemporaryDirectory() as directory:
            env = {**os.environ, "RIBUROM_PRODUCTION_HYPERDRIVE_ID": "d" * 32,
                   "RIBUROM_STAGING_HYPERDRIVE_ID": "a" * 32, "RIBUROM_PARALLEL_HYPERDRIVE_ID": "b" * 32}
            command = [sys.executable, str(CLOUDFLARE / "build.py")]
            subprocess.run(command + ["--production-live", "--enable-live-outbox", "--output", directory],
                           env=env, check=True, capture_output=True)
            config = json.loads((Path(directory) / "wrangler.jsonc").read_text())
            self.assertEqual(config["triggers"]["crons"], ["*/5 * * * *"])
            self.assertTrue(outbox_handoff.scheduled_outbox_allowed(SimpleNamespace(**config["vars"])))
            self.assertEqual(config["routes"], [
                {"pattern": "riburomtours.com", "custom_domain": True},
                {"pattern": "www.riburomtours.com", "custom_domain": True},
            ])
            self.assertFalse(config["workers_dev"])
            self.assertFalse(config["preview_urls"])
            self.assertTrue(config["keep_vars"])
            self.assertTrue(config["observability"]["logs"]["enabled"])
            for profile in ("--production-candidate", "--application-staging", "--parallel-comparison"):
                with self.subTest(profile=profile):
                    result = subprocess.run(command + [profile, "--enable-live-outbox"],
                                            env=env, capture_output=True, text=True)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn("requires --production-live", result.stderr)

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
            return SimpleNamespace(status=status, headers=headers)
        response.json = response

        worker_api = SimpleNamespace(DurableObject=object, WorkerEntrypoint=object,
                                     Response=response, wsgi=None)
        with patch.dict(sys.modules, {"workers": worker_api, "outbox_handoff": outbox_handoff}):
            probe = load_worker_module("production_brevo_probe")
            with patch.dict(sys.modules, {"production_brevo_probe": probe}):
                module = load_worker_module("worker")
        worker = module.Default()
        worker.env = SimpleNamespace(RIBUROM_MODE="application", RIBUROM_HOST=HOST,
                                     RIBUROM_STAGING_ACCESS_REQUIRED="true", RIBUROM_STAGING_ACCESS_TOKEN="demo")
        for method, path, status in (
            ("GET", "/workspace", 401), ("GET", "/static/logo.png", 401),
            ("POST", "/admin/login", 401), ("POST", "/contact", 405),
            ("POST", "/control-room/invoices", 405), ("POST", "/__staging/bootstrap", 404),
            ("POST", "/__staging/brevo-send", 404),
            ("POST", probe.PRODUCTION_BREVO_PATH, 401),
        ):
            with self.subTest(path=path):
                req = SimpleNamespace(method=method, url=f"https://{HOST}{path}", headers={})
                self.assertEqual(asyncio.run(worker.fetch(req)).status, status)
        basic = "Basic " + b64encode(b"rehearsal:demo").decode()
        request = SimpleNamespace(method="POST", url=f"https://{HOST}{probe.PRODUCTION_BREVO_PATH}",
                                  headers={"Authorization": basic})
        self.assertEqual(asyncio.run(worker.fetch(request)).status, 404)
        worker.env.OUTBOX_SCHEDULED = worker.env.RIBUROM_LIVE_OUTBOX_APPROVED = "false"
        token = "a" * 32
        worker.env.RIBUROM_BREVO_PROBE_AUTH = token + ":1795600001"
        fetch = AsyncMock(return_value=SimpleNamespace(status=200))
        with patch.object(probe, "time", return_value=1795600000), patch.object(
            module, "flask_stub", return_value=SimpleNamespace(fetch=fetch),
        ):
            self.assertEqual(asyncio.run(worker.fetch(request)).status, 404)
            fetch.assert_not_awaited()
            request.headers["X-Riburom-Brevo-Probe"] = token
            self.assertEqual(asyncio.run(worker.fetch(request)).status, 200)
            fetch.assert_awaited_once_with(request)
        worker.env.RIBUROM_STAGING_ACCESS_REQUIRED = "false"
        req = SimpleNamespace(method="GET", url=f"https://{HOST}/", headers={})
        self.assertEqual(asyncio.run(worker.fetch(req)).status, 404)

        worker.env.RIBUROM_HOST = "riburomtours.com"
        for url in ("http://riburomtours.com/all_tours?q=first%20trip",
                    "https://www.riburomtours.com/all_tours?q=first%20trip"):
            req = SimpleNamespace(method="GET", url=url, headers={})
            actual = asyncio.run(worker.fetch(req))
            self.assertEqual(actual.status, 301)
            self.assertEqual(actual.headers["Location"], "https://riburomtours.com/all_tours?q=first%20trip")
        for path in ("/__staging/bootstrap", "/__comparison/readiness", probe.PRODUCTION_BREVO_PATH):
            req = SimpleNamespace(method="POST", url=f"https://riburomtours.com{path}", headers={})
            self.assertEqual(asyncio.run(worker.fetch(req)).status, 404)
        req = SimpleNamespace(method="POST", url="https://riburomtours.com/contact", headers={})
        with patch.object(module, "cache_public_or_forward", AsyncMock(return_value=SimpleNamespace(status=200))) as forward:
            self.assertEqual(asyncio.run(worker.fetch(req)).status, 200)
            forward.assert_awaited_once_with(worker.env, req, "/contact")

    def test_production_brevo_probe_requires_current_token_and_disabled_outbox(self):
        with patch.dict(sys.modules, {"outbox_handoff": outbox_handoff}):
            probe = load_worker_module("production_brevo_probe")
        token = "a" * 32
        request = SimpleNamespace(method="POST", headers={"X-Riburom-Brevo-Probe": token})
        settings = dict(RIBUROM_MODE="application", RIBUROM_HOST=HOST,
                        RIBUROM_STAGING_ACCESS_REQUIRED="true", OUTBOX_SCHEDULED="false",
                        RIBUROM_LIVE_OUTBOX_APPROVED="false", RIBUROM_BREVO_PROBE_AUTH=token + ":1795600001")
        with patch.object(probe, "time", return_value=1795600000):
            self.assertIsNone(probe.probe_denial(SimpleNamespace(**settings), request))
            for name, bad in (("RIBUROM_HOST", "riburomtours.com"), ("OUTBOX_SCHEDULED", "true"),
                              ("RIBUROM_LIVE_OUTBOX_APPROVED", "true"),
                              ("RIBUROM_STAGING_ACCESS_REQUIRED", "false"),
                              ("RIBUROM_BREVO_PROBE_AUTH", token + ":1795600000")):
                with self.subTest(name=name):
                    self.assertIsNotNone(probe.probe_denial(SimpleNamespace(**{**settings, name: bad}), request))
