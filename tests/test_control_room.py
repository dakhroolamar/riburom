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
        from models import User, SiteSettings, Message, Package, AuditLog
        from marketplace_models import Provider
        self.fixture_models = (Message,Package,Provider,User)
        self.original_ids = {model:{row[0] for row in self.db.session.query(model.id).all()} for model in self.fixture_models}
        self.original_audit_ids = {row[0] for row in self.db.session.query(AuditLog.id).all()}
        self.settings = SiteSettings.query.first()
        self.original_config = self.settings.public_config_json
        self.client = self.app.test_client()
        self.owner = User.query.filter_by(role='owner').first()
        self.login(self.owner)

    def tearDown(self):
        from models import AuditLog
        self.db.session.rollback()
        AuditLog.query.filter(AuditLog.id.notin_(self.original_audit_ids)).delete(synchronize_session=False)
        # These are disposable unittest fixtures in the named isolated test DB.
        for table in reversed(self.db.metadata.sorted_tables):
            if table.name.startswith('control_'):
                self.db.session.execute(table.delete())
        for model in self.fixture_models:
            model.query.filter(model.id.notin_(self.original_ids[model])).delete(synchronize_session=False)
        self.settings.public_config_json = self.original_config
        self.db.session.commit()
        self.context.pop()
        type(self).context = self.app.app_context()
        self.context.push()

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

    def test_package_editor_validates_structured_input_preserves_url_and_previews_private(self):
        from models import Package
        package = Package(title='Before', slug='stable-tour-url', description='Original', published=False, price='Legacy group rate')
        self.db.session.add(package); self.db.session.commit()
        values = dict(title='Changed title', description='Updated overview', price_mode='amount', price_amount='12500.50',
                      price_basis='person', nights='3', days='4', itinerary='Day 1: Arrival', package_token=package.updated_at.isoformat())
        response = self.client.post(f'/edit_package/{package.id}', data=values)
        self.assertEqual(response.status_code, 302)
        self.db.session.refresh(package)
        self.assertEqual(package.slug, 'stable-tour-url')
        self.assertEqual(package.price, '₹ 12,500.50 per person')
        self.assertEqual(package.duration, '3 Nights / 4 Days')
        self.assertFalse(package.published)
        self.assertEqual(self.client.get('/tours/stable-tour-url').status_code, 404)
        preview = self.client.get(f'/workspace/control/packages/{package.id}/preview')
        self.assertEqual(preview.status_code, 200)
        self.assertIn('no-store', preview.headers['Cache-Control'])
        self.assertIn('noindex', preview.headers['X-Robots-Tag'])
        self.assertIn(b'<title>Changed title', preview.data)
        self.assertEqual(preview.data.count(b'<title>'), 1)
        package.title = 'Escape <unsafe> & preview'
        self.db.session.commit()
        escaped_preview = self.client.get(f'/workspace/control/packages/{package.id}/preview')
        self.assertIn(b'Escape &lt;unsafe&gt; &amp; preview', escaped_preview.data)
        package.title = 'Changed title'
        self.db.session.commit()
        favicon = self.client.get('/favicon.ico')
        self.assertEqual(favicon.status_code, 200)
        self.assertEqual(favicon.mimetype, 'image/svg+xml')
        self.assertIn(b'<svg', favicon.data)
        favicon.close()
        copy = self.client.get(f'/add_package?copy={package.id}')
        self.assertEqual(copy.status_code, 200)
        self.assertIn(b'Changed title (copy)', copy.data)
        self.assertNotIn(b'name="published" checked', copy.data)
        invalid = self.client.post(f'/edit_package/{package.id}', data={**values, 'price_amount':'NaN', 'package_token':package.updated_at.isoformat()})
        self.assertEqual(invalid.status_code, 400)
        self.assertIn(b'Updated overview', invalid.data)
        self.db.session.refresh(package)
        self.assertEqual(package.price, '₹ 12,500.50 per person')

    def test_enquiry_due_mine_spam_and_atomic_bulk_updates(self):
        from datetime import date, timedelta
        from models import Message
        from control_room_models import LeadWorkspace
        records = [Message(name=name, email='work@example.com', message='Trip enquiry') for name in ('Due Traveller','Other Traveller')]
        self.db.session.add_all(records); self.db.session.flush()
        due = LeadWorkspace(source='website', source_id=records[0].id, assigned_user_id=self.owner.id, follow_up=date.today(), status='CONTACTED')
        other = LeadWorkspace(source='website', source_id=records[1].id, follow_up=date.today()-timedelta(days=1), status='NEW')
        self.db.session.add_all([due,other]); self.db.session.commit()
        for view, expected, absent in [('mine','Due Traveller','Other Traveller'),('due','Due Traveller','Other Traveller'),('overdue','Other Traveller','Due Traveller')]:
            text = self.client.get('/workspace/control/enquiries?work='+view).data
            self.assertIn(expected.encode(), text); self.assertNotIn(absent.encode(), text)
        keys = [f'website-{record.id}' for record in records]
        values = dict(keys=keys, action='spam', **{'token_'+keys[0]:due.updated_at.isoformat(), 'token_'+keys[1]:'stale'})
        self.assertEqual(self.client.post('/workspace/control/leads/bulk', data=values).status_code, 409)
        self.db.session.rollback(); self.db.session.refresh(due)
        self.assertEqual(due.status,'CONTACTED')
        values['token_'+keys[1]]=other.updated_at.isoformat()
        self.assertEqual(self.client.post('/workspace/control/leads/bulk', data=values).status_code,302)
        self.db.session.refresh(due); self.db.session.refresh(other)
        self.assertEqual((due.status,other.status),('SPAM','SPAM'))
        active=self.client.get('/workspace/control/enquiries').data
        self.assertNotIn(b'Due Traveller',active)
        self.assertIn(b'Due Traveller',self.client.get('/workspace/control/enquiries?status=SPAM').data)
        reopened=self.client.post('/workspace/control/leads/'+keys[0].replace('-', '/'), data={'action':'reopen','work_token':due.updated_at.isoformat()})
        self.assertEqual(reopened.status_code,302)

    def test_tourism_operations_role_and_personal_preferences_do_not_grant_owner_access(self):
        from models import User, Message
        from control_room_models import ControlPreference
        operator=User(username='tourism-operator',full_name='Tourism Operator',role='tourism_operations',password_hash='disabled')
        self.db.session.add(operator); self.db.session.commit(); self.login(operator)
        for section in ('enquiries','trips','partners','marketplace','media'):
            self.assertEqual(self.client.get('/workspace/control/'+section).status_code,200)
        self.assertEqual(self.client.get('/workspace/control/settings').status_code,403)
        self.assertEqual(self.client.post('/workspace/control/website/home/draft').status_code,403)
        self.assertEqual(self.client.post('/workspace/control/dashboard/preferences',data={'new_enquiries':'on'}).status_code,302)
        own=self.db.session.get(ControlPreference,f'dashboard:{operator.id}')
        self.assertTrue(json.loads(own.value_json)['new_enquiries'])
        self.assertIsNone(self.db.session.get(ControlPreference,'notifications'))
        self.login(self.owner)
        self.assertIsNone(self.db.session.get(ControlPreference,f'dashboard:{self.owner.id}'))

    def test_partner_private_operational_details_and_package_quote_trip_links(self):
        from models import Package, Message
        from marketplace_models import Provider
        from control_room_models import PartnerOperations, Quote, Trip, LeadWorkspace
        partner=Provider(name='Operations Partner',slug='operations-partner',status='DRAFT')
        package=Package(title='Linked Package',slug='linked-package',description='Tour overview')
        message=Message(name='Linked Traveller',email='linked@example.com',message='Tour please')
        self.db.session.add_all([partner,package,message]); self.db.session.commit()
        response=self.client.post(f'/workspace/marketplace/providers/{partner.id}/update',data=dict(name=partner.name,slug=partner.slug,status='APPROVED',is_active='on',contact_person='Contact Person',location='Shillong',service_area='Khasi Hills',operational_notes='Private agreed rate'))
        self.assertEqual(response.status_code,302)
        operations=self.db.session.get(PartnerOperations,partner.id)
        self.assertEqual(operations.location,'Shillong')
        self.assertNotIn(b'Private agreed rate',self.client.get('/marketplace/providers/'+partner.slug).data)
        self.assertEqual(self.client.post(f'/workspace/control/quotes/website/{message.id}',data=dict(package_id=package.id,amount='15000',summary='Confirmed custom group price',valid_until='2026-11-01',work_token='new')).status_code,302)
        self.assertEqual(Quote.query.one().package_id,package.id)
        lead=LeadWorkspace.query.filter_by(source='website',source_id=message.id).one()
        self.assertEqual(self.client.post('/workspace/control/trips/save',data=dict(package_id=package.id,name='Linked Traveller',destination='Shillong',start_date='2026-11-10',end_date='2026-11-13',travellers='4',status='PLANNED',source='website',source_id=message.id,work_token=lead.updated_at.isoformat())).status_code,302)
        trip=Trip.query.one()
        self.assertEqual(trip.package_id,package.id)
        self.assertEqual(self.client.post(f'/delete_package/{package.id}').status_code,302)
        self.assertIsNotNone(self.db.session.get(Package,package.id))
        template=self.client.get(f'/workspace/control/trips/{trip.id}/template')
        self.assertEqual(template.status_code,200)
        self.assertNotIn('start_date',template.json)
        self.assertIn('no-store',template.headers['Cache-Control'])

    def test_readonly_staff_cannot_bulk_triage_or_preview_packages(self):
        from models import User, Message, Package
        viewer=User(username='operations-viewer',full_name='Read Only',role='enquiries',permissions_json='["view_messages"]',password_hash='disabled')
        message=Message(name='Protected lead',email='readonly@example.com',message='Trip')
        package=Package(title='Private package',slug='private-package',description='Private',published=False)
        self.db.session.add_all([viewer,message,package]); self.db.session.commit(); self.login(viewer)
        key=f'website-{message.id}'
        self.assertEqual(self.client.post('/workspace/control/leads/bulk',data={'keys':key,'token_'+key:'new','action':'spam'}).status_code,403)
        self.assertEqual(self.client.get(f'/workspace/control/packages/{package.id}/preview').status_code,403)
        self.assertEqual(self.client.get('/add_package').status_code,403)

    def test_public_enquiry_rejects_malformed_contact_details_and_stores_date_range(self):
        from app import limiter
        from models import Message
        limiter.reset()
        original=Message.query.count()
        common=dict(name='Date validation traveller',email='dates@example.com',message='A family trip please')
        for invalid in ({'phone':'not a number'}, {'travel_dates':'-138'}, {'travel_start':'2026-11-10','travel_end':'2026-11-01'}):
            self.assertEqual(self.client.post('/send_message',data={**common,**invalid}).status_code,302)
            self.assertEqual(Message.query.count(),original)
        self.assertEqual(self.client.post('/send_message',data={**common,'phone':'+91 9876543210','travel_start':'2026-11-01','travel_end':'2026-11-04'}).status_code,302)
        self.assertEqual(Message.query.filter_by(email='dates@example.com').one().travel_dates,'2026-11-01 – 2026-11-04')

    def test_package_upload_error_keeps_typed_fields_without_updating_saved_package(self):
        from models import Package
        from unittest.mock import patch
        package=Package(title='Saved package',slug='upload-saved-package',description='Saved overview',published=False)
        self.db.session.add(package);self.db.session.commit()
        with patch('app.save_image',side_effect=ValueError('Invalid photo')):
            response=self.client.post(f'/edit_package/{package.id}',data=dict(title='Typed replacement name',description='Typed replacement overview',package_token=package.updated_at.isoformat()))
        self.assertEqual(response.status_code,400)
        self.assertIn(b'Typed replacement name',response.data)
        self.db.session.refresh(package)
        self.assertEqual(package.title,'Saved package')

    def test_featured_story_upload_publish_and_unpublish(self):
        from unittest.mock import patch
        from models import SiteSettings
        settings = SiteSettings.query.first()
        fields = ('blog_title', 'blog_excerpt', 'blog_url', 'blog_image', 'blog_enabled', 'blog_show_home', 'public_config_json')
        original = {name: getattr(settings, name) for name in fields}
        try:
            response = self.client.get('/workspace/control/website?page=stories')
            self.assertEqual(response.status_code, 200)
            self.assertIn(b'name="blog_image"', response.data)
            with patch('app.save_image', return_value='uploads/story.png'):
                response = self.client.post('/update_blog', data={
                    'blog_title': 'The King Who Could Not Be Killed',
                    'blog_category': 'Folklore & Legends',
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
            self.assertNotIn(b'data-rb-hero-animation-video', home)
            self.assertNotIn(b'js/hero-intro.js', home)
            self.assertIn(b'data-story-shortcut', home)
            self.assertIn(b'Read Stories', home)
            self.assertNotIn(b'id="rb-home-blog"', home)
            self.assertNotIn(b'The King Who Could Not Be Killed', home)
            self.assertIn(b'href="/stories"', home)
            self.assertIn(b'js/story-navigation-card.js', home)
            self.assertNotIn(b'js/story-notification.js', home)
            self.assertNotIn(b'href="https://example.com/old-story"', home)
            self.assertNotIn(b'A legend passed through oral storytelling.', home)
            listing = self.client.get('/stories').data
            self.assertIn(b'Story categories', listing)
            self.assertIn(b'Folklore &amp; Legends', listing)
            self.assertIn(b'href="/stories/featured"', listing)
            self.assertIn(b'The King Who Could Not Be Killed', listing)
            self.assertIn(b'No published stories in this category.', self.client.get('/stories?category=Nature').data)
            self.assertNotIn(b'id="about-blog"', self.client.get('/about').data)
            self.assertNotIn(b'The King Who Could Not Be Killed', self.client.get('/about').data)
            self.client.post('/update_blog', data={'blog_title': 'Unpublished'})
            self.assertEqual(self.client.get('/stories/featured').status_code, 404)
            self.assertNotIn(b'data-story-shortcut', self.client.get('/').data)
            self.assertNotIn(b'The King Who Could Not Be Killed', self.client.get('/stories').data)
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
        response = self.client.post(base, data={'amount':'12500.50','summary':'Four day guided trip','valid_until':'2026-11-01','work_token':'new'})
        self.assertEqual(response.status_code, 302)
        lead = LeadWorkspace.query.filter_by(source='website',source_id=message.id).one()
        quote = Quote.query.filter_by(lead_id=lead.id).one()
        self.assertEqual(str(quote.amount), '12500.50')
        self.assertIn(b'Four day guided trip', self.client.get(f'/workspace/control/quotes/{quote.id}').data)
        values = dict(name='Workflow Traveller', destination='Shillong', start_date='2026-10-12', end_date='2026-10-15',
                      travellers='4', status='CONFIRMED', guide='Guide', driver='Driver', vehicle='Car',
                      source='website', source_id=str(message.id), itinerary='Arrival\nForest walk', accommodation='Shillong homestay', work_token=lead.updated_at.isoformat())
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

    def test_shared_metadata_rejects_stale_library_and_collection_saves(self):
        from cms_media_models import MediaAsset
        asset = MediaAsset(path='uploads/conflict-fixture.jpg', title='Original')
        self.db.session.add(asset); self.db.session.commit()
        original = asset.version
        saved = self.client.post(f'/workspace/control/media/metadata/{asset.id}', data={
            'version': original, 'title': 'Winner', 'location': 'Shillong'})
        self.assertEqual(saved.status_code, 200)
        self.assertGreater(saved.json['version'], original)
        self.assertEqual(self.client.post(f'/workspace/media-api/assets/{asset.id}', json={
            'version': original, 'alt': 'Stale'}).status_code, 409)
        self.assertEqual(self.client.post('/workspace/media-api/collections/hero', json={
            'version': 0, 'items': [{'asset_id': asset.id}],
            'metadata': {str(asset.id): {'version': original, 'alt': 'Stale'}}}).status_code, 409)
        self.assertEqual(self.client.post(f'/workspace/control/media/metadata/{asset.id}', data={
            'version': original, 'title': 'Stale', 'location': 'Lost'}).status_code, 409)
        self.db.session.expire_all()
        self.assertEqual(asset.title, 'Winner')
        from control_room_models import AssetMetadata
        self.assertEqual(self.db.session.get(AssetMetadata, asset.id).location, 'Shillong')
        response = self.client.post('/workspace/media-api/collections/hero', json={
            'version': 0, 'items': [{'asset_id': asset.id}],
            'metadata': {str(asset.id): {'version': asset.version, 'alt': 'Gallery winner'}}})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['asset_versions'][str(asset.id)], asset.version)
        self.assertEqual(asset.alt, 'Gallery winner')

    def test_empty_tour_gallery_omits_legacy_cover_in_public_cards(self):
        from models import Package
        tour = Package(title='Empty cover tour', slug='empty-cover-tour', description='Fixture', published=True, featured=True, image_file='uploads/legacy-cover-fixture.jpg')
        self.db.session.add(tour); self.db.session.commit()
        self.assertEqual(self.client.post(f'/workspace/media-api/collections/tour-{tour.id}', json={'version':0, 'items':[]}).status_code, 200)
        for route in ['/', '/all_tours']:
            html = self.client.get(route).data
            self.assertNotIn(b'/static/uploads/legacy-cover-fixture.jpg', html)
            import re
            card = next(card for card in re.findall(rb'<article\b.*?</article>', html, re.S) if b'Empty cover tour' in card)
            self.assertNotIn(b'<img', card)

    def test_detail_previews_require_target_and_render_selected_record(self):
        from control_room_models import WebsiteRevision
        from models import Package
        from marketplace_models import Provider
        tour = Package(title='Preview tour', slug='preview-tour', description='Tour fixture', published=True)
        provider = Provider(name='Preview provider', slug='preview-provider', status='APPROVED', is_active=True)
        self.db.session.add_all([tour, provider]); self.db.session.commit()
        for page, slug, expected in [('tour-detail', tour.slug, b'Preview tour'), ('provider', provider.slug, b'Preview provider')]:
            revision = WebsiteRevision(page=page, payload_json=json.dumps({'content': {'tour_detail_overview': 'Draft overview fixture'}, '_base': {'content': {}}}), base_token='test', author_id=self.owner.id)
            self.db.session.add(revision); self.db.session.commit()
            url = f'/workspace/control/website/revisions/{revision.id}/preview'
            selection = self.client.get(url)
            self.assertIn(b'Published record', selection.data)
            self.assertEqual(selection.headers['Cache-Control'], 'private, no-store')
            rendered = self.client.get(url, query_string={'slug': slug})
            self.assertEqual(rendered.status_code, 200)
            self.assertIn(expected, rendered.data)
            if page == 'tour-detail':
                self.assertIn(b'Draft overview fixture', rendered.data)
            self.assertEqual(self.client.get(url, query_string={'slug': 'unpublished-or-missing'}).status_code, 404)

    def test_opening_film_usage_and_filters(self):
        from control_room_models import LibraryVideo
        original = self.settings.hero_animation_video
        try:
            live = LibraryVideo(title='Live film', path='uploads/live-film.mp4', byte_size=20)
            unused = LibraryVideo(title='Unused film', path='uploads/unused-film.mp4', byte_size=20)
            self.db.session.add_all([live, unused]); self.settings.hero_animation_video = live.path
            self.db.session.commit()
            url = '/workspace/control/media/videos?page=1'
            used = self.client.get(url + '&usage=used').json
            self.assertEqual([item['id'] for item in used['items']], [live.id])
            self.assertEqual(used['items'][0]['usage'], ['Homepage opening film'])
            unused_items = self.client.get(url + '&usage=unused').json['items']
            self.assertEqual([item['id'] for item in unused_items], [unused.id])
            self.assertEqual(unused_items[0]['usage'], [])
        finally:
            self.settings.hero_animation_video = original
            self.db.session.commit()

    def test_media_metadata_and_replacement_update_current_references(self):
        from unittest.mock import patch
        from PIL import Image
        from models import Package
        from cms_media_models import MediaAsset
        asset=MediaAsset(path='uploads/control-original.jpg',title='Original')
        package=Package(title='Media reference tour',slug='media-reference-tour',description='Preserved',image_file=asset.path)
        self.db.session.add_all([asset,package]);self.db.session.commit()
        response=self.client.post(f'/workspace/control/media/metadata/{asset.id}',data={'version':asset.version,'title':'Updated title','alt':'Accessible description','location':'Shillong','category':'Landscape','tags':'nature'})
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
