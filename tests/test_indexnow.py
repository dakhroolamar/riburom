import json
import os
import unittest
from pathlib import Path
from unittest.mock import patch

from flask import Flask

import indexnow


TEST_KEY = "fd53e26ca8264926889f4cd2237f5b53"


class _FakeResponse:
    def __init__(self, status=200, body=b""):
        self.status = status
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def getcode(self):
        return self.status

    def read(self):
        return self.body


class IndexNowTests(unittest.TestCase):
    def test_key_file_is_disabled_without_configuration(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("INDEXNOW_KEY", None)
            app = Flask("indexnow-disabled")
            indexnow.register_indexnow(app)
            client = app.test_client()
            self.assertEqual(client.get(f"/{TEST_KEY}.txt").status_code, 404)

    def test_key_file_is_served_at_root_when_configured(self):
        with patch.dict(os.environ, {"INDEXNOW_KEY": TEST_KEY}, clear=False):
            app = Flask("indexnow-enabled")
            indexnow.register_indexnow(app)
            response = app.test_client().get(f"/{TEST_KEY}.txt")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.get_data(as_text=True).strip(), TEST_KEY)
            self.assertTrue(response.content_type.startswith("text/plain"))
            self.assertEqual(
                response.headers.get("X-Robots-Tag"),
                "noindex, nofollow",
            )

    def test_invalid_key_is_rejected(self):
        with patch.dict(os.environ, {"INDEXNOW_KEY": "bad key!"}, clear=False):
            with self.assertRaises(ValueError):
                indexnow.get_indexnow_key()

    def test_payload_uses_canonical_host_and_root_key_location(self):
        with patch.dict(os.environ, {"INDEXNOW_KEY": TEST_KEY}, clear=False):
            payload = indexnow.build_indexnow_payload([
                "https://riburomtours.com/",
                "https://riburomtours.com/all_tours",
                "https://riburomtours.com/all_tours",
            ])
        self.assertEqual(payload["host"], "riburomtours.com")
        self.assertEqual(payload["key"], TEST_KEY)
        self.assertEqual(
            payload["keyLocation"],
            f"https://riburomtours.com/{TEST_KEY}.txt",
        )
        self.assertEqual(
            payload["urlList"],
            [
                "https://riburomtours.com/",
                "https://riburomtours.com/all_tours",
            ],
        )

    def test_payload_rejects_noncanonical_host(self):
        with patch.dict(os.environ, {"INDEXNOW_KEY": TEST_KEY}, clear=False):
            with self.assertRaises(ValueError):
                indexnow.build_indexnow_payload([
                    "https://riburom.onrender.com/",
                ])

    def test_best_effort_notification_builds_canonical_urls(self):
        captured = {}

        def fake_submit(urls, timeout):
            captured["urls"] = urls
            captured["timeout"] = timeout
            return {"ok": True, "status": 200, "submitted": len(urls)}

        with patch.dict(os.environ, {"INDEXNOW_KEY": TEST_KEY}, clear=False):
            with patch("indexnow.submit_indexnow_urls", side_effect=fake_submit):
                result = indexnow.notify_indexnow_paths(
                    ["/", "/all_tours", "marketplace"],
                    timeout=2,
                )

        self.assertTrue(result["ok"])
        self.assertEqual(captured["timeout"], 2)
        self.assertEqual(
            captured["urls"],
            [
                "https://riburomtours.com/",
                "https://riburomtours.com/all_tours",
                "https://riburomtours.com/marketplace",
            ],
        )

    def test_best_effort_notification_never_breaks_publish_flow(self):
        with patch.dict(os.environ, {"INDEXNOW_KEY": TEST_KEY}, clear=False):
            with patch(
                "indexnow.submit_indexnow_urls",
                side_effect=RuntimeError("synthetic transport failure"),
            ):
                result = indexnow.notify_indexnow_paths(["/"])

        self.assertFalse(result["ok"])
        self.assertIsNone(result["status"])

    def test_cms_change_mapping_for_static_pages(self):
        self.assertEqual(indexnow.public_paths_for_cms_change("home"), ["/"])
        self.assertEqual(indexnow.public_paths_for_cms_change("hero"), ["/"])
        self.assertEqual(indexnow.public_paths_for_cms_change("about"), ["/about"])
        self.assertEqual(indexnow.public_paths_for_cms_change("about_team"), ["/about"])
        self.assertEqual(indexnow.public_paths_for_cms_change("tours"), ["/all_tours"])

    def test_disabled_public_site_submit_skips_database_lookup(self):
        with patch("indexnow.get_indexnow_key", return_value=None):
            with patch("indexnow.current_public_paths") as current_paths:
                result = indexnow.notify_indexnow_public_site()
        self.assertTrue(result["skipped"])
        current_paths.assert_not_called()

    def test_cms_edit_routes_are_wired_to_indexnow(self):
        root = Path(__file__).resolve().parents[1]
        app_source = (root / "app.py").read_text(encoding="utf-8")
        pages_source = (root / "cms_pages.py").read_text(encoding="utf-8")
        routes_source = (root / "cms_routes.py").read_text(encoding="utf-8")
        backgrounds_source = (root / "cms_backgrounds.py").read_text(encoding="utf-8")

        self.assertIn("notify_indexnow_public_site()", app_source)
        self.assertIn("notify_indexnow_cms_change('about')", app_source)
        self.assertIn("notify_indexnow_cms_change('home')", app_source)
        self.assertIn("notify_indexnow_cms_change(section)", pages_source)
        self.assertIn("notify_indexnow_cms_change(key)", pages_source)
        self.assertIn("notify_indexnow_cms_change(section_key)", backgrounds_source)
        self.assertIn("notify_indexnow_cms_change(gallery_key)", backgrounds_source)
        self.assertIn("notify_indexnow_public_site()", routes_source)
        self.assertIn("notify_indexnow_cms_change('home')", routes_source)

    def test_one_time_bootstrap_workflow_submits_live_sitemap(self):
        root = Path(__file__).resolve().parents[1]
        workflow = (root / ".github" / "workflows" / "indexnow-bootstrap.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn("[indexnow-bootstrap]", workflow)
        self.assertIn("https://riburomtours.com/sitemap.xml", workflow)
        self.assertIn("https://api.indexnow.org/indexnow", workflow)

    def test_publish_routes_are_wired_to_indexnow(self):
        root = Path(__file__).resolve().parents[1]
        app_source = (root / "app.py").read_text(encoding="utf-8")
        marketplace_source = (root / "marketplace_admin.py").read_text(encoding="utf-8")

        self.assertIn("from indexnow import notify_indexnow_paths", app_source)
        self.assertIn("f'/tours/{pkg.slug}'", app_source)
        self.assertIn("f'/tours/{slug}'", app_source)
        self.assertIn("from indexnow import notify_indexnow_paths", marketplace_source)
        self.assertIn("def _provider_is_public(provider):", marketplace_source)
        self.assertIn("def _service_is_public(service):", marketplace_source)
        self.assertIn("notify_indexnow_paths(_provider_paths", marketplace_source)

    def test_submit_posts_indexnow_json_payload(self):
        captured = {}

        def fake_urlopen(request, timeout):
            captured["url"] = request.full_url
            captured["timeout"] = timeout
            captured["content_type"] = request.headers.get("Content-type")
            captured["payload"] = json.loads(request.data.decode("utf-8"))
            return _FakeResponse(status=200)

        with patch.dict(os.environ, {"INDEXNOW_KEY": TEST_KEY}, clear=False):
            with patch("indexnow.urlopen", side_effect=fake_urlopen):
                result = indexnow.submit_indexnow_urls([
                    "https://riburomtours.com/",
                    "https://riburomtours.com/marketplace",
                ])

        self.assertTrue(result["ok"])
        self.assertEqual(result["status"], 200)
        self.assertEqual(result["submitted"], 2)
        self.assertEqual(captured["url"], "https://api.indexnow.org/indexnow")
        self.assertEqual(captured["content_type"], "application/json; charset=utf-8")
        self.assertEqual(captured["payload"]["host"], "riburomtours.com")
        self.assertEqual(captured["payload"]["key"], TEST_KEY)
        self.assertEqual(len(captured["payload"]["urlList"]), 2)


if __name__ == "__main__":
    unittest.main()
