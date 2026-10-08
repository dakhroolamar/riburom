"""The Control Room migration adds tables without rewriting existing content."""
import unittest
from flask import Flask
from flask_migrate import Migrate, stamp, upgrade, downgrade
from sqlalchemy import inspect
from models import db, Package
import cms_media_models
import marketplace_models
import control_room_models


class ControlMigrationTests(unittest.TestCase):
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
                    db.session.add(TravellerReview(name='Migration visitor',rating=5,comment='Preserved review'))
                    db.session.commit()
                    self.assertEqual(TravellerReview.query.one().rating,5)
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
