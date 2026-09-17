"""Reusable CMS media; legacy site settings remain the content source of truth."""
from datetime import datetime
from models import db


class MediaAsset(db.Model):
    __tablename__ = 'cms_media_assets'
    id = db.Column(db.Integer, primary_key=True)
    path = db.Column(db.String(1000), nullable=False, unique=True)
    title = db.Column(db.String(240), nullable=False)
    alt = db.Column(db.String(500), nullable=False, default='')
    caption = db.Column(db.String(1000), nullable=False, default='')
    credit = db.Column(db.String(500), nullable=False, default='')
    width = db.Column(db.Integer)
    height = db.Column(db.Integer)
    byte_size = db.Column(db.Integer)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


class MediaCollection(db.Model):
    __tablename__ = 'cms_media_collections'
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(100), nullable=False, unique=True)
    title = db.Column(db.String(240), nullable=False)
    version = db.Column(db.Integer, nullable=False, default=1)
    __mapper_args__ = {'version_id_col': version}
    items = db.relationship('MediaCollectionItem', cascade='all, delete-orphan',
                            order_by='MediaCollectionItem.position', lazy='selectin')


class MediaCollectionItem(db.Model):
    __tablename__ = 'cms_media_collection_items'
    id = db.Column(db.Integer, primary_key=True)
    collection_id = db.Column(db.Integer, db.ForeignKey('cms_media_collections.id'), nullable=False, index=True)
    asset_id = db.Column(db.Integer, db.ForeignKey('cms_media_assets.id'), nullable=False, index=True)
    position = db.Column(db.Integer, nullable=False, default=0)
    focal_x = db.Column(db.Integer, nullable=False, default=50)
    focal_y = db.Column(db.Integer, nullable=False, default=50)
    organization = db.Column(db.String(240), nullable=False, default='')
    url = db.Column(db.String(1000), nullable=False, default='')
    label = db.Column(db.String(240), nullable=False, default='')
    visible = db.Column(db.Boolean, nullable=False, default=True)
    new_tab = db.Column(db.Boolean, nullable=False, default=False)
    asset = db.relationship(MediaAsset, lazy='joined')


class PageSection(db.Model):
    __tablename__ = 'cms_page_sections'
    id = db.Column(db.Integer, primary_key=True)
    page = db.Column(db.String(80), nullable=False)
    key = db.Column(db.String(80), nullable=False)
    settings = db.Column(db.JSON, nullable=False, default=dict)
    version = db.Column(db.Integer, nullable=False, default=1)
    __table_args__ = (db.UniqueConstraint('page', 'key', name='uq_cms_page_section'),)
    __mapper_args__ = {'version_id_col': version}
