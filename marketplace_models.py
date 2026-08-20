"""Marketplace domain models for RI BUROM.

Phase A establishes provider and service foundations without coupling them to
legacy CMS, Package, Message, or User models.

Phase B intentionally introduces PackageItem as the first bridge between the
legacy Package aggregate and reusable marketplace Services.

Phase C introduces independent MarketplaceInquiry records so service requests
do not enter the generic website contact/enquiry workflow.
"""
from datetime import datetime

from sqlalchemy.orm import validates

from models import db, Package


PROVIDER_STATUSES = {
    'DRAFT',
    'SUBMITTED',
    'UNDER_REVIEW',
    'VERIFIED',
    'APPROVED',
    'PUBLISHED',
    'ACTIVE',
    'REJECTED',
    'SUSPENDED',
    'INACTIVE',
    'ARCHIVED',
}

SERVICE_STATUSES = {
    'DRAFT',
    'PUBLISHED',
    'ACTIVE',
    'INACTIVE',
    'ARCHIVED',
}

INQUIRY_STATUSES = {
    'NEW',
    'CONTACTED',
    'IN_PROGRESS',
    'QUOTED',
    'CONFIRMED',
    'DECLINED',
    'CLOSED',
}


class ProviderType(db.Model):
    __tablename__ = 'provider_types'
    __table_args__ = (
        db.Index('ix_provider_types_is_active', 'is_active'),
        db.Index('ix_provider_types_sort_order', 'sort_order'),
    )

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    slug = db.Column(db.String(140), unique=True, nullable=False)
    description = db.Column(db.Text, nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    sort_order = db.Column(db.Integer, default=0, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    provider_assignments = db.relationship(
        'ProviderTypeAssignment',
        back_populates='provider_type',
    )


class ServiceCategory(db.Model):
    __tablename__ = 'service_categories'
    __table_args__ = (
        db.Index('ix_service_categories_is_active', 'is_active'),
        db.Index('ix_service_categories_sort_order', 'sort_order'),
    )

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    slug = db.Column(db.String(140), unique=True, nullable=False)
    description = db.Column(db.Text, nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    sort_order = db.Column(db.Integer, default=0, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    services = db.relationship(
        'Service',
        back_populates='service_category',
    )


class Provider(db.Model):
    __tablename__ = 'providers'
    __table_args__ = (
        db.Index('ix_providers_is_active', 'is_active'),
    )

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    slug = db.Column(db.String(240), unique=True, nullable=False)
    description = db.Column(db.Text, nullable=True)
    image_url = db.Column(db.String(500), nullable=True)
    email = db.Column(db.String(254), nullable=True)
    phone = db.Column(db.String(40), nullable=True)
    status = db.Column(db.String(40), nullable=False, default='DRAFT')
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    provider_type_assignments = db.relationship(
        'ProviderTypeAssignment',
        back_populates='provider',
    )
    services = db.relationship(
        'Service',
        back_populates='provider',
    )

    @validates('status')
    def validate_status(self, key, value):
        if value not in PROVIDER_STATUSES:
            raise ValueError(f'Invalid provider status: {value!r}')
        return value


class ProviderTypeAssignment(db.Model):
    __tablename__ = 'provider_type_assignments'
    __table_args__ = (
        db.UniqueConstraint(
            'provider_id',
            'provider_type_id',
            name='uq_provider_type_assignment',
        ),
        db.Index('ix_provider_type_assignments_provider_id', 'provider_id'),
        db.Index('ix_provider_type_assignments_provider_type_id', 'provider_type_id'),
    )

    id = db.Column(db.Integer, primary_key=True)
    provider_id = db.Column(
        db.Integer,
        db.ForeignKey('providers.id'),
        nullable=False,
    )
    provider_type_id = db.Column(
        db.Integer,
        db.ForeignKey('provider_types.id'),
        nullable=False,
    )
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    provider = db.relationship(
        'Provider',
        back_populates='provider_type_assignments',
    )
    provider_type = db.relationship(
        'ProviderType',
        back_populates='provider_assignments',
    )


class Service(db.Model):
    __tablename__ = 'services'
    __table_args__ = (
        db.UniqueConstraint(
            'provider_id',
            'slug',
            name='uq_service_provider_slug',
        ),
        db.Index('ix_services_provider_id', 'provider_id'),
        db.Index('ix_services_category_id', 'category_id'),
        db.Index('ix_services_status', 'status'),
    )

    id = db.Column(db.Integer, primary_key=True)
    provider_id = db.Column(
        db.Integer,
        db.ForeignKey('providers.id'),
        nullable=False,
    )
    category_id = db.Column(
        db.Integer,
        db.ForeignKey('service_categories.id'),
        nullable=False,
    )
    name = db.Column(db.String(200), nullable=False)
    slug = db.Column(db.String(240), nullable=False)
    description = db.Column(db.Text, nullable=True)
    image_url = db.Column(db.String(500), nullable=True)
    status = db.Column(db.String(40), nullable=False, default='DRAFT')
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    provider = db.relationship(
        'Provider',
        back_populates='services',
    )
    service_category = db.relationship(
        'ServiceCategory',
        back_populates='services',
    )
    package_items = db.relationship(
        'PackageItem',
        back_populates='service',
        passive_deletes=True,
    )

    @validates('status')
    def validate_status(self, key, value):
        if value not in SERVICE_STATUSES:
            raise ValueError(f'Invalid service status: {value!r}')
        return value


class PackageItem(db.Model):
    """Bridge between a curated Package and a reusable marketplace Service."""

    __tablename__ = 'package_items'
    __table_args__ = (
        db.UniqueConstraint(
            'package_id',
            'service_id',
            name='uq_package_item_package_service',
        ),
        db.Index('ix_package_items_package_sort', 'package_id', 'sort_order'),
        db.Index('ix_package_items_service_id', 'service_id'),
    )

    id = db.Column(db.Integer, primary_key=True)
    package_id = db.Column(
        db.Integer,
        db.ForeignKey('packages.id', ondelete='CASCADE'),
        nullable=False,
    )
    service_id = db.Column(
        db.Integer,
        db.ForeignKey('services.id', ondelete='RESTRICT'),
        nullable=False,
    )
    sort_order = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    package = db.relationship(
        Package,
        back_populates='package_items',
    )
    service = db.relationship(
        'Service',
        back_populates='package_items',
    )


class MarketplaceInquiry(db.Model):
    """Structured customer request tied to a marketplace service."""

    __tablename__ = 'marketplace_inquiries'
    __table_args__ = (
        db.Index('ix_marketplace_inquiries_email', 'email'),
        db.Index('ix_marketplace_inquiries_status', 'status'),
        db.Index('ix_marketplace_inquiries_created_at', 'created_at'),
        db.Index('ix_marketplace_inquiries_provider_id', 'provider_id'),
        db.Index('ix_marketplace_inquiries_service_id', 'service_id'),
    )

    id = db.Column(db.Integer, primary_key=True)

    provider_id = db.Column(
        db.Integer,
        db.ForeignKey('providers.id', ondelete='SET NULL'),
        nullable=True,
    )
    service_id = db.Column(
        db.Integer,
        db.ForeignKey('services.id', ondelete='SET NULL'),
        nullable=True,
    )

    provider_name = db.Column(db.String(200), nullable=False)
    service_name = db.Column(db.String(200), nullable=False)
    category_name = db.Column(db.String(120), nullable=False)

    name = db.Column(db.String(200), nullable=False)
    email = db.Column(db.String(254), nullable=False)
    phone = db.Column(db.String(40), nullable=True)

    travel_date = db.Column(db.String(120), nullable=True)
    return_date = db.Column(db.String(120), nullable=True)
    travellers = db.Column(db.Integer, nullable=True)
    pickup_location = db.Column(db.String(300), nullable=True)
    drop_location = db.Column(db.String(300), nullable=True)
    check_in = db.Column(db.String(120), nullable=True)
    check_out = db.Column(db.String(120), nullable=True)
    rooms = db.Column(db.Integer, nullable=True)
    nights = db.Column(db.Integer, nullable=True)
    language = db.Column(db.String(120), nullable=True)
    duration = db.Column(db.String(120), nullable=True)
    requirements = db.Column(db.Text, nullable=True)

    status = db.Column(db.String(40), nullable=False, default='NEW')
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    provider = db.relationship('Provider', backref=db.backref('marketplace_inquiries', lazy=True))
    service = db.relationship('Service', backref=db.backref('marketplace_inquiries', lazy=True))

    @validates('status')
    def validate_status(self, key, value):
        if value not in INQUIRY_STATUSES:
            raise ValueError(f'Invalid marketplace inquiry status: {value!r}')
        return value
