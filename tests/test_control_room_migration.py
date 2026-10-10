"""The Control Room migration adds tables without rewriting existing content."""
import unittest
import os
from flask import Flask
from flask_migrate import Migrate, stamp, upgrade, downgrade
from sqlalchemy import inspect
from models import db, Package
from tests.postgres_test_safety import assert_disposable_postgres_url
import cms_media_models
import marketplace_models
import control_room_models


class ControlMigrationTests(unittest.TestCase):
    def test_operations_migration_adopts_bootstrap_and_preserves_rows_on_roundtrip(self):
        from sqlalchemy import text
        app=Flask(__name__)
        database_url = getattr(self, 'url', 'sqlite://')
        app.config.update(SQLALCHEMY_DATABASE_URI=database_url,SQLALCHEMY_TRACK_MODIFICATIONS=False)
        db.init_app(app);Migrate(app,db,directory='migrations')
        with app.app_context():
            if database_url.startswith('postgresql'):
                assert_disposable_postgres_url(database_url)
                with db.engine.begin() as connection:
                    connection.execute(text('DROP SCHEMA public CASCADE'))
                    connection.execute(text('CREATE SCHEMA public'))
            db.create_all()
            stamp(directory='migrations',revision='b7d2e9a4c610')
            upgrade(directory='migrations',revision='c8f1a2d3e470')
            db.session.execute(text("INSERT INTO control_trips (name,destination,start_date,end_date,travellers,status,guide,driver,vehicle,itinerary_json,accommodation_json,checklist_json,created_at,updated_at) VALUES ('Preserved group','Shillong','2026-11-01','2026-11-03',4,'PLANNED','','','','[]','[]','{}',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"))
            db.session.commit();db.session.remove()
            downgrade(directory='migrations',revision='b7d2e9a4c610')
            self.assertEqual(db.session.execute(text('SELECT name FROM control_trips')).scalar(),'Preserved group')
            db.session.remove()
            upgrade(directory='migrations',revision='c8f1a2d3e470')
            self.assertEqual(db.session.execute(text('SELECT name,package_id FROM control_trips')).one(),('Preserved group',None))
            self.assertIn('control_partner_operations',inspect(db.engine).get_table_names())
            db.session.remove();db.engine.dispose()

    def test_shared_image_version_migration_preserves_existing_metadata(self):
        from sqlalchemy import text
        app = Flask(__name__)
        app.config.update(SQLALCHEMY_DATABASE_URI='sqlite://', SQLALCHEMY_TRACK_MODIFICATIONS=False)
        db.init_app(app); Migrate(app, db, directory='migrations')
        with app.app_context():
            db.create_all()
            db.session.execute(text("INSERT INTO cms_media_assets (path,title,alt,caption,credit,version,created_at) VALUES ('uploads/preserved.jpg','Preserved','Existing alt','','',1,CURRENT_TIMESTAMP)"))
            db.session.commit(); db.session.remove()
            with db.engine.begin() as connection:
                connection.execute(text('ALTER TABLE cms_media_assets DROP COLUMN version'))
            stamp(directory='migrations', revision='f9c4d8e1a235')
            upgrade(directory='migrations', revision='b7d2e9a4c610')
            self.assertEqual(db.session.execute(text('SELECT title,alt,version FROM cms_media_assets')).one(), ('Preserved', 'Existing alt', 1))
            db.session.remove()
            downgrade(directory='migrations', revision='f9c4d8e1a235')
            self.assertEqual(db.session.execute(text('SELECT alt FROM cms_media_assets')).scalar(), 'Existing alt')
            db.session.remove(); db.engine.dispose()

    def test_reliability_migration_preserves_content_and_existing_outbox_rows(self):
        from models import SiteSettings, NotificationOutbox, TravellerReview
        from sqlalchemy import text
        app = Flask(__name__)
        app.config.update(SQLALCHEMY_DATABASE_URI='sqlite://', SQLALCHEMY_TRACK_MODIFICATIONS=False)
        db.init_app(app); Migrate(app, db, directory='migrations')
        with app.app_context():
            db.create_all()
            db.session.add_all([SiteSettings(id=1, public_config_json='{"content":{"hero_title":"Preserved"}}'),
                TravellerReview(name='Existing visitor', rating=5, comment='Existing review'),
                NotificationOutbox(source_type='test', source_id='1', event_type='test', channel='email', recipient='test@example.com', body='Preserved delivery')])
            db.session.commit(); db.session.remove()
            with db.engine.begin() as connection:
                connection.execute(text('DROP INDEX ix_notification_outbox_next_attempt_at'))
                for table, column in [('site_settings', 'version'), ('control_website_revisions', 'is_backup'),
                                      ('notification_outbox', 'claim_token'), ('notification_outbox', 'next_attempt_at'),
                                      ('traveller_reviews', 'is_visible')]:
                    connection.execute(text(f'ALTER TABLE {table} DROP COLUMN {column}'))
            stamp(directory='migrations', revision='a9c4d7e2f015')
            upgrade(directory='migrations', revision='f9c4d8e1a235')
            self.assertEqual(db.session.get(SiteSettings, 1).version, 1)
            self.assertIn('Preserved', db.session.get(SiteSettings, 1).public_config_json)
            self.assertTrue(TravellerReview.query.one().is_visible)
            self.assertEqual(NotificationOutbox.query.one().body, 'Preserved delivery')
            db.session.remove()
            downgrade(directory='migrations', revision='a9c4d7e2f015')
            self.assertNotIn('version', {c['name'] for c in inspect(db.engine).get_columns('site_settings')})
            self.assertEqual(db.session.execute(text('SELECT body FROM notification_outbox')).scalar(), 'Preserved delivery')
            db.session.remove(); db.engine.dispose()

    def test_reviews_migration_creates_table_and_adopts_bootstrap(self):
        for existing in (False, True):
            with self.subTest(existing=existing):
                app=Flask(__name__)
                app.config.update(SQLALCHEMY_DATABASE_URI='sqlite://',SQLALCHEMY_TRACK_MODIFICATIONS=False)
                db.init_app(app);Migrate(app,db,directory='migrations')
                with app.app_context():
                    if existing:
                        db.create_all()
                    stamp(directory='migrations',revision='f8b3c7d0e124')
                    upgrade(directory='migrations',revision='a9c4d7e2f015')
                    self.assertIn('traveller_reviews',inspect(db.engine).get_table_names())
                    from models import TravellerReview
                    # Exercise this historical schema without asking today's ORM
                    # to write columns introduced by later migrations.
                    from sqlalchemy import text
                    db.session.execute(text("INSERT INTO traveller_reviews (name,rating,comment,created_at) VALUES ('Migration visitor',5,'Preserved review',CURRENT_TIMESTAMP)"))
                    db.session.commit()
                    self.assertEqual(db.session.execute(text('SELECT rating FROM traveller_reviews')).scalar(),5)
                    db.session.remove();db.engine.dispose()

    def test_follow_up_migration_preserves_existing_leads(self):
        app=Flask(__name__)
        app.config.update(SQLALCHEMY_DATABASE_URI='sqlite://',SQLALCHEMY_TRACK_MODIFICATIONS=False)
        db.init_app(app);Migrate(app,db,directory='migrations')
        with app.app_context():
            tables=[t for t in db.metadata.sorted_tables if not t.name.startswith('control_')]
            db.metadata.create_all(db.engine,tables=tables)
            stamp(directory='migrations',revision='e6f7a8b9c012')
            upgrade(directory='migrations',revision='f7a2b6c9d013')
            from sqlalchemy import text
            db.session.execute(text("INSERT INTO control_leads (source,source_id,status,notes,updated_at) VALUES ('website',99,'CONTACTED','Preserved notes',CURRENT_TIMESTAMP)"))
            db.session.commit()
            upgrade(directory='migrations',revision='f8b3c7d0e124')
            row=db.session.execute(text('SELECT notes,next_action,follow_up FROM control_leads')).one()
            self.assertEqual(tuple(row),('Preserved notes','',None))
            downgrade(directory='migrations',revision='f7a2b6c9d013')
            self.assertEqual(db.session.execute(text('SELECT notes FROM control_leads')).scalar(),'Preserved notes')
            db.session.remove();db.engine.dispose()

    def test_fresh_bootstrap_schema_can_adopt_migration(self):
        app=Flask(__name__)
        app.config.update(SQLALCHEMY_DATABASE_URI='sqlite://',SQLALCHEMY_TRACK_MODIFICATIONS=False)
        db.init_app(app);Migrate(app,db,directory='migrations')
        with app.app_context():
            db.create_all()
            stamp(directory='migrations',revision='e6f7a8b9c012')
            upgrade(directory='migrations',revision='f7a2b6c9d013')
            self.assertIn('control_service_inventory',inspect(db.engine).get_table_names())
            db.session.remove();db.engine.dispose()

    def test_upgrade_and_downgrade_preserve_catalogue(self):
        app=Flask(__name__)
        app.config.update(SQLALCHEMY_DATABASE_URI='sqlite://',SQLALCHEMY_TRACK_MODIFICATIONS=False)
        db.init_app(app);Migrate(app,db,directory='migrations')
        with app.app_context():
            tables=[t for t in db.metadata.sorted_tables if not t.name.startswith('control_')]
            db.metadata.create_all(db.engine,tables=tables)
            package=Package(title='Existing tour',slug='migration-preserved',description='Original content')
            db.session.add(package);db.session.commit()
            stamp(directory='migrations',revision='e6f7a8b9c012')
            upgrade(directory='migrations',revision='f7a2b6c9d013')
            names=inspect(db.engine).get_table_names()
            self.assertIn('control_service_inventory',names)
            self.assertIn('control_partner_documents',names)
            self.assertEqual(db.session.get(Package,package.id).description,'Original content')
            db.session.commit()
            downgrade(directory='migrations',revision='e6f7a8b9c012')
            self.assertNotIn('control_trips',inspect(db.engine).get_table_names())
            self.assertEqual(db.session.get(Package,package.id).description,'Original content')
            db.session.remove();db.engine.dispose()


postgres_url = os.environ.get('CMS_TEST_DATABASE_URL')
assert_disposable_postgres_url(postgres_url)


@unittest.skipUnless(postgres_url, 'CMS_TEST_DATABASE_URL is required for PostgreSQL operational migration QA')
class ControlOperationsPostgresMigrationTests(unittest.TestCase):
    url = postgres_url
    test_operations_migration_adopts_bootstrap_and_preserves_rows_on_roundtrip = ControlMigrationTests.test_operations_migration_adopts_bootstrap_and_preserves_rows_on_roundtrip
