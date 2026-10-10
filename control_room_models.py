"""Persistent operational workflows for the RI BUROM Control Room."""
from datetime import datetime
from models import db
from sqlalchemy.orm import deferred


class LeadWorkspace(db.Model):
    __tablename__ = 'control_leads'
    __table_args__ = (db.UniqueConstraint('source', 'source_id', name='uq_control_lead_source'),)
    id = db.Column(db.Integer, primary_key=True)
    source = db.Column(db.String(20), nullable=False)
    source_id = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(24), nullable=False, default='NEW')
    assigned_user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    notes = db.Column(db.Text, nullable=False, default='')
    budget = db.Column(db.Numeric(12, 2))
    call_at = db.Column(db.DateTime)
    next_action = deferred(db.Column(db.String(500), nullable=False, default='', server_default=''))
    follow_up = deferred(db.Column(db.Date))
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    assigned_user = db.relationship('User')


class Trip(db.Model):
    __tablename__ = 'control_trips'
    id = db.Column(db.Integer, primary_key=True)
    lead_id = db.Column(db.Integer, db.ForeignKey('control_leads.id'), unique=True)
    package_id = db.Column(db.Integer, db.ForeignKey('packages.id', name='fk_control_trips_package'))
    package = db.relationship('Package')
    name = db.Column(db.String(200), nullable=False)
    destination = db.Column(db.String(300), nullable=False)
    start_date = db.Column(db.Date, nullable=False, index=True)
    end_date = db.Column(db.Date, nullable=False)
    travellers = db.Column(db.Integer, nullable=False, default=1)
    status = db.Column(db.String(24), nullable=False, default='PLANNED', index=True)
    guide = db.Column(db.String(200), nullable=False, default='')
    driver = db.Column(db.String(200), nullable=False, default='')
    vehicle = db.Column(db.String(200), nullable=False, default='')
    itinerary_json = db.Column(db.Text, nullable=False, default='[]')
    accommodation_json = db.Column(db.Text, nullable=False, default='[]')
    checklist_json = db.Column(db.Text, nullable=False, default='{}')
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    lead = db.relationship('LeadWorkspace')


class TripUpdate(db.Model):
    __tablename__ = 'control_trip_updates'
    id = db.Column(db.Integer, primary_key=True)
    trip_id = db.Column(db.Integer, db.ForeignKey('control_trips.id'), nullable=False, index=True)
    author_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    message = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    author = db.relationship('User')


class Quote(db.Model):
    __tablename__ = 'control_quotes'
    id = db.Column(db.Integer, primary_key=True)
    lead_id = db.Column(db.Integer, db.ForeignKey('control_leads.id'), nullable=False, index=True)
    package_id = db.Column(db.Integer, db.ForeignKey('packages.id', name='fk_control_quotes_package'))
    package = db.relationship('Package')
    amount = db.Column(db.Numeric(12, 2), nullable=False)
    summary = db.Column(db.Text, nullable=False)
    valid_until = db.Column(db.Date, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    lead = db.relationship('LeadWorkspace')


class PartnerDocument(db.Model):
    __tablename__ = 'control_partner_documents'
    id = db.Column(db.Integer, primary_key=True)
    provider_id = db.Column(db.Integer, db.ForeignKey('providers.id'), nullable=False, index=True)
    kind = db.Column(db.String(80), nullable=False)
    file_name = db.Column(db.String(240), nullable=False)
    file_data = db.deferred(db.Column(db.LargeBinary, nullable=False))
    status = db.Column(db.String(24), nullable=False, default='UNDER_REVIEW')
    review_note = db.Column(db.Text, nullable=False, default='')
    expires_on = db.Column(db.Date)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    reviewed_by_id = db.Column(db.Integer, db.ForeignKey('users.id'))


class PartnerOperations(db.Model):
    __tablename__ = 'control_partner_operations'
    provider_id = db.Column(db.Integer, db.ForeignKey('providers.id', ondelete='CASCADE'), primary_key=True)
    contact_person = db.Column(db.String(200), nullable=False, default='', server_default='')
    location = db.Column(db.String(240), nullable=False, default='', server_default='')
    service_area = db.Column(db.String(500), nullable=False, default='', server_default='')
    notes = db.Column(db.Text, nullable=False, default='', server_default='')


class WebsiteRevision(db.Model):
    __tablename__ = 'control_website_revisions'
    id = db.Column(db.Integer, primary_key=True)
    page = db.Column(db.String(80), nullable=False, index=True)
    payload_json = db.Column(db.Text, nullable=False)
    base_token = db.Column(db.String(128), nullable=False)
    author_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    published_at = db.Column(db.DateTime)
    is_backup = db.Column(db.Boolean, nullable=False, default=False, server_default=db.false())


class ControlPreference(db.Model):
    __tablename__ = 'control_preferences'
    key = db.Column(db.String(80), primary_key=True)
    value_json = db.Column(db.Text, nullable=False, default='{}')


class Invoice(db.Model):
    __tablename__ = 'control_invoices'
    id = db.Column(db.Integer, primary_key=True)
    customer = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    amount = db.Column(db.Numeric(12, 2), nullable=False)
    due_date = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(24), nullable=False, default='ISSUED')
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


class AssetMetadata(db.Model):
    __tablename__ = 'control_asset_metadata'
    asset_id = db.Column(db.Integer, db.ForeignKey('cms_media_assets.id'), primary_key=True)
    location = db.Column(db.String(240), nullable=False, default='')
    category = db.Column(db.String(100), nullable=False, default='')
    tags = db.Column(db.String(1000), nullable=False, default='')


class LibraryVideo(db.Model):
    __tablename__ = 'control_library_videos'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(240), nullable=False)
    path = db.Column(db.String(1000), nullable=False)
    byte_size = db.Column(db.Integer, nullable=False)
    caption = db.Column(db.String(1000), nullable=False, default='')
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


class ServiceInventory(db.Model):
    __tablename__ = 'control_service_inventory'
    service_id = db.Column(db.Integer, db.ForeignKey('services.id'), primary_key=True)
    location = db.Column(db.String(240), nullable=False, default='')
    price = db.Column(db.Numeric(12, 2))
    available_slots = db.Column(db.Integer)
