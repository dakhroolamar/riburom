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

    def test_anonymous_cannot_write(self):
        response = self.app.test_client().post('/workspace/media-api/collections/hero',json={'version':0,'items':[]})
        self.assertEqual(response.status_code,302)


if __name__ == '__main__':
    unittest.main()
