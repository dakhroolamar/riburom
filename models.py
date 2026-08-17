"""SQLAlchemy models for Ri Burom Tours & Travels."""
from datetime import datetime
import json

from flask_sqlalchemy import SQLAlchemy


db = SQLAlchemy()

DEFAULT_MISSION = (
    "Come as a traveller. Leave with a connection. We seek to create "
    "journeys that bring travellers closer to Meghalaya's landscapes, "
    "culture, traditions, stories, and people."
)

DEFAULT_NATURE_TEXT = "Landscapes, forests, waterfalls, trails, and the natural character of Meghalaya."
DEFAULT_CULTURE_TEXT = "Living traditions, stories, food, heritage, and local perspectives."
DEFAULT_COMMUNITY_TEXT = "Travel that values local people, livelihoods, and respectful encounters."

ROLE_PERMISSIONS = {
    'owner': {
        'view_dashboard', 'manage_users', 'manage_tours', 'manage_media',
        'manage_about', 'manage_team', 'view_messages', 'manage_messages',
        'view_audit_log', 'manage_structure', 'view_customer_analytics', 'view_marketplace', 'manage_marketplace',
    },
    'content_manager': {
        'view_dashboard', 'manage_tours', 'manage_media', 'manage_about',
        'manage_team',
    },
    'enquiries': {
        'view_dashboard', 'view_messages', 'manage_messages',
    },
}
ROLE_LABELS = {
    'owner': 'Owner',
    'content_manager': 'Content Manager',
    'enquiries': 'Enquiries / Booking',
}


class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    full_name = db.Column(db.String(160), nullable=False)
    email = db.Column(db.String(254), unique=True, nullable=True, index=True)
    password_hash = db.Column(db.String(300), nullable=False)
    role = db.Column(db.String(40), nullable=False, default='enquiries')
    # Per-user permission overrides. NULL means use the legacy role defaults;
    # an explicit JSON list (including []) means use exactly those permissions.
    permissions_json = db.Column(db.Text, nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    last_login = db.Column(db.DateTime)

    @property
    def role_label(self):
        return ROLE_LABELS.get(self.role, self.role.replace('_', ' ').title())

    @property
    def permissions(self):
        # Owner remains full-access regardless of the custom checkbox list.
        if self.role == 'owner':
            return set().union(*ROLE_PERMISSIONS.values())

        # Existing accounts created before custom permissions were introduced
        # continue to use their established role defaults.
        if self.permissions_json is None:
            return set(ROLE_PERMISSIONS.get(self.role, set()))

        try:
            values = json.loads(self.permissions_json)
            if isinstance(values, list):
                return {str(value) for value in values if isinstance(value, str)}
        except (TypeError, ValueError, json.JSONDecodeError):
            pass
        return set()

    def has_permission(self, permission):
        return permission in self.permissions


class AuditLog(db.Model):
    __tablename__ = 'audit_logs'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True, index=True)
    username = db.Column(db.String(80), nullable=True)
    action = db.Column(db.String(100), nullable=False)
    target_type = db.Column(db.String(80), nullable=True)
    target_id = db.Column(db.String(80), nullable=True)
    details = db.Column(db.Text)
    ip_address = db.Column(db.String(64))
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)

    user = db.relationship('User', backref=db.backref('audit_logs', lazy=True))


