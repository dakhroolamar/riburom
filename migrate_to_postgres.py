"""Copy the local SQLite data into DATABASE_URL (PostgreSQL recommended).

Usage:
    DATABASE_URL="postgresql://..." python3 migrate_to_postgres.py

The source is read with sqlite3 directly so this script can migrate databases
from older Ri Burom builds before the new columns existed. Existing target rows
matched by primary key are skipped.
"""
import os
import sqlite3
import sys
from datetime import datetime


def rows_as_dicts(conn, table):
    conn.row_factory = sqlite3.Row
    return [dict(row) for row in conn.execute(f'SELECT * FROM {table}').fetchall()]


BASE_DIR = os.path.abspath(os.path.dirname(__file__))
sqlite_path = os.path.join(BASE_DIR, 'riburom.db')
target_url = os.environ.get('DATABASE_URL')
if not target_url:
    sys.exit('DATABASE_URL is not set.')
if target_url.startswith('postgres://'):
    target_url = target_url.replace('postgres://', 'postgresql://', 1)
if not os.path.exists(sqlite_path):
    sys.exit(f'No local riburom.db found at {sqlite_path}.')

source = sqlite3.connect(sqlite_path)
packages = rows_as_dicts(source, 'packages')
about = rows_as_dicts(source, 'about_content')
team = rows_as_dicts(source, 'team_members')
about_sections = rows_as_dicts(source, 'about_sections') if 'about_sections' in {r[0] for r in source.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()} else []
messages = rows_as_dicts(source, 'messages')
users = rows_as_dicts(source, 'users') if 'users' in {r[0] for r in source.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()} else []
audits = rows_as_dicts(source, 'audit_logs') if 'audit_logs' in {r[0] for r in source.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()} else []
site_settings = rows_as_dicts(source, 'site_settings') if 'site_settings' in {r[0] for r in source.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()} else []
source.close()

from flask import Flask
from models import db, Package, AboutContent, AboutSection, SiteSettings, TeamMember, Message, User, AuditLog

# Importing Flask-Migrate is unnecessary for the one-time data copy.
target_app = Flask(__name__ + '_target')
target_app.config['SQLALCHEMY_DATABASE_URI'] = target_url
target_app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(target_app)


def slugify(value):
    import re
    value = re.sub(r'[^a-zA-Z0-9\s-]', '', value or '').strip().lower()
    value = re.sub(r'[\s_-]+', '-', value)
    return value.strip('-') or 'tour'


def make_unique_slug(title, used):
    base = slugify(title)
    slug = base
    i = 2
    while slug in used:
        slug = f'{base}-{i}'
        i += 1
    used.add(slug)
    return slug


with target_app.app_context():
    db.create_all()
    added = skipped = 0
    used_slugs = {row[0] for row in Package.query.with_entities(Package.slug).all() if row[0]}

    for row in packages:
        if db.session.get(Package, row['id']) is not None:
            skipped += 1
            continue
        created = row.get('created_at') or datetime.utcnow()
        pkg = Package(
            id=row['id'],
            title=row.get('title') or 'Untitled Tour',
            slug=make_unique_slug(row.get('title') or 'tour', used_slugs),
            description=row.get('description') or '',
            location=row.get('location'),
            duration=row.get('duration'),
            price=row.get('price'),
            category=row.get('category'),
            best_season=row.get('best_season'),
            difficulty=row.get('difficulty'),
            itinerary=row.get('itinerary'),
            included=row.get('included'),
            excluded=row.get('excluded'),
            image_file=row.get('image_file'),
            pdf_file=row.get('pdf_file'),
            published=True if row.get('published') is None else bool(row['published']),
            featured=False if row.get('featured') is None else bool(row['featured']),
            sort_order=row.get('sort_order') or row['id'],
            created_at=created,
            updated_at=row.get('updated_at') or created,
        )
        db.session.add(pkg)
        added += 1

    for row in about:
        if db.session.get(AboutContent, row['id']) is None:
            db.session.add(AboutContent(id=row['id'], mission=row.get('mission'), hero_image=row.get('hero_image')))
            added += 1
        else:
            skipped += 1

    for row in about_sections:
        if db.session.get(AboutSection, row['id']) is None:
            db.session.add(AboutSection(id=row['id'], key=row.get('key') or f'section_{row['id']}', label=row.get('label') or 'About Section', enabled=True if row.get('enabled') is None else bool(row['enabled']), sort_order=row.get('sort_order') or row['id']))
            added += 1
        else:
            skipped += 1

    for row in site_settings:
        if db.session.get(SiteSettings, row['id']) is None:
            fields = {column.name for column in SiteSettings.__table__.columns}
            payload = {key: value for key, value in row.items() if key in fields}
            db.session.add(SiteSettings(**payload))
            added += 1
        else:
            skipped += 1

    for row in team:
        if db.session.get(TeamMember, row['id']) is None:
            db.session.add(TeamMember(id=row['id'], name=row['name'], position=row['position'], role_type=row.get('role_type') or 'team_member', sort_order=row.get('sort_order') or row['id'], description=row.get('description'), photo_file=row.get('photo_file')))
            added += 1
        else:
            skipped += 1

    for row in messages:
        if db.session.get(Message, row['id']) is None:
            db.session.add(Message(id=row['id'], name=row['name'], email=row['email'], phone=row.get('phone'), travel_dates=row.get('travel_dates'), travellers=row.get('travellers'), tour_interest=row.get('tour_interest'), message=row['message'], created_at=row.get('created_at') or datetime.utcnow(), is_read=bool(row.get('is_read'))))
            added += 1
        else:
            skipped += 1

    for row in users:
        if db.session.get(User, row['id']) is None:
            db.session.add(User(id=row['id'], username=row['username'], full_name=row['full_name'], email=row.get('email'), password_hash=row['password_hash'], role=row.get('role') or 'enquiries', is_active=True if row.get('is_active') is None else bool(row['is_active']), created_at=row.get('created_at') or datetime.utcnow(), updated_at=row.get('updated_at') or row.get('created_at') or datetime.utcnow(), last_login=row.get('last_login')))
            added += 1
        else:
            skipped += 1

    for row in audits:
        if db.session.get(AuditLog, row['id']) is None:
            db.session.add(AuditLog(id=row['id'], user_id=row.get('user_id'), username=row.get('username'), action=row['action'], target_type=row.get('target_type'), target_id=row.get('target_id'), details=row.get('details'), ip_address=row.get('ip_address'), created_at=row.get('created_at') or datetime.utcnow()))
            added += 1
        else:
            skipped += 1

    db.session.commit()

print(f'Migration complete: {added} row(s) added, {skipped} row(s) already present/skipped.')
print('This script copies database records only. Local image/PDF files still need persistent storage or re-uploading.')
