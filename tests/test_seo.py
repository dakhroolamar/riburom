import json
import os
import re
import unittest
from xml.etree import ElementTree

from tests.test_bootstrap import configure_isolated_sqlite


SEO_DB_PATH = configure_isolated_sqlite("seo_test")

import wsgi
from app import app, db
from models import Package


class SeoFoundationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
        cls.db_path = SEO_DB_PATH
        cls.client = app.test_client()
        with app.app_context():
            db.create_all()
            cls.package = Package.query.filter_by(slug="seo-test-experience").first()
            if cls.package is None:
                cls.package = Package(
                    title="SEO Test Experience",
                    slug="seo-test-experience",
                    description="A public Meghalaya experience used to validate SEO metadata.",
                    location="Meghalaya",
                    category="Nature",
                    published=True,
                )
                db.session.add(cls.package)
                db.session.commit()

    @classmethod
    def tearDownClass(cls):
        with app.app_context():
            db.session.remove()
            db.engine.dispose()
        try:
            os.remove(cls.db_path)
        except FileNotFoundError:
            pass

    def _json_ld(self, body):
        match = re.search(
            r'<script type="application/ld\\+json">(.*?)</script>',
            body,
            flags=re.DOTALL,
        )
        self.assertIsNotNone(match)
        return json.loads(match.group(1))

    def test_robots_txt(self):
        response = self.client.get("/robots.txt")
        body = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn("Allow: /", body)
        for path in ("/admin", "/workspace", "/api/"):
            self.assertIn(f"Disallow: {path}", body)
        self.assertIn("Sitemap: https://riburomtours.com/sitemap.xml", body)

    def test_sitemap_is_valid_and_public_only(self):
        response = self.client.get("/sitemap.xml")
        self.assertEqual(response.status_code, 200)
        root = ElementTree.fromstring(response.data)
        namespace = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        urls = [node.text for node in root.findall("sm:url/sm:loc", namespace)]
        self.assertIn("https://riburomtours.com/", urls)
        self.assertIn("https://riburomtours.com/about", urls)
        self.assertIn("https://riburomtours.com/all_tours", urls)
        self.assertIn("https://riburomtours.com/marketplace", urls)
        self.assertIn("https://riburomtours.com/tours/seo-test-experience", urls)
        self.assertFalse(
            any("/admin" in url or "/workspace" in url or "/api/" in url for url in urls)
        )

        tour_node = next(
            node
            for node in root.findall("sm:url", namespace)
            if node.find("sm:loc", namespace).text.endswith("/tours/seo-test-experience")
        )
        self.assertIsNotNone(tour_node.find("sm:lastmod", namespace))

    def test_public_pages_have_canonical_social_and_index_metadata(self):
        for path in ("/", "/about", "/all_tours", "/marketplace"):
            response = self.client.get(path)
            body = response.get_data(as_text=True)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(body.lower().count('<link rel="canonical"'), 1)
            self.assertIn('name="robots" content="index,follow', body)
            self.assertIn('property="og:site_name"', body)
            self.assertIn('property="og:title"', body)
            self.assertIn('property="og:description"', body)
            self.assertIn('property="og:url"', body)
            self.assertIn('property="og:image"', body)
            self.assertIn('name="twitter:card"', body)
            self.assertIn("application/ld+json", body)
            self.assertEqual(response.headers.get("X-Robots-Tag"), "index, follow")

    def test_homepage_has_expected_seo_metadata_and_schema_graph(self):
        body = self.client.get("/").get_data(as_text=True)
        self.assertIn(
            "<title>Ri Burom Tours &amp; Travels | Meghalaya Experiences</title>",
            body,
        )
        self.assertIn('name="description"', body)
        self.assertIn("Meghalaya-rooted journeys", body)
        self.assertIn("https://riburomtours.com/", body)

        data = self._json_ld(body)
        self.assertEqual(data["@context"], "https://schema.org")
        graph = data["@graph"]
        types = [node.get("@type") for node in graph]
        self.assertTrue(
            any(
                node.get("@id") == "https://riburomtours.com/#organization"
                and "TravelAgency" in node.get("@type", [])
                for node in graph
            )
        )
        self.assertIn("WebSite", types)
        self.assertIn("WebPage", types)

    def test_tours_collection_exposes_item_list_schema(self):
        body = self.client.get("/all_tours").get_data(as_text=True)
        data = self._json_ld(body)
        item_lists = [
            node for node in data["@graph"] if node.get("@type") == "ItemList"
        ]
        self.assertTrue(item_lists)
        serialized = json.dumps(item_lists)
        self.assertIn("SEO Test Experience", serialized)
        self.assertIn(
            "https://riburomtours.com/tours/seo-test-experience",
            serialized,
        )

    def test_tour_page_has_unique_metadata_and_tour_schema(self):
        body = self.client.get("/tours/seo-test-experience").get_data(as_text=True)
        self.assertEqual(body.lower().count("<title>"), 1)
        self.assertIn(
            "<title>SEO Test Experience | RI BUROM Meghalaya Experiences</title>",
            body,
        )
        self.assertIn(
            "https://riburomtours.com/tours/seo-test-experience",
            body,
        )
        data = self._json_ld(body)
        tourist_trips = [
            node for node in data["@graph"] if node.get("@type") == "TouristTrip"
        ]
        self.assertEqual(len(tourist_trips), 1)
        self.assertEqual(tourist_trips[0]["name"], "SEO Test Experience")
        self.assertEqual(
            tourist_trips[0]["itinerary"]["name"],
            "Meghalaya",
        )

    def test_llms_txt_lists_canonical_public_resources_only(self):
        response = self.client.get("/llms.txt")
        body = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn("# RI BUROM Tours & Travels", body)
        self.assertIn("https://riburomtours.com/sitemap.xml", body)
        self.assertIn(
            "https://riburomtours.com/tours/seo-test-experience",
            body,
        )
        self.assertNotIn("https://riburomtours.com/workspace", body)
        self.assertNotIn("https://riburomtours.com/admin", body)

    def test_private_and_error_routes_emit_noindex_header(self):
        private_response = self.client.get("/admin/login")
        self.assertEqual(
            private_response.headers.get("X-Robots-Tag"),
            "noindex, nofollow",
        )

        error_response = self.client.get("/this-page-does-not-exist")
        self.assertEqual(error_response.status_code, 404)
        self.assertEqual(
            error_response.headers.get("X-Robots-Tag"),
            "noindex, nofollow",
        )

    def test_private_routes_are_not_in_sitemap(self):
        xml = self.client.get("/sitemap.xml").get_data(as_text=True)
        for path in (
            "/admin",
            "/admin/login",
            "/workspace",
            "/workspace/administration",
            "/workspace/developer",
            "/api/",
        ):
            self.assertNotIn(f"https://riburomtours.com{path}", xml)


if __name__ == "__main__":
    unittest.main()
