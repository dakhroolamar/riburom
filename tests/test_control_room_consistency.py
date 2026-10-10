"""Independent regressions for shared tourism work and capped inventory selectors."""
import json
import unittest
from datetime import datetime, timedelta
from html.parser import HTMLParser

from tests import test_control_room as fixtures


class PackageOptions(HTMLParser):
    def __init__(self):
        super().__init__()
        self.edit_form = False
        self.package_select = False
        self.selected = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'dialog':
            self.edit_form = attrs.get('id') == 'trip-edit'
        if self.edit_form and tag == 'select':
            self.package_select = attrs.get('name') == 'package_id'
        if self.package_select and tag == 'option' and 'selected' in attrs:
            self.selected.append(attrs.get('value'))

    def handle_endtag(self, tag):
        if tag == 'select':
            self.package_select = False
        elif tag == 'dialog':
            self.edit_form = False


class ReviewFields(HTMLParser):
    def __init__(self, action):
        super().__init__()
        self.action = action
        self.active = False
        self.select_name = None
        self.option_selected = False
        self.fields = {}

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'form':
            self.active = attrs.get('action') == self.action
        if not self.active:
            return
        if tag == 'input' and attrs.get('name'):
            self.fields[attrs['name']] = attrs.get('value', '')
        elif tag == 'select':
            self.select_name = attrs.get('name')
        elif tag == 'option':
            self.option_selected = 'selected' in attrs

    def handle_data(self, data):
        if self.active and self.select_name and self.option_selected:
            self.fields[self.select_name] = data.strip()

    def handle_endtag(self, tag):
        if tag == 'form':
            self.active = False
        elif tag == 'select':
            self.select_name = None
        elif tag == 'option':
            self.option_selected = False


