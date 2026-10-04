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
