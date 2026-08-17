import os
import unittest
from xml.etree import ElementTree

from tests.test_bootstrap import configure_isolated_sqlite


SEO_DB_PATH = configure_isolated_sqlite('seo_test')

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
            cls.package = Package.query.filter_by(slug='seo-test-experience').first()
            if cls.package is None:
                cls.package = Package(
                    title='SEO Test Experience',
                    slug='seo-test-experience',
                    description='A public Meghalaya experience used to validate SEO metadata.',
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

    def test_robots_txt(self):
        response = self.client.get('/robots.txt')
        body = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn('Allow: /', body)
        for path in ('/admin', '/admin/login', '/workspace', '/workspace/', '/api/'):
            self.assertIn(f'Disallow: {path}', body)
        self.assertIn('Sitemap: https://riburom.onrender.com/sitemap.xml', body)

    def test_sitemap_is_valid_and_public_only(self):
        response = self.client.get('/sitemap.xml')
        self.assertEqual(response.status_code, 200)
        root = ElementTree.fromstring(response.data)
        namespace = {'sm': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
        urls = [node.text for node in root.findall('sm:url/sm:loc', namespace)]
        self.assertIn('https://riburom.onrender.com/', urls)
        self.assertIn('https://riburom.onrender.com/about', urls)
        self.assertIn('https://riburom.onrender.com/all_tours', urls)
        self.assertIn('https://riburom.onrender.com/tours/seo-test-experience', urls)
        self.assertFalse(any('/admin' in url or '/workspace' in url or '/api/' in url for url in urls))

    def test_public_pages_have_canonical_and_social_metadata(self):
        for path in ('/', '/about', '/all_tours'):
            response = self.client.get(path)
            body = response.get_data(as_text=True)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(body.lower().count('<link rel="canonical"'), 1)
            self.assertIn('property="og:title"', body)
            self.assertIn('property="og:description"', body)
            self.assertIn('property="og:url"', body)
            self.assertIn('property="og:image"', body)
            self.assertIn('name="twitter:card"', body)
            self.assertIn('application/ld+json', body)

    def test_homepage_has_expected_seo_metadata(self):
        body = self.client.get('/').get_data(as_text=True)
        self.assertIn('<title>RI BUROM Tours &amp; Travels | Meghalaya Tours &amp; Experiences</title>', body)
        self.assertIn('name="description"', body)
        self.assertIn('Meghalaya-rooted tours and travel experiences', body)
        self.assertIn('https://riburom.onrender.com/', body)

    def test_tour_page_has_unique_metadata_and_canonical(self):
        body = self.client.get('/tours/seo-test-experience').get_data(as_text=True)
        self.assertEqual(body.lower().count('<title>'), 1)
        self.assertIn('<title>SEO Test Experience | RI BUROM Meghalaya Experiences</title>', body)
        self.assertIn('https://riburom.onrender.com/tours/seo-test-experience', body)
        self.assertIn('SEO Test Experience', body)
        self.assertIn('TouristTrip', body)

    def test_private_routes_are_not_in_sitemap(self):
        xml = self.client.get('/sitemap.xml').get_data(as_text=True)
        for path in ('/admin', '/admin/login', '/workspace', '/workspace/administration', '/workspace/developer', '/api/'):
            self.assertNotIn(f'https://riburom.onrender.com{path}', xml)


if __name__ == '__main__':
    unittest.main()
