import io
import os
import unittest
from unittest.mock import patch
from PIL import Image
from tests.test_bootstrap import configure_isolated_sqlite


class CmsPagesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.path = configure_isolated_sqlite('cms_pages')
        import wsgi
        from app import app, db, run_deploy_bootstrap
        from models import User
        cls.app, cls.db = app, db
        app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
        cls.context = app.app_context(); cls.context.push()
        run_deploy_bootstrap()
        cls.owner = User.query.filter_by(role='owner').first()

    @classmethod
    def tearDownClass(cls):
        cls.db.session.remove(); cls.db.engine.dispose(); cls.context.pop()
        os.remove(cls.path)

    def setUp(self):
        from cms_media_models import MediaCollectionItem, MediaCollection, MediaAsset, PageSection
        for model in (MediaCollectionItem, MediaCollection, MediaAsset, PageSection):
            model.query.delete()
        self.db.session.commit()
        self.client = self.app.test_client()
        with self.client.session_transaction() as session:
            session['user_id'] = self.owner.id
            session['session_version'] = self.owner.session_version

    def asset(self, title='test.png'):
        from cms_media_models import MediaAsset
        asset = MediaAsset(path='uploads/' + title, title=title, alt='A waterfall')
        self.db.session.add(asset); self.db.session.commit()
        return asset.id

    def test_pages_library_and_public_render(self):
        for path in ['/workspace/pages', '/workspace/pages/tour-detail', '/workspace/pages/footer', '/workspace/library', '/', '/api/public-section-backgrounds']:
            self.assertEqual(self.client.get(path).status_code, 200, path)

    def test_collection_order_replace_and_conflict(self):
        first, second = self.asset(), self.asset('second.png')
        url = '/workspace/media-api/collections/hero'
        saved = self.client.post(url, json={'version':0,'items':[{'asset_id':first},{'asset_id':second}]}).get_json()
        self.assertEqual(saved['version'], 1)
        self.assertEqual(self.client.post(url, json={'version':0,'items':[]}).status_code, 409)
        response = self.client.post(url, json={'version':1,'items':[{'asset_id':second},{'asset_id':first}]})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.get(url).get_json()['items'][0]['asset_id'], second)
        self.assertEqual(self.client.delete('/workspace/media-api/assets/' + str(first)).status_code, 409)
        response = self.client.post(url, json={'version':2,'items':[{'asset_id':second}]})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.delete('/workspace/media-api/assets/' + str(first)).status_code, 200)

    def test_invalid_partner_url_and_focal_point(self):
        asset = self.asset()
        url = '/workspace/media-api/collections/footer_partners'
        for extra in [{'url':'javascript:alert(1)'}, {'focal_x':101}, {'visible':'yes'}]:
            self.assertEqual(self.client.post(url, json={'version':0,'items':[dict(asset_id=asset, **extra)]}).status_code, 400)

    def test_failed_upload_preserves_collection(self):
        asset = self.asset()
        url = '/workspace/media-api/collections/hero'
        self.client.post(url, json={'version':0,'items':[{'asset_id':asset}]})
        buffer = io.BytesIO(); Image.new('RGB',(32,32)).save(buffer,format='PNG'); buffer.seek(0)
        with patch('cms_pages.save_image', side_effect=RuntimeError('Cloudinary unavailable')):
            response = self.client.post('/workspace/media-api/assets', data={'image':(buffer,'phone.png')})
        self.assertEqual(response.status_code, 502)
        self.assertEqual(self.client.get(url).get_json()['items'][0]['asset_id'], asset)

    def test_validation_and_successful_upload(self):
        self.assertEqual(self.client.post('/workspace/media-api/assets', data={'image':(io.BytesIO(b'bad'),'bad.png')}).status_code, 400)
        buffer = io.BytesIO(); Image.new('RGB',(32,48)).save(buffer,format='PNG'); buffer.seek(0)
        with patch('cms_pages.save_image', return_value='uploads/valid.png'):
            response = self.client.post('/workspace/media-api/assets', data={'image':(buffer,'valid.png')})
        self.assertEqual(response.status_code, 201)
        result = self.client.get('/workspace/media-api/assets').get_json()[0]
        self.assertEqual((result['width'],result['height']), (32,48))

    def test_logo_bounds_and_stale_save(self):
        url = '/workspace/media-api/hero-placement'
        self.assertEqual(self.client.post(url,json={'version':0,'settings':{'mobile':{'size':500}}}).status_code,400)
        response = self.client.post(url,json={'version':0,'settings':{'mobile':{'size':55,'x':45,'y':50}}})
        self.assertEqual(response.status_code,200)
        self.assertEqual(self.client.post(url,json={'version':0,'settings':{}}).status_code,409)

    def test_content_is_scoped_and_conflict_checked(self):
        url = '/workspace/media-api/content/hero'
        token = self.client.get(url).get_json()['token']
        self.assertEqual(self.client.post(url,json={'token':token,'values':{'footer_contact':'No'}}).status_code,400)
        self.assertEqual(self.client.post(url,json={'token':token,'values':{'hero_title':'Updated hero'}}).status_code,200)
        self.assertEqual(self.client.post(url,json={'token':token,'values':{'hero_title':'Stale'}}).status_code,409)

    def test_section_design_is_scoped_and_conflict_checked(self):
        url = '/workspace/media-api/design/home_about_gallery'
        original = self.client.get(url).get_json()
        token = original['token']
        self.assertEqual(len(original['fields']), 4)
        self.assertEqual(self.client.post(url, json={'token':token, 'values':{'heading_color':'url(bad)'}}).status_code, 400)
        self.assertEqual(self.client.post(url, json={'token':token, 'values':{'unrelated':'#123456'}}).status_code, 400)
        saved = self.client.post(url, json={'token':token, 'values':{'heading_color':'#214b39'}})
        self.assertEqual(saved.status_code, 200)
        self.assertEqual(self.client.post(url, json={'token':token, 'values':{'heading_color':'#123456'}}).status_code, 409)
        fields = {field['name']:field['value'] for field in saved.get_json()['fields']}
        self.assertEqual(fields['heading_color'], '#214b39')
        self.assertEqual(self.app.test_client().get(url).status_code, 302)

    def test_gallery_behavior_is_validated_and_rendered(self):
        url = '/workspace/media-api/gallery-design/home_gallery'
        token = self.client.get(url).get_json()['token']
        values = {'autoplay':False, 'interval':7000, 'ratio':'3/2'}
        self.assertEqual(self.client.post(url, json={'token':token, 'values':dict(values, interval=1)}).status_code, 400)
        saved = self.client.post(url, json={'token':token, 'values':values})
        self.assertEqual(saved.status_code, 200)
        self.assertEqual(saved.get_json()['values'], values)
        self.assertEqual(self.client.post(url, json={'token':token, 'values':values}).status_code, 409)
        html = self.client.get('/').get_data(as_text=True)
        self.assertIn('data-gallery-interval="7000"', html)
        self.assertIn('--gallery-ratio:3/2', html)
        self.assertNotIn('data-cms-gallery data-gallery-autoplay', html)
        # Restore the public defaults for other tests sharing the site settings row.
        self.client.post(url, json={'token':saved.get_json()['token'], 'values':{'autoplay':True,'interval':6000,'ratio':'16/9'}})

    def test_design_permissions_and_csrf_remain_enforced(self):
        from models import User
        user = User(username='media-only', full_name='Media editor', password_hash='disabled',
                    role='content_manager', permissions_json='["manage_media"]')
        self.db.session.add(user); self.db.session.commit()
        client = self.app.test_client()
        with client.session_transaction() as session:
            session['user_id'] = user.id
            session['session_version'] = user.session_version
        self.assertEqual(client.get('/workspace/media-api/design/hero').status_code, 200)
        self.assertEqual(client.get('/workspace/media-api/gallery-design/hero').status_code, 200)
        html = client.get('/workspace/pages').get_data(as_text=True)
        self.assertNotIn('data-panel="content"', html)
        self.assertIn('data-panel="media"', html)
        self.assertIn('Typography & colors', html)
        self.assertIn('id="section-design"', html)
        self.assertNotIn('Navigation & labels', html)

        content_user = User(username='content-only', full_name='Content editor', password_hash='disabled',
                            role='content_manager', permissions_json='["manage_about"]')
        self.db.session.add(content_user); self.db.session.commit()
        content_client = self.app.test_client()
        with content_client.session_transaction() as session:
            session['user_id'] = content_user.id
            session['session_version'] = content_user.session_version
        self.assertEqual(content_client.get('/workspace/media-api/design/hero').status_code, 403)
        content_html = content_client.get('/workspace/pages').get_data(as_text=True)
        self.assertIn('Navigation & labels', content_html)
        self.assertNotIn('Typography & colors', content_html)
        self.assertNotIn('id="section-design"', content_html)

        self.app.config['WTF_CSRF_ENABLED'] = True
        try:
            rejected = client.post('/workspace/media-api/gallery-design/hero', json={})
            self.assertEqual(rejected.status_code, 302)
            self.assertEqual(rejected.location, '/')
            with client.session_transaction() as session:
                self.assertIn('form expired', session['_flashes'][-1][1])
        finally:
            self.app.config['WTF_CSRF_ENABLED'] = False

    def test_explicit_empty_gallery_does_not_restore_legacy_content(self):
        import json
        from app import get_site_settings
        from cms_pages import collection_media
        settings = get_site_settings(); original = settings.public_config_json
        try:
            cfg = json.loads(original)
            cfg.setdefault('theme', {}).setdefault('galleries', {})['home_gallery'] = ['uploads/legacy-gallery.jpg']
            settings.public_config_json = json.dumps(cfg); self.db.session.commit()
            self.assertEqual(len(collection_media('home_gallery')), 1)
            asset_id = self.asset()
            url = '/workspace/media-api/collections/home_gallery'
            filled = self.client.post(url, json={'version': 0, 'items': [{'asset_id': asset_id}]}).json
            cleared = self.client.post(url, json={'version': filled['version'], 'items': []})
            self.assertEqual(cleared.status_code, 200)
            self.assertEqual(collection_media('home_gallery'), [])
            self.assertEqual(self.client.get(url).json['legacy'], [])
        finally:
            settings.public_config_json = original; self.db.session.commit()

    def test_anonymous_cannot_write(self):
        response = self.app.test_client().post('/workspace/media-api/collections/hero',json={'version':0,'items':[]})
        self.assertEqual(response.status_code,302)


if __name__ == '__main__':
    unittest.main()
