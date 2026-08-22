import os
import unittest

from tests.test_bootstrap import configure_isolated_sqlite


class PublicMotionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db_path = configure_isolated_sqlite('public_motion')

        import wsgi
        from app import app, db

        cls.app = app
        cls.db = db
        cls.app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
        cls.context = cls.app.app_context()
        cls.context.push()
        db.create_all()
        cls.client = app.test_client()

    @classmethod
    def tearDownClass(cls):
        cls.db.session.remove()
        cls.db.engine.dispose()
        cls.context.pop()
        try:
            os.remove(cls.db_path)
        except FileNotFoundError:
            pass

    def test_public_pages_include_loading_and_motion_layer(self):
        for path in ('/', '/all_tours', '/about', '/marketplace'):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200)
                self.assertIn(b'rb-public-site', response.data)
                self.assertIn(b'ri-burom-motion.js?v=6', response.data)
                self.assertIn(b'prefers-reduced-motion', response.data)

    def test_home_hero_uses_persistent_logo_stage_and_fragment_enhancement(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'rb-home-hero', response.data)
        self.assertIn(b'rb-hero-logo-stage', response.data)
        self.assertIn(b'id="rbHeroLogo"', response.data)
        self.assertIn(b'data-fallback-src', response.data)

        motion_js_path = self.app.static_folder + '/js/ri-burom-motion.js'
        with open(motion_js_path, 'r', encoding='utf-8') as motion_js:
            motion_script = motion_js.read()

        motion_css_path = self.app.static_folder + '/css/ri-burom-motion.css'
        with open(motion_css_path, 'r', encoding='utf-8') as motion_css:
            motion_styles = motion_css.read()

        self.assertIn('assembleHeroLogo', motion_script)
        self.assertIn('resolveHeroLogo', motion_script)
        self.assertIn('rb-hero-logo-fragment-layer', motion_script)
        self.assertIn('rb-hero-logo-stage', motion_styles)
        self.assertIn('is-assembling', motion_styles)
        self.assertNotIn('replaceWith(wrapper)', motion_script)
        self.assertIn(b'rb-hero-logo-stage', response.data)


if __name__ == '__main__':
    unittest.main()
