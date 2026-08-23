import io
import os
import unittest

from PIL import Image

from tests.test_bootstrap import configure_isolated_sqlite


class HeroAnimationVideoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db_path = configure_isolated_sqlite('hero_animation_video')
        import wsgi
        from app import app, db
        from models import SiteSettings, User

        cls.app = app
        cls.db = db
        cls.SiteSettings = SiteSettings
        cls.User = User
        cls.app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
        cls.context = cls.app.app_context()
        cls.context.push()
        db.create_all()
        cls.client = app.test_client()
        cls.owner = User.query.filter_by(role='owner').first()
        if cls.owner is None:
            raise RuntimeError('Test bootstrap did not create an Owner account')
        cls.created_media = []

    @classmethod
    def tearDownClass(cls):
        from storage import delete_media
        for value in getattr(cls, 'created_media', []):
            delete_media(value)
        cls.db.session.remove()
        cls.db.engine.dispose()
        cls.context.pop()
        try:
            os.remove(cls.db_path)
        except FileNotFoundError:
            pass

    def setUp(self):
        from storage import delete_media
        settings = self.db.session.get(self.SiteSettings, 1)
        for field in ('hero_animation_video', 'hero_logo', 'header_mark', 'header_wordmark'):
            old_value = getattr(settings, field)
            setattr(settings, field, None)
            if old_value:
                delete_media(old_value)
        self.db.session.commit()

        self.client = self.app.test_client()
        with self.client.session_transaction() as session:
            session['user_id'] = self.owner.id

    @staticmethod
    def _valid_mp4(seed=b'video'):
        return b'\x00\x00\x00\x18ftypisom' + seed + b'\x00' * 32

    @staticmethod
    def _valid_png():
        image = Image.new('RGBA', (32, 32), (20, 83, 45, 255))
        buffer = io.BytesIO()
        image.save(buffer, format='PNG')
        return buffer.getvalue()

    def test_hero_animation_video_is_deferred_for_pre_migration_bootstrap(self):
        property_ = self.SiteSettings.__mapper__.attrs.hero_animation_video
        self.assertTrue(property_.deferred)

        statement = self.db.session.query(self.SiteSettings).statement
        compiled = str(statement.compile(dialect=self.db.engine.dialect))
        self.assertNotIn('hero_animation_video', compiled)

    def test_cms_exposes_current_replace_and_remove_video_controls(self):
        response = self.client.get('/workspace/cms/media')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Current Hero Animation Video', response.data)
        self.assertIn(b'Replace Video', response.data)
        self.assertIn(b'hero_animation_video', response.data)
        self.assertNotIn(b'>Remove Video<', response.data)

        save_response = self.client.post(
            '/workspace/cms/save-hero-animation-video',
            data={'hero_animation_video': (io.BytesIO(self._valid_mp4()), 'hero.mp4', 'video/mp4')},
            content_type='multipart/form-data',
        )
        self.assertEqual(save_response.status_code, 302)
        value = self.db.session.get(self.SiteSettings, 1).hero_animation_video
        self.created_media.append(value)

        response = self.client.get('/workspace/cms/media')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Current Hero Animation Video', response.data)
        self.assertIn(b'Replace Video', response.data)
        self.assertIn(b'Remove Video', response.data)

    def test_homepage_renders_video_when_configured(self):
        settings = self.db.session.get(self.SiteSettings, 1)
        settings.hero_logo = 'logo.png'
        settings.hero_animation_video = 'uploads/hero.mp4'
        self.db.session.commit()

        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'rb-hero-video-stage', response.data)
        self.assertIn(b'data-rb-hero-animation-video', response.data)
        self.assertIn(b'autoplay', response.data)
        self.assertIn(b'muted', response.data)
        self.assertIn(b'playsinline', response.data)
        self.assertIn(b'preload="metadata"', response.data)
        self.assertIn(b'rb-hero-permanent-logo', response.data)

        motion_path = os.path.join(self.app.static_folder, 'js', 'ri-burom-motion.js')
        css_path = os.path.join(self.app.static_folder, 'css', 'ri-burom-motion.css')
        with open(motion_path, 'r', encoding='utf-8') as fh:
            motion = fh.read()
        with open(css_path, 'r', encoding='utf-8') as fh:
            styles = fh.read()
        self.assertIn('hero.appendChild(video)', motion)
        self.assertIn('video.muted = false', motion)
        self.assertIn('Enable sound', motion)
        self.assertIn("button.setAttribute('href', '/all_tours')", motion)
        self.assertIn('rb-hero-animation-video--background', styles)
        self.assertIn('object-fit:cover', styles)
        self.assertIn('.rb-hero-video-complete .rb-hero-animation-video--background', styles)
        self.assertIn('.rb-hero.rb-hero-video-playing .rb-hero-content', styles)
        self.assertIn('.rb-hero.rb-hero-video-complete .rb-hero-content', styles)

    def test_homepage_renders_permanent_logo_without_video(self):
        settings = self.db.session.get(self.SiteSettings, 1)
        settings.hero_logo = 'logo.png'
        settings.hero_animation_video = None
        self.db.session.commit()

        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'rb-hero-permanent-logo', response.data)
        self.assertNotIn(b'data-rb-hero-animation-video', response.data)

    def test_video_can_be_saved(self):
        response = self.client.post(
            '/workspace/cms/save-hero-animation-video',
            data={'hero_animation_video': (io.BytesIO(self._valid_mp4()), 'hero.mp4', 'video/mp4')},
            content_type='multipart/form-data',
        )
        self.assertEqual(response.status_code, 302)
        value = self.db.session.get(self.SiteSettings, 1).hero_animation_video
        self.assertTrue(value)
        self.created_media.append(value)
        self.assertTrue(value.endswith('.mp4'))

    def test_video_can_be_replaced_and_old_media_removed(self):
        first = self.client.post(
            '/workspace/cms/save-hero-animation-video',
            data={'hero_animation_video': (io.BytesIO(self._valid_mp4(b'one')), 'one.mp4', 'video/mp4')},
            content_type='multipart/form-data',
        )
        self.assertEqual(first.status_code, 302)
        old_value = self.db.session.get(self.SiteSettings, 1).hero_animation_video
        self.created_media.append(old_value)
        self.assertTrue(os.path.exists(os.path.join(self.app.root_path, 'static', old_value)))

        second = self.client.post(
            '/workspace/cms/save-hero-animation-video',
            data={'hero_animation_video': (io.BytesIO(self._valid_mp4(b'two')), 'two.mp4', 'video/mp4')},
            content_type='multipart/form-data',
        )
        self.assertEqual(second.status_code, 302)
        new_value = self.db.session.get(self.SiteSettings, 1).hero_animation_video
        self.created_media.append(new_value)
        self.assertNotEqual(old_value, new_value)
        self.assertFalse(os.path.exists(os.path.join(self.app.root_path, 'static', old_value)))
        self.assertTrue(os.path.exists(os.path.join(self.app.root_path, 'static', new_value)))

    def test_video_can_be_removed(self):
        self.client.post(
            '/workspace/cms/save-hero-animation-video',
            data={'hero_animation_video': (io.BytesIO(self._valid_mp4()), 'hero.mp4', 'video/mp4')},
            content_type='multipart/form-data',
        )
        value = self.db.session.get(self.SiteSettings, 1).hero_animation_video
        self.created_media.append(value)
        self.assertTrue(os.path.exists(os.path.join(self.app.root_path, 'static', value)))

        response = self.client.post(
            '/workspace/cms/save-hero-animation-video',
            data={'remove_hero_animation_video': '1'},
        )
        self.assertEqual(response.status_code, 302)
        self.assertIsNone(self.db.session.get(self.SiteSettings, 1).hero_animation_video)
        self.assertFalse(os.path.exists(os.path.join(self.app.root_path, 'static', value)))

    def test_unsupported_video_is_rejected(self):
        response = self.client.post(
            '/workspace/cms/save-hero-animation-video',
            data={'hero_animation_video': (io.BytesIO(b'not-video'), 'hero.mov', 'video/quicktime')},
            content_type='multipart/form-data',
        )
        self.assertEqual(response.status_code, 302)
        self.assertIsNone(self.db.session.get(self.SiteSettings, 1).hero_animation_video)

    def test_reduced_motion_is_handled_in_frontend_without_playback(self):
        motion_path = os.path.join(self.app.static_folder, 'js', 'ri-burom-motion.js')
        css_path = os.path.join(self.app.static_folder, 'css', 'ri-burom-motion.css')
        with open(motion_path, 'r', encoding='utf-8') as fh:
            motion = fh.read()
        with open(css_path, 'r', encoding='utf-8') as fh:
            styles = fh.read()

        self.assertIn("'(prefers-reduced-motion: reduce)'", motion)
        self.assertIn('if (reduceMotion)', motion)
        self.assertIn("stage.classList.add('is-fallback')", motion)
        self.assertIn('video.play()', motion)
        self.assertIn("video.addEventListener('ended'", motion)
        self.assertIn("video.addEventListener('error'", motion)
        self.assertIn('.rb-hero-animation-video--background{display:none !important}', styles)

    def test_old_logo_animation_machinery_is_removed(self):
        motion_path = os.path.join(self.app.static_folder, 'js', 'ri-burom-motion.js')
        css_path = os.path.join(self.app.static_folder, 'css', 'ri-burom-motion.css')
        with open(motion_path, 'r', encoding='utf-8') as fh:
            motion = fh.read()
        with open(css_path, 'r', encoding='utf-8') as fh:
            styles = fh.read()

        for obsolete in ('rbHeroLogo', 'assembleHeroLogo', 'createFragment', 'playFragment', 'rb-hero-logo-stage', 'rb-logo-fragment'):
            self.assertNotIn(obsolete, motion)
            self.assertNotIn(obsolete, styles)

    def test_existing_image_branding_still_works(self):
        response = self.client.post(
            '/update_branding',
            data={'hero_logo': (io.BytesIO(self._valid_png()), 'logo.png', 'image/png')},
            content_type='multipart/form-data',
        )
        self.assertEqual(response.status_code, 302)
        value = self.db.session.get(self.SiteSettings, 1).hero_logo
        self.assertTrue(value)
        self.created_media.append(value)
        self.assertTrue(value.endswith('.png'))


if __name__ == '__main__':
    unittest.main()
