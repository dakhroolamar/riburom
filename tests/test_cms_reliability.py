"""Regression coverage for CMS latency, draft rebasing and durable delivery."""
import json
import os
import unittest
from datetime import datetime, timedelta
from unittest.mock import patch
from sqlalchemy import event
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError
from tests.test_bootstrap import configure_isolated_sqlite


class CmsReliabilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.path = configure_isolated_sqlite('cms_reliability')
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
        from models import User, SiteSettings, NotificationOutbox, TravellerReview
        from cms_media_models import MediaAsset, MediaCollection, MediaCollectionItem
        from control_room_models import WebsiteRevision, ControlPreference
        self.models = (NotificationOutbox, TravellerReview, MediaCollectionItem, MediaCollection, MediaAsset, WebsiteRevision, ControlPreference)
        self.original_ids = {model: {row[0] for row in self.db.session.query(model.__mapper__.primary_key[0]).all()} for model in self.models}
        self.settings = self.db.session.get(SiteSettings, 1)
        self.original_config = self.settings.public_config_json
        self.client = self.app.test_client()
        owner = User.query.filter_by(role='owner').first()
        with self.client.session_transaction() as state:
            state['user_id'] = owner.id
            state['session_version'] = owner.session_version

    def tearDown(self):
        from models import SiteSettings
        self.db.session.rollback()
        for model in self.models:
            model.query.filter(model.__mapper__.primary_key[0].notin_(self.original_ids[model])).delete(synchronize_session=False)
        self.db.session.get(SiteSettings, 1).public_config_json = self.original_config
        self.db.session.commit()
        self.db.session.expire_all()

    def draft(self, title):
        from config_concurrency import public_config_token
        from control_room_models import WebsiteRevision
        response = self.client.post('/workspace/control/website/home/draft', data={
            'token': public_config_token(self.settings), 'hero_title': title})
        self.assertEqual(response.status_code, 302)
        return WebsiteRevision.query.filter_by(page='home', is_backup=False).order_by(WebsiteRevision.id.desc()).first()

    def test_dashboard_has_bounded_queries_and_reuses_authenticated_user(self):
        queries = []
        def count_queries(conn, cursor, statement, parameters, context, executemany):
            queries.append(statement)
        event.listen(self.db.engine, 'before_cursor_execute', count_queries)
        try:
            self.assertEqual(self.client.get('/workspace/control/overview').status_code, 200)
        finally:
            event.remove(self.db.engine, 'before_cursor_execute', count_queries)
        self.assertLessEqual(len(queries), 15)
        self.assertLessEqual(sum('FROM users' in statement for statement in queries), 1)

    def test_request_cached_user_still_validates_session_revocation(self):
        from flask import session
        from app import get_current_user
        from models import User
        owner = User.query.filter_by(role='owner').first()
        with self.app.test_request_context('/'):
            session['user_id'] = owner.id
            session['session_version'] = owner.session_version
            self.assertEqual(get_current_user().id, owner.id)
            session['session_version'] = owner.session_version + 1
            self.assertIsNone(get_current_user())
            self.assertNotIn('user_id', session)

    def test_media_query_budget_and_pagination_are_independent_of_library_size(self):
        from cms_media_models import MediaAsset
        def add(start, count):
            self.db.session.add_all([MediaAsset(path=f'uploads/performance-fixture-{i}.jpg', title=f'performance-fixture {i}') for i in range(start, start + count)])
            self.db.session.commit()
        def measure():
            queries = []
            def capture(*args): queries.append(args[2])
            event.listen(self.db.engine, 'before_cursor_execute', capture)
            try:
                response = self.client.get('/workspace/control/media/assets?q=performance-fixture')
                self.assertEqual(response.status_code, 200)
                return len(queries)
            finally:
                event.remove(self.db.engine, 'before_cursor_execute', capture)
        add(0, 10)
        small = measure()
        add(10, 90)
        large = measure()
        self.assertLessEqual(large, 15)
        self.assertLessEqual(large, small + 2)
        first = self.client.get('/workspace/control/media/assets?q=performance-fixture&page=1').json
        second = self.client.get('/workspace/control/media/assets?q=performance-fixture&page=2').json
        self.assertEqual(first['total'], 100)
        self.assertEqual(len(first['items']), 40)
        self.assertTrue(first['has_next'])
        self.assertFalse({a['id'] for a in first['items']} & {a['id'] for a in second['items']})

    def test_atomic_version_rejects_two_overlapping_configuration_writes(self):
        from models import SiteSettings
        with Session(self.db.engine) as first, Session(self.db.engine) as second:
            a, b = first.get(SiteSettings, 1), second.get(SiteSettings, 1)
            a.public_config_json = json.dumps({'content': {'hero_title': 'First editor'}})
            b.public_config_json = json.dumps({'content': {'hero_subtitle': 'Second editor'}})
            first.commit()
            with self.assertRaises(StaleDataError):
                second.commit()
            second.rollback()
        self.db.session.expire_all()
        self.assertEqual(json.loads(self.settings.public_config_json)['content']['hero_title'], 'First editor')

    def test_appearance_save_does_not_invalidate_an_unrelated_text_draft(self):
        from config_concurrency import public_config_token
        from app import get_public_config
        revision = self.draft('Rebased draft title')
        response = self.client.post('/workspace/media-api/design/hero', json={
            'token': public_config_token(self.settings), 'values': {'background_color': '#123456'}})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.post(f'/workspace/control/website/revisions/{revision.id}/publish').status_code, 302)
        cfg = get_public_config(self.settings)
        self.assertEqual(cfg['content']['hero_title'], 'Rebased draft title')
        self.assertEqual(cfg['theme']['sections']['hero']['background_color'], '#123456')
        editor = self.client.get('/workspace/control/website').data
        self.assertIn(b'Rebased draft title', editor)
        from control_room_models import WebsiteRevision
        backup = WebsiteRevision.query.filter_by(is_backup=True).order_by(WebsiteRevision.id.desc()).first()
        self.assertIsNone(backup.published_at)

    def test_conflicting_text_edit_still_blocks_publication_and_preview_is_linked(self):
        from config_concurrency import public_config_token
        revision = self.draft('Draft title')
        self.assertIn(f'/revisions/{revision.id}/preview'.encode(), self.client.get('/workspace/control/website').data)
        self.client.post('/workspace/media-api/content/hero', json={'token': public_config_token(self.settings), 'values': {'hero_title': 'Other editor'}})
        self.assertEqual(self.client.post(f'/workspace/control/website/revisions/{revision.id}/publish').status_code, 409)

    def test_gallery_metadata_and_selection_commit_together(self):
        from cms_media_models import MediaAsset
        asset = MediaAsset(path='uploads/batch-metadata-fixture.jpg', title='Batch fixture')
        self.db.session.add(asset); self.db.session.commit()
        current = self.client.get('/workspace/media-api/collections/home_gallery').json
        request = dict(version=current['version'], items=[{'asset_id': asset.id}], metadata={str(asset.id): {'version':asset.version, 'alt': 'New alt text'}})
        self.assertEqual(self.client.post('/workspace/media-api/collections/home_gallery', json=request).status_code, 200)
        self.assertEqual(self.db.session.get(MediaAsset, asset.id).alt, 'New alt text')
        request['metadata'][str(asset.id)]['alt'] = 'Stale overwrite'
        self.assertEqual(self.client.post('/workspace/media-api/collections/home_gallery', json=request).status_code, 409)
        self.assertEqual(self.db.session.get(MediaAsset, asset.id).alt, 'New alt text')

    def test_cms_indexing_is_queued_without_calling_the_network(self):
        from models import NotificationOutbox
        from indexnow import notify_indexnow_paths, PUBLIC_BASE_URL
        with patch.dict(os.environ, {'INDEXNOW_KEY': 'reliability-fixture-key'}), patch('indexnow.submit_indexnow_urls') as network:
            with self.app.test_request_context('/'):
                first = notify_indexnow_paths(['/about'])
                second = notify_indexnow_paths(['/about'])
            network.assert_not_called()
            self.assertTrue(first['queued'] and second['queued'])
            rows = NotificationOutbox.query.filter_by(channel='indexnow', body=json.dumps([PUBLIC_BASE_URL + '/about'], separators=(',', ':'))).all()
            self.assertEqual(len(rows), 1)

    def test_cms_save_commits_indexing_intent_in_the_same_transaction(self):
        from models import NotificationOutbox
        from config_concurrency import public_config_token
        session = self.db.session()
        commit = session.commit
        with patch.dict(os.environ, {'INDEXNOW_KEY': 'atomic-review-key'}), patch('indexnow.submit_indexnow_urls') as network:
            with patch.object(session, 'commit', wraps=commit) as commits:
                response = self.client.post('/workspace/media-api/content/hero', json={
                    'token': public_config_token(self.settings), 'values': {'hero_title': 'Atomic title'}})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(commits.call_count, 1)
            network.assert_not_called()
            self.assertTrue(NotificationOutbox.query.filter_by(channel='indexnow', status='PENDING').count())
            self.assertEqual(json.loads(self.settings.public_config_json)['content']['hero_title'], 'Atomic title')

    def test_failed_content_commit_rolls_back_indexing_intent_too(self):
        from models import NotificationOutbox
        from config_concurrency import public_config_token
        before = NotificationOutbox.query.filter_by(channel='indexnow').count()
        original = self.settings.public_config_json
        with patch.dict(os.environ, {'INDEXNOW_KEY': 'atomic-review-key'}), patch.object(self.db.session(), 'commit', side_effect=RuntimeError('Injected commit failure')):
            with self.assertRaisesRegex(RuntimeError, 'Injected commit failure'):
                self.client.post('/workspace/media-api/content/hero', json={
                    'token': public_config_token(self.settings), 'values': {'hero_title': 'Uncommitted title'}})
        self.db.session.rollback(); self.db.session.expire_all()
        self.assertEqual(self.settings.public_config_json, original)
        self.assertEqual(NotificationOutbox.query.filter_by(channel='indexnow').count(), before)

    def test_shared_image_orm_version_rejects_overlapping_sessions(self):
        from cms_media_models import MediaAsset
        asset = MediaAsset(path='uploads/overlapping-review.jpg', title='Original')
        self.db.session.add(asset); self.db.session.commit()
        with Session(self.db.engine) as first, Session(self.db.engine) as second:
            a = first.get(MediaAsset, asset.id); b = second.get(MediaAsset, asset.id)
            a.alt = 'Winner'; b.alt = 'Stale'
            first.commit()
            with self.assertRaises(StaleDataError):
                second.commit()
            second.rollback()
        self.db.session.expire_all()
        self.assertEqual(asset.alt, 'Winner')

    def test_delivery_claim_blocks_an_overlapping_worker_and_retries_after_backoff(self):
        from models import NotificationOutbox
        from notifications import process_outbox_ids
        row = NotificationOutbox(source_type='fixture', source_id='exclusive', event_type='fixture', channel='email', recipient='test@example.com', body='Claim test')
        self.db.session.add(row); self.db.session.commit(); row_id = row.id
        def delivery(claimed):
            # A second worker arrives while the first is inside the provider call.
            with self.app.app_context():
                self.assertEqual(process_outbox_ids([row_id])['skipped'], 1)
            return False
        with patch('notifications._deliver_outbox_row', side_effect=delivery):
            self.assertEqual(process_outbox_ids([row_id])['failed'], 1)
        self.assertEqual(process_outbox_ids([row_id])['skipped'], 1)
        row = self.db.session.get(NotificationOutbox, row_id)
        row.next_attempt_at = datetime.utcnow() - timedelta(seconds=1)
        self.db.session.commit()
        with patch('notifications._deliver_outbox_row', return_value=True) as delivery:
            self.assertEqual(process_outbox_ids([row_id])['sent'], 1)
            delivery.assert_called_once()
        self.assertEqual(self.db.session.get(NotificationOutbox, row_id).attempts, 2)

    def test_expired_delivery_lease_can_be_recovered(self):
        from models import NotificationOutbox
        from notifications import process_outbox_ids
        row = NotificationOutbox(source_type='fixture', source_id='expired', event_type='fixture', channel='email', recipient='test@example.com', body='Recovery', status='PROCESSING', attempts=1, claim_token='dead-worker', next_attempt_at=datetime.utcnow() - timedelta(seconds=1))
        self.db.session.add(row); self.db.session.commit(); row_id = row.id
        with patch('notifications._deliver_outbox_row', return_value=True):
            self.assertEqual(process_outbox_ids([row_id])['sent'], 1)
        self.assertIsNone(self.db.session.get(NotificationOutbox, row_id).claim_token)

    def test_owner_can_disable_delivery_and_cancel_pending_notifications(self):
        from models import NotificationOutbox
        from control_room_models import ControlPreference
        from notifications import enqueue_new_enquiry
        previous = self.db.session.get(ControlPreference, 'delivery')
        original = previous.value_json if previous else None
        row = NotificationOutbox(source_type='fixture', source_id='disable', event_type='fixture', channel='email', recipient='test@example.com', body='Disabled delivery')
        self.db.session.add(row); self.db.session.commit()
        try:
            response = self.client.post('/workspace/control/settings/notifications', data={'delivery_preferences': '1'})
            self.assertEqual(response.status_code, 302)
            self.assertEqual(self.db.session.get(NotificationOutbox, row.id).status, 'CANCELLED')
            with patch.dict(os.environ, {'NOTIFICATION_EMAIL': 'test@example.com', 'NOTIFICATION_PHONE': '+123456789'}), patch('notifications._messaging_configured', return_value=True):
                self.assertEqual(enqueue_new_enquiry({'name': 'Muted'}, source_type='fixture', source_id='muted'), [])
        finally:
            if original is not None:
                self.db.session.get(ControlPreference, 'delivery').value_json = original
                self.db.session.commit()

    def test_review_moderation_and_generic_success_feedback(self):
        from models import TravellerReview
        review = TravellerReview(name='Moderation fixture', rating=4, comment='Unique moderation comment')
        self.db.session.add(review); self.db.session.commit()
        self.assertIn(b'Unique moderation comment', self.client.get('/').data)
        self.assertEqual(self.app.test_client().post(f'/workspace/control/reviews/{review.id}', data={'action': 'hide'}).status_code, 302)
        self.client.post(f'/workspace/control/reviews/{review.id}', data={'action': 'hide'})
        self.assertNotIn(b'Unique moderation comment', self.client.get('/').data)
        self.client.post(f'/workspace/control/reviews/{review.id}', data={'action': 'show'})
        self.assertIn(b'Unique moderation comment', self.client.get('/').data)
        with self.client.session_transaction() as state: state['_flashes'] = [('success', 'Logged out.')]
        response = self.client.get('/').data
        self.assertIn(b'Logged out.', response)
        self.assertNotIn(b'rbSuccessModal', response)


if __name__ == '__main__':
    unittest.main()
