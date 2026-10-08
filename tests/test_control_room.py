"""Authorization, persistence and publishing regressions for Control Room."""
import io
import json
import os
import unittest
from tests.test_bootstrap import configure_isolated_sqlite


class ControlRoomTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.path = configure_isolated_sqlite('control_room')
        import wsgi
        from app import app, db, run_deploy_bootstrap
        cls.app, cls.db = app, db
        app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
        run_deploy_bootstrap()
        cls.context = app.app_context()
        cls.context.push()

    @classmethod
    def tearDownClass(cls):
        cls.db.session.remove()
        cls.db.engine.dispose()
        cls.context.pop()
        try:
            os.remove(cls.path)
        except FileNotFoundError:
            pass

    def setUp(self):
        from models import User, SiteSettings, Message, Package
        from marketplace_models import Provider
        self.fixture_models = (Message,Package,Provider,User)
        self.original_ids = {model:{row[0] for row in self.db.session.query(model.id).all()} for model in self.fixture_models}
        self.settings = SiteSettings.query.first()
        self.original_config = self.settings.public_config_json
        self.client = self.app.test_client()
        self.owner = User.query.filter_by(role='owner').first()
        self.login(self.owner)

    def tearDown(self):
        self.db.session.rollback()
        # These are disposable unittest fixtures in the named isolated test DB.
        for table in reversed(self.db.metadata.sorted_tables):
            if table.name.startswith('control_'):
                self.db.session.execute(table.delete())
        for model in self.fixture_models:
            model.query.filter(model.id.notin_(self.original_ids[model])).delete(synchronize_session=False)
        self.settings.public_config_json = self.original_config
        self.db.session.commit()
        self.db.session.expire_all()

    def login(self, user):
        with self.client.session_transaction() as state:
            state.clear()
            state['user_id'] = user.id
            state['session_version'] = user.session_version

    def test_all_screens_and_legacy_entry_points(self):
        for section in ('overview','enquiries','trips','marketplace','partners','website','media','settings'):
            with self.subTest(section=section):
                response = self.client.get('/workspace/control/'+section)
                self.assertEqual(response.status_code, 200)
                self.assertIn(b'cr-sidebar', response.data)
        for route in ('/workspace','/workspace/cms','/workspace/marketplace','/workspace/administration'):
            self.assertEqual(self.client.get(route).status_code, 302)

    def test_featured_story_upload_publish_and_unpublish(self):
        from unittest.mock import patch
        from models import SiteSettings
        settings = SiteSettings.query.first()
        fields = ('blog_title', 'blog_excerpt', 'blog_url', 'blog_image', 'blog_enabled', 'blog_show_home')
        original = {name: getattr(settings, name) for name in fields}
        try:
            response = self.client.get('/workspace/control/website?page=stories')
            self.assertEqual(response.status_code, 200)
            self.assertIn(b'name="blog_image"', response.data)
            with patch('app.save_image', return_value='uploads/story.png'):
                response = self.client.post('/update_blog', data={
                    'blog_title': 'The King Who Could Not Be Killed',
                    'blog_excerpt': 'A legend passed through oral storytelling.',
                    'blog_url': 'https://example.com/old-story',
                    'blog_enabled': 'on', 'blog_show_home': 'on',
                    'blog_image': (io.BytesIO(b'validated by storage mock'), 'story.png'),
                })
            self.assertEqual(response.status_code, 302)
            self.assertIn('page=stories', response.location)
            page = self.client.get('/stories/featured')
            self.assertEqual(page.status_code, 200)
            self.assertIn(b'The King Who Could Not Be Killed', page.data)
            self.assertIn(b'height:auto', page.data)
            self.assertIn(b'js/ri-burom-motion.js', page.data)
            home = self.client.get('/').data
            self.assertIn(b'aria-label="Featured story"', home)
            self.assertIn(b'Read Stories from Meghalaya', home)
            self.assertIn(b'href="/stories"', home)
            self.assertNotIn(b'href="https://example.com/old-story"', home)
            self.assertNotIn(b'A legend passed through oral storytelling.', home)
            self.client.post('/update_blog', data={'blog_title': 'Unpublished'})
            self.assertEqual(self.client.get('/stories/featured').status_code, 404)
        finally:
            for name, value in original.items():
                setattr(settings, name, value)
            self.db.session.commit()

    def test_story_editor_requires_content_permission(self):
        from models import User
        staff = User(username='story-viewer', full_name='Story Viewer', role='staff', permissions_json='{}', password_hash='unused')
        self.db.session.add(staff)
        self.db.session.commit()
        self.login(staff)
        self.assertEqual(self.client.get('/workspace/control/website?page=stories').status_code, 403)
        self.assertEqual(self.client.post('/update_blog', data={'blog_enabled': 'on'}).status_code, 403)

    def test_invalid_story_image_does_not_publish_settings(self):
        from models import SiteSettings
        settings = SiteSettings.query.first()
        before = (settings.blog_title, settings.blog_image, settings.blog_enabled)
        response = self.client.post('/update_blog', data={
            'blog_title': 'Must not publish', 'blog_enabled': 'on',
            'blog_image': (io.BytesIO(b'not an image'), 'invalid.png'),
        })
        self.assertEqual(response.status_code, 302)
        self.db.session.refresh(settings)
        self.assertEqual((settings.blog_title, settings.blog_image, settings.blog_enabled), before)

    def test_public_review_publishes_immediately_and_escapes_html(self):
        from app import limiter
        from models import TravellerReview
        limiter.reset()
        client = self.app.test_client()
        original_ids = {row.id for row in TravellerReview.query.all()}
        try:
            response = client.post('/reviews', data={'name': '<b>Visitor</b>', 'rating': '5', 'comment': '<script>alert(1)</script>Beautiful journey'})
            self.assertEqual(response.status_code, 303)
            page = client.get('/').data
            self.assertIn(b'5 out of 5 stars', page)
            self.assertIn(b'&lt;script&gt;alert(1)&lt;/script&gt;Beautiful journey', page)
            self.assertNotIn(b'<script>alert(1)</script>', page)
            self.assertLess(page.index(b'id="reviews"'), page.index(b'id="rb-home-contact"'))
            self.assertEqual(page.count(b'class="rb-review-scroll"'), 2)
            count = TravellerReview.query.count()
            client.post('/reviews', data={'name': 'Visitor', 'rating': '6', 'comment': 'Invalid rating'})
            self.assertEqual(TravellerReview.query.count(), count)
            client.post('/reviews', data={'name': 'Visitor', 'rating': '1', 'comment': 'x' * 601})
            self.assertEqual(TravellerReview.query.count(), count)
            self.assertEqual(client.post('/reviews', data={'name':'Visitor','rating':'4','comment':'Limited'}).status_code,429)
        finally:
            TravellerReview.query.filter(TravellerReview.id.notin_(original_ids)).delete(synchronize_session=False)
            self.db.session.commit()
            limiter.reset()

    def test_stories_navigation_has_a_public_empty_state(self):
        from models import SiteSettings
        settings = SiteSettings.query.first()
        enabled = settings.blog_enabled
        try:
            settings.blog_enabled = False
            self.db.session.commit()
            self.assertEqual(self.client.get('/stories').status_code,200)
            self.assertEqual(self.client.get('/stories/featured').status_code,404)
            self.assertIn(b'href="/stories"',self.client.get('/').data)
        finally:
            settings.blog_enabled = enabled
            self.db.session.commit()

    def test_quote_and_trip_conversion_preserve_source_enquiry(self):
        from models import Message
        from control_room_models import LeadWorkspace, Quote, Trip
        message = Message(name='Workflow Traveller', email='workflow@example.com', message='Original enquiry')
        self.db.session.add(message); self.db.session.commit()
        base = f'/workspace/control/quotes/website/{message.id}'
        response = self.client.post(base, data={'amount':'12500.50','summary':'Four day guided trip','valid_until':'2026-11-01'})
        self.assertEqual(response.status_code, 302)
        lead = LeadWorkspace.query.filter_by(source='website',source_id=message.id).one()
        quote = Quote.query.filter_by(lead_id=lead.id).one()
        self.assertEqual(str(quote.amount), '12500.50')
        self.assertIn(b'Four day guided trip', self.client.get(f'/workspace/control/quotes/{quote.id}').data)
        values = dict(name='Workflow Traveller', destination='Shillong', start_date='2026-10-12', end_date='2026-10-15',
                      travellers='4', status='CONFIRMED', guide='Guide', driver='Driver', vehicle='Car',
                      source='website', source_id=str(message.id), itinerary='Arrival\nForest walk', accommodation='Shillong homestay')
        self.assertEqual(self.client.post('/workspace/control/trips/save',data=values).status_code,302)
        trip = Trip.query.filter_by(lead_id=lead.id).one()
        self.assertEqual(json.loads(trip.itinerary_json), ['Arrival','Forest walk'])
        self.assertEqual(message.message,'Original enquiry')
        self.assertEqual(self.client.post('/workspace/control/trips/save',data=values).status_code,409)
        self.db.session.rollback()

    def test_drafts_preview_publish_and_reject_stale_revision(self):
        from app import get_site_settings, get_public_config
        from config_concurrency import public_config_token
        from control_room_models import WebsiteRevision
        settings = get_site_settings()
        before = get_public_config(settings)['content']['site_title']
        values = {'token':public_config_token(settings),'site_title':'Reviewed new site title'}
        self.assertEqual(self.client.post('/workspace/control/website/home/draft',data=values).status_code,302)
        revision = WebsiteRevision.query.order_by(WebsiteRevision.id.desc()).first()
        self.assertEqual(get_public_config(settings)['content']['site_title'], before)
        preview = self.client.get(f'/workspace/control/website/revisions/{revision.id}/preview')
        self.assertEqual(preview.status_code,200)
        self.assertEqual(get_public_config(settings)['content']['site_title'],before)
        self.assertEqual(self.client.post(f'/workspace/control/website/revisions/{revision.id}/publish').status_code,302)
        self.assertEqual(get_public_config(settings)['content']['site_title'],'Reviewed new site title')
        self.assertEqual(self.client.post(f'/workspace/control/website/revisions/{revision.id}/publish').status_code,409)
        self.db.session.rollback()

    def test_partner_documents_are_private_and_reviewable(self):
        from marketplace_models import Provider
        from control_room_models import PartnerDocument
        from models import User
        partner = Provider(name='Private Document Partner',slug='private-document-partner',status='SUBMITTED')
        self.db.session.add(partner); self.db.session.commit()
        response = self.client.post(f'/workspace/control/partners/{partner.id}/documents', data={
            'kind':'Registration','document':(io.BytesIO(b'%PDF-1.4\nPrivate test document'),'registration.pdf')})
        self.assertEqual(response.status_code,302)
        document = PartnerDocument.query.filter_by(provider_id=partner.id).one()
        url = f'/workspace/control/partners/documents/{document.id}'
        # Locate the endpoint path from the registered rule to avoid a false test URL.
        rule = next(r for r in self.app.url_map.iter_rules() if r.endpoint=='control_document')
        url = str(rule).replace('<int:document_id>',str(document.id))
        response = self.client.get(url)
        self.assertEqual(response.status_code,200)
        self.assertIn('no-store',response.headers['Cache-Control'])
        self.assertEqual(self.client.post(url,data={'status':'VERIFIED','review_note':'Checked'}).status_code,302)
        self.assertEqual(document.status,'VERIFIED')
        viewer = User(username='private-doc-viewer',full_name='Viewer',password_hash='disabled',role='enquiries')
        self.db.session.add(viewer);self.db.session.commit();self.login(viewer)
        self.assertEqual(self.client.get(url).status_code,403)
        self.assertEqual(self.client.get('/workspace/control/settings').status_code,403)

    def test_invoice_validation_and_paid_record(self):
        from control_room_models import Invoice
        url='/workspace/control/invoices'
        self.assertEqual(self.client.post(url,data={'customer':'Guest','description':'Trip','amount':'NaN','due_date':'2026-11-01'}).status_code,400)
        self.db.session.rollback()
        self.assertEqual(self.client.post(url,data={'customer':'Guest','description':'Trip','amount':'15000','due_date':'2026-11-01'}).status_code,302)
        invoice=Invoice.query.order_by(Invoice.id.desc()).first()
        self.assertEqual(self.client.post(f'{url}/{invoice.id}',data={'status':'PAID'}).status_code,302)
        self.assertEqual(invoice.status,'PAID')

    def test_read_only_user_cannot_mutate_workflows(self):
        from models import User
        viewer=User(username='workflow-viewer',full_name='Workflow Viewer',password_hash='disabled',role='enquiries',permissions_json='["view_messages"]')
        self.db.session.add(viewer);self.db.session.commit();self.login(viewer)
        self.assertEqual(self.client.get('/workspace/control/enquiries').status_code,200)
        self.assertEqual(self.client.post('/workspace/control/trips/save').status_code,403)
        self.assertEqual(self.client.post('/workspace/control/quotes/website/1').status_code,403)
        self.assertEqual(self.client.post('/workspace/control/website/home/draft').status_code,403)
        self.assertEqual(self.client.post('/workspace/control/media/metadata/1').status_code,403)

    def test_media_metadata_and_replacement_update_current_references(self):
        from unittest.mock import patch
        from PIL import Image
        from models import Package
        from cms_media_models import MediaAsset
        asset=MediaAsset(path='uploads/control-original.jpg',title='Original')
        package=Package(title='Media reference tour',slug='media-reference-tour',description='Preserved',image_file=asset.path)
        self.db.session.add_all([asset,package]);self.db.session.commit()
        response=self.client.post(f'/workspace/control/media/metadata/{asset.id}',data={'title':'Updated title','alt':'Accessible description','location':'Shillong','category':'Landscape','tags':'nature'})
        self.assertEqual(response.status_code,200)
        self.assertTrue(response.json['ok'])
        image=io.BytesIO();Image.new('RGB',(32,32),(20,60,35)).save(image,format='PNG');image.seek(0)
        with patch('storage.save_image',return_value='uploads/control-replacement.jpg'):
            response=self.client.post(f'/workspace/control/media/assets/{asset.id}/replace',data={'image':(image,'replacement.png')})
        self.assertEqual(response.status_code,200)
        self.assertEqual(package.image_file,asset.path)
        self.assertEqual(asset.path,'uploads/control-replacement.jpg')
        self.assertEqual(self.client.delete(f'/workspace/media-api/assets/{asset.id}').status_code,409)

    def test_linked_records_are_preserved_by_old_delete_actions(self):
        from models import Message
        from marketplace_models import Provider
        from control_room_models import LeadWorkspace,PartnerDocument
        message=Message(name='Preserved lead',email='preserve@example.com',message='Retain history')
        partner=Provider(name='Preserved partner',slug='preserved-partner',status='DRAFT')
        self.db.session.add_all([message,partner]);self.db.session.flush()
        self.db.session.add_all([LeadWorkspace(source='website',source_id=message.id),PartnerDocument(provider_id=partner.id,kind='Registration',file_name='private.pdf',file_data=b'%PDF-1.4')]);self.db.session.commit()
        self.assertEqual(self.client.post(f'/delete_message/{message.id}').status_code,302)
        self.assertIsNotNone(self.db.session.get(Message,message.id))
        self.assertEqual(self.client.post(f'/workspace/marketplace/providers/{partner.id}/delete').status_code,302)
        self.assertIsNotNone(self.db.session.get(Provider,partner.id))

    def test_global_search_respects_module_permissions(self):
        from datetime import date
        from models import User,Message
        from control_room_models import Trip
        message=Message(name='Search fixture guest',email='search@example.com',message='Search enquiry')
        trip=Trip(name='Search fixture private trip',destination='Shillong',start_date=date.today(),end_date=date.today())
        viewer=User(username='search-viewer',full_name='Search Viewer',password_hash='disabled',role='enquiries',permissions_json='["view_messages"]')
        self.db.session.add_all([message,trip,viewer]);self.db.session.commit();self.login(viewer)
        response=self.client.get('/workspace/control/search?q=Search%20fixture')
        self.assertEqual(response.status_code,200)
        self.assertIn(b'Search fixture guest',response.data)
        self.assertNotIn(b'Search fixture private trip',response.data)

    def test_media_search_finds_records_beyond_recent_window(self):
        from cms_media_models import MediaAsset
        from datetime import datetime,timedelta
        for index in range(205):
            self.db.session.add(MediaAsset(path=f'uploads/search-fixture-{index}.jpg',title=f'Search asset {index}',created_at=datetime(2020,1,1)+timedelta(days=index)))
        self.db.session.commit()
        response=self.client.get('/workspace/control/media/assets?q=Search%20asset%200')
        self.assertEqual(response.status_code,200)
        self.assertEqual([item['title'] for item in response.json['items']],['Search asset 0'])

    def test_website_embeds_media_without_loading_public_preview(self):
        response = self.client.get('/workspace/control/website')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Page Media & Appearance', response.data)
        self.assertIn(b'id="upload-images"', response.data)
        self.assertNotIn(b'<iframe', response.data)
        self.assertNotIn(b'Content JSON', response.data)

    def test_work_accept_update_close_reopen_and_stale_save(self):
        from models import Message, AuditLog
        from control_room_models import LeadWorkspace
        message=Message(name='Desk Guest',email='desk@example.com',message='Original request')
        self.db.session.add(message);self.db.session.commit()
        url=f'/workspace/control/leads/website/{message.id}'
        self.assertEqual(self.client.post(url,data={'work_token':'new','action':'accept'}).status_code,302)
        state=LeadWorkspace.query.filter_by(source='website',source_id=message.id).one()
        self.assertEqual(state.status,'IN_PROGRESS')
        self.assertEqual(state.assigned_user_id,self.owner.id)
        old_token=state.updated_at.isoformat()
        data={'work_token':old_token,'status':'CONTACTED','assigned_user_id':str(self.owner.id),
              'next_action':'Send estimate','follow_up':'2026-10-08','progress_note':'Called customer.'}
        self.assertEqual(self.client.post(url,data=data).status_code,302)
        self.assertEqual(state.next_action,'Send estimate')
        self.assertEqual(state.follow_up.isoformat(),'2026-10-08')
        self.assertEqual(self.client.post(url,data={'work_token':old_token,'action':'close'}).status_code,409)
        for action,status in [('close','CLOSED'),('reopen','NEW')]:
            self.assertEqual(self.client.post(url,data={'work_token':state.updated_at.isoformat(),'action':action}).status_code,302)
            self.assertEqual(state.status,status)
        self.assertEqual(message.message,'Original request')
        history=AuditLog.query.filter_by(target_type='control_leads',target_id=str(state.id),action='work_updated').all()
        self.assertEqual(len(history),4)
        self.assertTrue(any('Called customer.' in item.details for item in history))

    def test_closed_work_is_filtered_and_viewer_cannot_update(self):
        from models import Message,User
        from control_room_models import LeadWorkspace
        message=Message(name='Closed Desk Guest',email='closed@example.com',message='Request')
        self.db.session.add(message);self.db.session.flush()
        state=LeadWorkspace(source='website',source_id=message.id,status='CLOSED')
        viewer=User(username='desk-read-only',full_name='Viewer',password_hash='disabled',role='custom',permissions_json='["view_messages"]')
        self.db.session.add_all([state,viewer]);self.db.session.commit()
        self.assertNotIn(b'Closed Desk Guest',self.client.get('/workspace/control/enquiries').data)
        self.assertIn(b'Closed Desk Guest',self.client.get('/workspace/control/enquiries?status=CLOSED').data)
        self.login(viewer)
        response=self.client.get('/workspace/control/enquiries?status=CLOSED')
        self.assertNotIn(b'Accept &amp; assign to me',response.data)
        self.assertEqual(self.client.post(f'/workspace/control/leads/website/{message.id}',data={'work_token':state.updated_at.isoformat(),'action':'reopen'}).status_code,403)

if __name__ == '__main__':
    unittest.main()