class Package(db.Model):
    __tablename__ = 'packages'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    slug = db.Column(db.String(240), unique=True, nullable=False, default='tour')
    description = db.Column(db.Text, nullable=False)
    location = db.Column(db.String(200))
    duration = db.Column(db.String(100))
    price = db.Column(db.String(100))
    category = db.Column(db.String(100))
    best_season = db.Column(db.String(200))
    difficulty = db.Column(db.String(50))
    itinerary = db.Column(db.Text)
    included = db.Column(db.Text)
    excluded = db.Column(db.Text)
    image_file = db.Column(db.String(500))
    pdf_file = db.Column(db.String(500))
    published = db.Column(db.Boolean, default=True, nullable=False)
    featured = db.Column(db.Boolean, default=False, nullable=False)
    sort_order = db.Column(db.Integer, default=0, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Phase B: a Package can contain zero or more reusable marketplace Services
    # through PackageItem. This relationship does not change any existing
    # Package fields or public rendering behaviour.
    package_items = db.relationship(
        'PackageItem',
        back_populates='package',
        cascade='all, delete-orphan',
        passive_deletes=True,
        order_by='PackageItem.sort_order.asc(), PackageItem.id.asc()',
    )


class AboutContent(db.Model):
    __tablename__ = 'about_content'

    id = db.Column(db.Integer, primary_key=True)
    mission = db.Column(db.Text)
    hero_image = db.Column(db.String(500))


class SiteSettings(db.Model):
    """Singleton content/settings record for public-facing brand sections."""
    __tablename__ = 'site_settings'

    id = db.Column(db.Integer, primary_key=True)

    # Header / hero logos
    header_wordmark = db.Column(db.String(500))
    header_mark = db.Column(db.String(500))
    hero_logo = db.Column(db.String(500))
    header_wordmark_width = db.Column(db.Integer, default=125, nullable=False)
    header_mark_width = db.Column(db.Integer, default=48, nullable=False)
    header_logo_gap = db.Column(db.Integer, default=8, nullable=False)
    header_logo_position = db.Column(db.String(10), default='left', nullable=False)
    hero_logo_width = db.Column(db.Integer, default=300, nullable=False)

    # Global public-site typography controls. Admin UI remains fixed for usability.
    body_font = db.Column(db.String(40), default='inter', nullable=False)
    heading_font = db.Column(db.String(40), default='poppins', nullable=False)
    base_font_size = db.Column(db.Integer, default=16, nullable=False)
    heading_scale = db.Column(db.Integer, default=100, nullable=False)
    body_text_color = db.Column(db.String(20), default='#1f2937', nullable=False)
    heading_text_color = db.Column(db.String(20), default='#14532d', nullable=False)
    link_text_color = db.Column(db.String(20), default='#166534', nullable=False)

    # About: three core pillars
    nature_title = db.Column(db.String(200), default='Nature')
    nature_text = db.Column(db.Text, default=DEFAULT_NATURE_TEXT)
    culture_title = db.Column(db.String(200), default='Culture')
    culture_text = db.Column(db.Text, default=DEFAULT_CULTURE_TEXT)
    community_title = db.Column(db.String(200), default='Community')
    community_text = db.Column(db.Text, default=DEFAULT_COMMUNITY_TEXT)

    # Two additional editable About sections
    about_extra1_enabled = db.Column(db.Boolean, default=True, nullable=False)
    about_extra1_title = db.Column(db.String(200), default='')
    about_extra1_text = db.Column(db.Text, default='')
    about_extra2_enabled = db.Column(db.Boolean, default=True, nullable=False)
    about_extra2_title = db.Column(db.String(200), default='')
    about_extra2_text = db.Column(db.Text, default='')

    # Logo meaning / designer section
    logo_meaning_enabled = db.Column(db.Boolean, default=True, nullable=False)
    logo_meaning_title = db.Column(db.String(200), default='The Meaning Behind Our Logo')
    logo_meaning_text = db.Column(db.Text, default='')
    logo_meaning_pdf = db.Column(db.String(500))
    logo_designer_name = db.Column(db.String(200), default='')
    logo_designer_credit = db.Column(db.String(300), default='')

    # Featured external blog story
    blog_enabled = db.Column(db.Boolean, default=False, nullable=False)
    blog_show_home = db.Column(db.Boolean, default=False, nullable=False)
    blog_url = db.Column(db.String(1000), default='')
    blog_title = db.Column(db.String(300), default='')
    blog_excerpt = db.Column(db.Text, default='')
    blog_button_text = db.Column(db.String(120), default='Read the Story')
    blog_image = db.Column(db.String(500))

    # Footer / social / Instagram
    footer_business_name = db.Column(db.String(200), default='Ri Burom Tours & Travels')
    footer_tagline = db.Column(db.String(300), default='Meghalaya-rooted travel experiences.')
    footer_phone = db.Column(db.String(200), default='+91 8132863587 / 9863043620')
    footer_email = db.Column(db.String(254), default='riburomtoursandtravels@gmail.com')
    footer_address = db.Column(db.String(500), default='Meghalaya, India')
    footer_copyright = db.Column(db.String(300), default='© 2026 Ri Burom Tours & Travels. All rights reserved.')
    instagram_url = db.Column(db.String(1000), default='')
    instagram_label = db.Column(db.String(120), default='Follow us on Instagram')
    instagram_qr = db.Column(db.String(500))
    instagram_show_qr = db.Column(db.Boolean, default=True, nullable=False)
    public_config_json = db.Column(db.Text, default='')

    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class AboutSection(db.Model):
    __tablename__ = 'about_sections'

    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(50), unique=True, nullable=False, index=True)
    label = db.Column(db.String(200), nullable=False)
    enabled = db.Column(db.Boolean, default=True, nullable=False)
    sort_order = db.Column(db.Integer, default=0, nullable=False)


class TeamMember(db.Model):
    __tablename__ = 'team_members'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    position = db.Column(db.String(200), nullable=False)
    role_type = db.Column(db.String(40), nullable=False, default='team_member')
    sort_order = db.Column(db.Integer, default=0, nullable=False)
    description = db.Column(db.Text)
    photo_file = db.Column(db.String(500))


class Message(db.Model):
    __tablename__ = 'messages'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    email = db.Column(db.String(254), nullable=False, index=True)
    phone = db.Column(db.String(40))
    travel_dates = db.Column(db.String(120))
    travellers = db.Column(db.Integer)
    tour_interest = db.Column(db.String(200))
    message = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    is_read = db.Column(db.Boolean, default=False, nullable=False, index=True)


def seed_defaults():
    if db.session.get(AboutContent, 1) is None:
        db.session.add(AboutContent(id=1, mission=DEFAULT_MISSION))
        db.session.commit()
    if db.session.get(SiteSettings, 1) is None:
        db.session.add(SiteSettings(id=1))
        db.session.commit()

    defaults = [
        ('belief', 'What We Believe', True, 1),
        ('pillars', 'Nature | Culture | Community', True, 2),
        ('extra1', 'Additional Section 1', True, 3),
        ('extra2', 'Additional Section 2', True, 4),
        ('team', 'Our People', True, 5),
        ('logo_meaning', 'The Meaning Behind Our Logo', True, 6),
        ('blog', 'Stories from the Journey', True, 7),
    ]
    existing = {row.key for row in AboutSection.query.all()}
    created = False
    for key, label, enabled, order in defaults:
        if key not in existing:
            db.session.add(AboutSection(key=key, label=label, enabled=enabled, sort_order=order))
            created = True
    if created:
        db.session.commit()


# Import Phase A marketplace models after the legacy models and shared db object
# are defined. This registers their tables in the same SQLAlchemy metadata while
# keeping all legacy application entities independent.
import marketplace_models  # noqa: E402,F401
