"""Marketplace domain models for RI BUROM.

Phase A establishes provider and service foundations without coupling them to
legacy CMS, Package, Message, or User models.
"""
from datetime import datetime

from sqlalchemy.orm import validates

from models import db


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


class ProviderType(db.Model):
    __tablename__ = 'provider_types'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    slug = db.Column(db.String(140), unique=True, nullable=False, index=True)
    description = db.Column(db.Text, nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False, index=True)
    sort_order = db.Column(db.Integer, default=0, nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    provider_assignments = db.relationship(
        'ProviderTypeAssignment',
        back_populates='provider_type',
    )


class ServiceCategory(db.Model):
    __tablename__ = 'service_categories'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    slug = db.Column(db.String(140), unique=True, nullable=False, index=True)
    description = db.Column(db.Text, nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False, index=True)
    sort_order = db.Column(db.Integer, default=0, nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    services = db.relationship(
        'Service',
        back_populates='service_category',
    )


class Provider(db.Model):
    __tablename__ = 'providers'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    slug = db.Column(db.String(240), unique=True, nullable=False, index=True)
    description = db.Column(db.Text, nullable=True)
    email = db.Column(db.String(254), nullable=True)
    phone = db.Column(db.String(40), nullable=True)
    status = db.Column(db.String(40), nullable=False, default='DRAFT')
    is_active = db.Column(db.Boolean, default=True, nullable=False, index=True)
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

    @validates('status')
    def validate_status(self, key, value):
        if value not in SERVICE_STATUSES:
            raise ValueError(f'Invalid service status: {value!r}')
        return value