class ControlRoomConsistencyTests(unittest.TestCase):
    setUpClass = classmethod(fixtures.ControlRoomTests.setUpClass.__func__)
    tearDownClass = classmethod(fixtures.ControlRoomTests.tearDownClass.__func__)
    setUp = fixtures.ControlRoomTests.setUp
    tearDown = fixtures.ControlRoomTests.tearDown
    login = fixtures.ControlRoomTests.login

    def enquiry(self, status='NEW'):
        from models import Message
        from control_room_models import LeadWorkspace
        message = Message(name='Consistency traveller', email='consistency@example.invalid', message='Original traveller notes')
        self.db.session.add(message)
        self.db.session.flush()
        lead = LeadWorkspace(source='website', source_id=message.id, status=status)
        self.db.session.add(lead)
        self.db.session.commit()
        return message, lead

    def quote_data(self, token):
        return dict(amount='1234.50', summary='Reviewed quote', valid_until='2026-11-01', work_token=token)

    def trip_data(self, **overrides):
        return dict(name='Consistency group', destination='Shillong', start_date='2026-11-10',
                    end_date='2026-11-13', travellers='3', status='PLANNED', itinerary='Arrival\nForest walk',
                    guide='Original guide', **overrides)

    def create_trip(self):
        from control_room_models import Trip
        self.assertEqual(self.client.post('/workspace/control/trips/save', data=self.trip_data()).status_code, 302)
        return Trip.query.order_by(Trip.id.desc()).first()

    def test_terminal_enquiries_require_reopen_before_quote_or_conversion(self):
        from control_room_models import Quote, Trip
        for state in ('SPAM', 'CLOSED', 'DECLINED'):
            with self.subTest(status=state):
                message, lead = self.enquiry(state)
                token = lead.updated_at.isoformat()
                self.assertEqual(self.client.post(f'/workspace/control/quotes/website/{message.id}', data=self.quote_data(token)).status_code, 409)
                self.assertEqual(self.client.post('/workspace/control/trips/save', data=self.trip_data(source='website', source_id=message.id, work_token=token)).status_code, 409)
                self.db.session.expire_all()
                self.assertEqual(lead.status, state)
                self.assertEqual(Quote.query.filter_by(lead_id=lead.id).count(), 0)
                self.assertEqual(Trip.query.filter_by(lead_id=lead.id).count(), 0)

    def test_revised_quote_preserves_confirmed_status(self):
        from control_room_models import Quote
        message, lead = self.enquiry('CONFIRMED')
        self.assertEqual(self.client.post(f'/workspace/control/quotes/website/{message.id}', data=self.quote_data(lead.updated_at.isoformat())).status_code, 302)
        self.db.session.expire_all()
        self.assertEqual(lead.status, 'CONFIRMED')
        self.assertEqual(Quote.query.filter_by(lead_id=lead.id).count(), 1)

    def test_stale_and_missing_enquiry_tokens_do_not_create_documents_or_trips(self):
        from control_room_models import Quote, Trip
        message, lead = self.enquiry()
        old = lead.updated_at.isoformat()
        lead.notes = 'Another manager recorded a call'
        lead.updated_at = datetime.utcnow() + timedelta(seconds=1)
        self.db.session.commit()
        for token in (old, None):
            quote = self.quote_data(token)
            trip = self.trip_data(source='website', source_id=message.id, work_token=token)
            if token is None:
                quote.pop('work_token'); trip.pop('work_token')
            self.assertEqual(self.client.post(f'/workspace/control/quotes/website/{message.id}', data=quote).status_code, 409)
            self.assertEqual(self.client.post('/workspace/control/trips/save', data=trip).status_code, 409)
        self.db.session.expire_all()
        self.assertEqual(lead.status, 'NEW')
        self.assertEqual(lead.notes, 'Another manager recorded a call')
        self.assertEqual(Quote.query.filter_by(lead_id=lead.id).count(), 0)
        self.assertEqual(Trip.query.filter_by(lead_id=lead.id).count(), 0)

    def test_stale_trip_editor_and_checklists_preserve_latest_assignments(self):
        trip = self.create_trip()
        old = trip.updated_at.isoformat()
        trip.guide = 'New manager guide'
        trip.updated_at = datetime.utcnow() + timedelta(seconds=1)
        self.db.session.commit()
        for token in (old, None):
            data = self.trip_data(id=trip.id, trip_token=token)
            if token is None:
                data.pop('trip_token')
            self.assertEqual(self.client.post('/workspace/control/trips/save', data=data).status_code, 409)
            for action in ('checklist', 'milestones'):
                update = dict(action=action, trip_token=token, completed=['Vehicle assigned and inspected'], completed_days=['1'])
                if token is None:
                    update.pop('trip_token')
                self.assertEqual(self.client.post(f'/workspace/control/trips/{trip.id}/update', data=update).status_code, 409)
        self.db.session.expire_all()
        self.assertEqual(trip.guide, 'New manager guide')
        self.assertEqual(json.loads(trip.checklist_json), {})

    def test_selected_package_outside_inventory_cap_survives_trip_edit(self):
        from models import Package
        for index in range(205):
            self.db.session.add(Package(title=f'AAA inventory {index:03}', slug=f'consistency-cap-{index}', description='Inventory fixture', published=False))
        package = Package(title='ZZZ linked inventory', slug='consistency-linked-inventory', description='Linked fixture', published=False)
        self.db.session.add(package); self.db.session.commit()
        self.assertEqual(self.client.post('/workspace/control/trips/save', data=self.trip_data(package_id=package.id)).status_code, 302)
        from control_room_models import Trip
        trip = Trip.query.order_by(Trip.id.desc()).first()
        response = self.client.get(f'/workspace/control/trips?selected={trip.id}')
        self.assertEqual(response.status_code, 200)
        parser = PackageOptions(); parser.feed(response.get_data(as_text=True))
        self.assertEqual(parser.selected, [str(package.id)])
        self.assertEqual(self.client.post('/workspace/control/trips/save', data=self.trip_data(id=trip.id, trip_token=trip.updated_at.isoformat(), package_id=parser.selected[0])).status_code, 302)
        self.db.session.expire_all()
        self.assertEqual(trip.package_id, package.id)

    def test_two_concurrent_trip_sessions_cannot_overwrite_the_winner(self):
        from sqlalchemy.orm import Session
        from sqlalchemy.orm.exc import StaleDataError
        from control_room_models import Trip
        trip = self.create_trip()
        with Session(self.db.engine) as first, Session(self.db.engine) as second:
            original = first.get(Trip, trip.id)
            stale = second.get(Trip, trip.id)
            original.guide = 'Winning manager guide'
            first.commit()
            stale.guide = 'Losing manager guide'
            with self.assertRaises(StaleDataError):
                second.commit()
            second.rollback()
        self.db.session.expire_all()
        self.assertEqual(trip.guide, 'Winning manager guide')

    def test_stale_and_missing_package_tokens_preserve_saved_content(self):
        from models import Package
        package = Package(title='Original package', slug='consistency-package-token', description='Original overview', published=False)
        self.db.session.add(package); self.db.session.commit()
        old = package.updated_at.isoformat()
        package.title = 'Latest manager package'
        package.updated_at = datetime.utcnow() + timedelta(seconds=1)
        self.db.session.commit()
        for token in (old, None):
            data = dict(title='Stale manager package', description='Stale overview', package_token=token)
            if token is None:
                data.pop('package_token')
            self.assertEqual(self.client.post(f'/edit_package/{package.id}', data=data).status_code, 409)
        self.db.session.expire_all()
        self.assertEqual(package.title, 'Latest manager package')
        self.assertEqual(package.description, 'Original overview')

    def test_two_concurrent_package_sessions_cannot_overwrite_the_winner(self):
        from sqlalchemy.orm import Session
        from sqlalchemy.orm.exc import StaleDataError
        from models import Package
        package = Package(title='Original race package', slug='consistency-package-race', description='Original overview', published=False)
        self.db.session.add(package); self.db.session.commit()
        with Session(self.db.engine) as first, Session(self.db.engine) as second:
            winner = first.get(Package, package.id)
            stale = second.get(Package, package.id)
            winner.description = 'Winning manager overview'
            first.commit()
            stale.description = 'Losing manager overview'
            with self.assertRaises(StaleDataError):
                second.commit()
            second.rollback()
        self.db.session.expire_all()
        self.assertEqual(package.description, 'Winning manager overview')

    def test_authenticated_enquiry_and_quote_responses_are_not_cacheable(self):
        from control_room_models import Quote
        message, lead = self.enquiry()
        self.assertEqual(self.client.post(f'/workspace/control/quotes/website/{message.id}', data=self.quote_data(lead.updated_at.isoformat())).status_code, 302)
        quote = Quote.query.filter_by(lead_id=lead.id).one()
        for url in (f'/workspace/control/enquiries?selected=website-{message.id}', f'/workspace/control/quotes/{quote.id}'):
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertIn('private', response.headers.get('Cache-Control', ''))
            self.assertIn('no-store', response.headers.get('Cache-Control', ''))

    def test_partner_review_form_preserves_status_and_note_when_editing_one_field(self):
        from marketplace_models import Provider
        from control_room_models import PartnerDocument
        partner = Provider(name='Consistency review partner', slug='consistency-review-partner', status='UNDER_REVIEW')
        self.db.session.add(partner); self.db.session.flush()
        document = PartnerDocument(provider_id=partner.id, kind='Registration', file_name='fixture.pdf', file_data=b'%PDF-1.4',
                                   status='UNDER_REVIEW', review_note='Check <private> & original')
        self.db.session.add(document); self.db.session.commit()
        action = f'/workspace/control/documents/{document.id}'
        page = self.client.get(f'/workspace/control/partners?selected={partner.id}')
        fields = ReviewFields(action); fields.feed(page.get_data(as_text=True))
        self.assertEqual(fields.fields['status'], 'UNDER_REVIEW')
        self.assertEqual(fields.fields['review_note'], 'Check <private> & original')
        self.assertEqual(self.client.post(action, data={**fields.fields, 'review_note':'Updated private note'}).status_code, 302)
        self.db.session.expire_all()
        self.assertEqual(document.status, 'UNDER_REVIEW')
        page = self.client.get(f'/workspace/control/partners?selected={partner.id}')
        fields = ReviewFields(action); fields.feed(page.get_data(as_text=True))
        self.assertEqual(self.client.post(action, data={**fields.fields, 'status':'REJECTED'}).status_code, 302)
        self.db.session.expire_all()
        self.assertEqual(document.status, 'REJECTED')
        self.assertEqual(document.review_note, 'Updated private note')
