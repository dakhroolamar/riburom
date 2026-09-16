import io
import json
import os
import re
from collections import Counter
from datetime import datetime, timedelta
from functools import wraps
from html import escape
from urllib.parse import urljoin, urlparse, quote

from dotenv import load_dotenv
from flask import (
    Flask, render_template, request, redirect, url_for,
    session, flash, send_from_directory, abort, has_request_context, Response,
)
from sqlalchemy import inspect, func, desc
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_migrate import Migrate
from flask_wtf.csrf import CSRFError, CSRFProtect
from werkzeug.security import check_password_hash, generate_password_hash
import qrcode

load_dotenv()

from models import (
    db, Package, AboutContent, AboutSection, SiteSettings, TeamMember, Message,
    User, AuditLog, ROLE_PERMISSIONS, ROLE_LABELS, seed_defaults,
)
from storage import (
    save_image, save_pdf, save_generated_png, delete_media, allowed_file, imgsrc,
    STORAGE_BACKEND, ALLOWED_IMAGE_EXTENSIONS,
)
from marketplace_models import Provider, Service

app = Flask(__name__)
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
APP_ENV = (os.environ.get('APP_ENV') or os.environ.get('ENVIRONMENT') or 'production').lower()
IS_DEVELOPMENT = APP_ENV in {'development', 'dev', 'testing'}
IS_PRODUCTION = not IS_DEVELOPMENT

secret_key = os.environ.get('SECRET_KEY')
initial_password_hash = os.environ.get('ADMIN_PASSWORD_HASH')
legacy_dev_password = os.environ.get('ADMIN_PASSWORD')
initial_owner_username = os.environ.get('INITIAL_OWNER_USERNAME', 'owner').strip().lower() or 'owner'
initial_owner_name = os.environ.get('INITIAL_OWNER_NAME', 'RI BUROM Owner').strip() or 'RI BUROM Owner'
initial_owner_email = (os.environ.get('INITIAL_OWNER_EMAIL') or '').strip().lower() or None

if IS_PRODUCTION and not secret_key:
    raise RuntimeError('SECRET_KEY must be configured. Set APP_ENV=development only for local development.')
if IS_PRODUCTION and not initial_password_hash:
    raise RuntimeError('ADMIN_PASSWORD_HASH must be configured for the initial Owner account.')

# Development fallback is deliberately explicit. There is no production fallback.
if not secret_key and IS_DEVELOPMENT:
    secret_key = 'local-development-only-change-me'
if not initial_password_hash and IS_DEVELOPMENT and legacy_dev_password:
    initial_password_hash = generate_password_hash(legacy_dev_password)

app.config['SECRET_KEY'] = secret_key
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
app.config['UPLOAD_FOLDER'] = os.path.join(BASE_DIR, 'static')
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SECURE'] = IS_PRODUCTION
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['RATELIMIT_STORAGE_URI'] = os.environ.get('RATELIMIT_STORAGE_URI', 'memory://')

# --- Database ---
database_url = os.environ.get('DATABASE_URL')

if os.environ.get('TESTING') == '1':
    if not database_url:
        raise RuntimeError(
            'TESTING requires DATABASE_URL to be configured to an isolated SQLite database.'
        )

    normalized_database_url = database_url.lower()
    if normalized_database_url.startswith(('postgres://', 'postgresql://')):
        raise RuntimeError(
            'TESTING cannot use a PostgreSQL database. '
            'Tests must use an isolated SQLite database.'
        )

    if not normalized_database_url.startswith('sqlite:'):
        raise RuntimeError(
            'TESTING requires an isolated SQLite DATABASE_URL.'
        )
if database_url:
    if database_url.startswith('postgres://'):
        database_url = database_url.replace('postgres://', 'postgresql://', 1)
else:
    database_url = 'sqlite:///' + os.path.join(BASE_DIR, 'riburom.db')
app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)
Migrate(app, db)
csrf = CSRFProtect(app)
limiter = Limiter(key_func=get_remote_address, storage_uri=app.config['RATELIMIT_STORAGE_URI'], default_limits=[])
limiter.init_app(app)
app.jinja_env.filters['imgsrc'] = imgsrc


# Permission catalog shown to the Owner when creating/editing a user.
# The keys are deliberately tied to the authorization checks already used by
# the application, so the UI cannot grant a permission that the application
# does not understand.
PERMISSION_LABELS = {
    'view_dashboard': 'View Control Room / Dashboard',
    'manage_tours': 'Manage Experiences / Tours',
    'manage_media': 'Manage Photos, PDFs & Branding',
    'manage_about': 'Manage About Us / Website Content',
    'manage_team': 'Manage Team Members',
    'view_messages': 'View Contact Enquiries',
    'manage_messages': 'Manage Contact Enquiries',
    'view_customer_analytics': 'View Customer Analytics',
    'view_audit_log': 'View Recent Activity / Audit Log',
    'manage_structure': 'Manage Page Structure / Ordering',
    'view_marketplace': 'View Marketplace Providers & Services',
    'manage_marketplace': 'Manage Marketplace Providers & Services',
}
PERMISSION_KEYS = tuple(PERMISSION_LABELS.keys())


PUBLIC_SITE_DEFAULTS = {
    'content': {
        'site_title': 'Ri Burom Tours & Travels | Meghalaya Experiences',
        'meta_description': 'Ri Burom Tours & Travels creates Meghalaya-rooted journeys connecting travellers with landscapes, culture, traditions, stories, and communities.',
        'og_title': 'Ri Burom Tours & Travels',
        'og_description': 'Meghalaya-rooted travel experiences shaped by nature, culture, community, and hospitality.',
        'nav_home': 'Home', 'nav_tours': 'Explore All Tours', 'nav_about': 'About Us', 'nav_contact': 'Contact Us', 'nav_login': 'Login',
        'mobile_tours': 'Tours', 'mobile_about': 'About', 'mobile_contact': 'Contact', 'mobile_menu': 'Menu',
        'hero_eyebrow': 'Nature • Culture • Adventure • Community',
        'hero_title': 'Meghalaya, beyond the ordinary.',
        'hero_subtitle': 'Meghalaya-rooted journeys that bring travellers closer to the landscapes, stories, traditions, and people that make the state what it is.',
        'hero_primary_button': 'Explore Experiences', 'hero_secondary_button': 'Plan Your Journey',
        'home_about_eyebrow': 'About RI BUROM', 'home_about_title': 'Travel with a connection to place.',
        'home_about_text': 'We create thoughtfully designed experiences across Meghalaya that connect travellers with nature, culture, local communities, and the everyday stories behind the destination.',
        'home_tours_eyebrow': 'Explore', 'home_tours_title': 'Signature Experiences', 'home_tours_all': 'View all experiences →',
        'home_tour_button': 'View Experience', 'home_tours_empty': 'New adventure experiences are being curated right now. Check back soon!',
        'home_why_eyebrow': 'Why RI BUROM?', 'home_why_title': 'More than a package. A way to experience Meghalaya.',
        'home_why_text': 'Our approach is rooted in the place itself—its landscapes, living traditions, communities, and hospitality.',
        'why1_title': 'Experience Meghalaya', 'why1_text': 'Go beyond checklists and explore the character of the destination.',
        'why2_title': 'Local Connection', 'why2_text': 'Meet people, hear stories, and discover places through local perspectives.',
        'why3_title': 'Culture with Respect', 'why3_text': 'Experience living culture as something to understand, not merely photograph.',
        'why4_title': 'Responsible Travel', 'why4_text': 'Support local livelihoods while treating landscapes and communities with care.',
        'blog_eyebrow': 'Stories from the Journey',
        'contact_title': 'Plan Your Journey', 'contact_text': 'Tell us what you are looking for and we will help you plan the next step.',
        'form_name': 'Your Name', 'form_email': 'Email Address', 'form_phone': 'WhatsApp / Phone', 'form_travellers': 'Number of Travellers',
        'form_dates': 'Preferred Travel Dates', 'form_tour': 'Tour / Experience', 'form_message': 'Message', 'form_submit': 'Send Enquiry',
        'form_dates_placeholder': 'e.g. 12–15 October 2026', 'form_tour_placeholder': 'What are you interested in?',
        'whatsapp_text': 'Chat on WhatsApp', 'whatsapp_message': 'Hello RI BUROM, I would like to plan a trip to Meghalaya.',
        'tours_page_title': 'All Experiences - Ri Burom Tours & Travels', 'tours_page_eyebrow': 'Explore', 'tours_page_heading': 'All Experiences',
        'tours_page_intro': 'Discover our published experiences across Meghalaya.', 'tours_empty': 'New experiences are being curated right now. Check back soon!',
        'tours_view_button': 'View Experience', 'tours_price_prefix': 'From',
        'about_page_title': 'About Us - Ri Burom Tours & Travels', 'about_page_eyebrow': 'Our Story',
        'about_page_intro': 'A Meghalaya-rooted travel initiative built around connection, culture, community and meaningful experiences.',
        'about_team_empty': 'Our team profiles will appear here as they are added through the Control Room.',
        'about_logo_pdf': 'Read the complete logo concept PDF', 'about_logo_created': 'Logo created by',
        'tour_detail_overview': 'Overview', 'tour_detail_itinerary': 'Itinerary', 'tour_detail_included': "What's Included",
        'tour_detail_excluded': "What's Not Included", 'tour_detail_starting': 'Starting from', 'tour_detail_best_season': 'Best Season',
        'tour_detail_whatsapp': 'Plan This Experience on WhatsApp', 'tour_detail_enquiry': 'Send an Enquiry', 'tour_detail_pdf': 'View Detailed PDF',
        'tour_detail_category_fallback': 'Meghalaya Experience',
        'footer_explore': 'Explore', 'footer_contact': 'Contact', 'footer_qr': 'Scan to follow us on Instagram',
    },
    'theme': {
        'primary_color': '#166534', 'secondary_color': '#92400e', 'accent_color': '#d97706', 'link_color': '#166534',
        'header_bg_color': '#ffffff', 'footer_bg_color': '#78350f', 'button_radius': 10, 'section_spacing': 64,
        'hero_overlay_opacity': 55, 'whatsapp_visible': True, 'show_login_button': True,
    },
    'home': {
        'order': ['hero', 'about', 'tours', 'why', 'blog', 'contact'],
        'visibility': {'hero': True, 'about': True, 'tours': True, 'why': True, 'blog': True, 'contact': True},
    },
}


def _deep_merge(base, incoming):
    if isinstance(base, dict) and isinstance(incoming, dict):
        out = dict(base)
        for key, value in incoming.items():
            out[key] = _deep_merge(out[key], value) if key in out else value
        return out
    return incoming if incoming is not None else base


def get_public_config(settings=None):
    settings = settings or get_site_settings()
    try:
        raw = json.loads(settings.public_config_json or '{}') if settings.public_config_json else {}
    except (TypeError, ValueError, json.JSONDecodeError):
        raw = {}
    return _deep_merge(PUBLIC_SITE_DEFAULTS, raw)


def _safe_hex(value, default):
    value = (value or '').strip()
    return value if re.fullmatch(r'#[0-9a-fA-F]{6}', value) else default


FONT_OPTIONS = {
    'inter': ('Inter', 'Inter, Arial, sans-serif'),
    'poppins': ('Poppins', 'Poppins, Arial, sans-serif'),
    'montserrat': ('Montserrat', 'Montserrat, Arial, sans-serif'),
    'nunito': ('Nunito', 'Nunito, Arial, sans-serif'),
    'lora': ('Lora', 'Lora, Georgia, serif'),
    'merriweather': ('Merriweather', 'Merriweather, Georgia, serif'),
    'georgia': ('Georgia', 'Georgia, serif'),
    'arial': ('Arial', 'Arial, Helvetica, sans-serif'),
    'times': ('Times New Roman', 'Times New Roman, Times, serif'),
}

FONT_GOOGLE_FAMILIES = {
    'inter': 'Inter:wght@400;500;600;700;800',
    'poppins': 'Poppins:wght@400;500;600;700;800',
    'montserrat': 'Montserrat:wght@400;500;600;700;800',
    'nunito': 'Nunito:wght@400;600;700;800',
    'lora': 'Lora:wght@400;500;600;700',
    'merriweather': 'Merriweather:wght@400;700;900',
}


# ------------------------------------------------------------
# Helpers
# ------------------------------------------------------------
def slugify(value: str) -> str:
    value = re.sub(r'[^a-zA-Z0-9\s-]', '', value or '').strip().lower()
    value = re.sub(r'[\s_-]+', '-', value)
    return value.strip('-') or 'tour'


def unique_slug(title: str, current_id=None) -> str:
    base = slugify(title)
    slug = base
    counter = 2
    while True:
        query = Package.query.filter_by(slug=slug)
        if current_id is not None:
            query = query.filter(Package.id != current_id)
        if query.first() is None:
            return slug
        slug = f'{base}-{counter}'
        counter += 1


def valid_local_redirect(target: str | None) -> bool:
    if not target:
        return False
    ref = urlparse(request.host_url)
    test = urlparse(urljoin(request.host_url, target))
    return test.scheme in ('http', 'https') and test.netloc == ref.netloc


def get_site_settings():
    settings = db.session.get(SiteSettings, 1)
    if settings is None:
        settings = SiteSettings(id=1)
        db.session.add(settings)
        db.session.commit()
    return settings


def valid_external_url(value: str | None) -> bool:
    if not value:
        return False
    try:
        parsed = urlparse(value.strip())
    except ValueError:
        return False
    return parsed.scheme in {'http', 'https'} and bool(parsed.netloc)


def clamp_int(raw_value, default, minimum, maximum):
    try:
        value = int(raw_value)
    except (TypeError, ValueError):
        return default
    return max(minimum, min(maximum, value))


def generate_instagram_qr(url: str):
    qr = qrcode.QRCode(version=None, error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=8, border=4)
    qr.add_data(url)
    qr.make(fit=True)
    image = qr.make_image(fill_color='black', back_color='white')
    buf = io.BytesIO()
    image.save(buf, format='PNG')
    return save_generated_png(buf.getvalue())


def whatsapp_url(message: str) -> str:
    phone = os.environ.get('WHATSAPP_PHONE', '918132863587')
    return f'https://wa.me/{phone}?text={quote(message)}'


@app.context_processor
def inject_helpers():
    settings = get_site_settings()
    body_key = settings.body_font if settings.body_font in FONT_OPTIONS else 'inter'
    heading_key = settings.heading_font if settings.heading_font in FONT_OPTIONS else 'poppins'
    public = get_public_config(settings)
    # Precompute a {section_key: css_order_number} map server-side so the
    # template can set `order:` directly with zero client-side JS involved.
    # Any section missing from a corrupted/old order list still gets a
    # deterministic (if arbitrary) position instead of breaking rendering.
    home_order_list = public.get('home', {}).get('order') or []
    home_order_index = {key: i for i, key in enumerate(home_order_list)}
    for fallback_key in ('hero', 'about', 'tours', 'why', 'blog', 'contact'):
        home_order_index.setdefault(fallback_key, len(home_order_index))
    return {
        'whatsapp_url': whatsapp_url,
        'current_user': get_current_user(),
        'role_labels': ROLE_LABELS,
        'site_settings': settings,
        'font_options': FONT_OPTIONS,
        'body_font_css': FONT_OPTIONS[body_key][1],
        'heading_font_css': FONT_OPTIONS[heading_key][1],
        'google_font_families': [FONT_GOOGLE_FAMILIES[k] for k in (body_key, heading_key) if k in FONT_GOOGLE_FAMILIES],
        'public': public,
        'home_order_index': home_order_index,
    }


def add_audit(action, target_type=None, target_id=None, details=None):
    """Queue an audit event from either a request or application context.

    Startup/migration actions run outside an HTTP request, so Flask's session
    and remote-address helpers are not available there. Those events are
    intentionally recorded as system actions with no user/IP attached.
    """
    user = get_current_user() if has_request_context() else None
    ip_address = get_remote_address() if has_request_context() else None
    db.session.add(AuditLog(
        user_id=user.id if user else None,
        username=user.username if user else None,
        action=action,
        target_type=target_type,
        target_id=str(target_id) if target_id is not None else None,
        details=details,
        ip_address=ip_address,
    ))


def get_current_user():
    user_id = session.get('user_id')
    if not user_id:
        return None
    user = db.session.get(User, user_id)
    if user is None or not user.is_active:
        session.clear()
        return None
    return user


def _add_column_if_missing(table, column, ddl):
    from sqlalchemy import inspect, text
    inspector = inspect(db.engine)
    if table not in inspector.get_table_names():
        return
    existing = {c['name'] for c in inspector.get_columns(table)}
    if column in existing:
        return
    with db.engine.begin() as conn:
        if db.engine.dialect.name == 'postgresql':
            conn.execute(text(f'ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {column} {ddl}'))
        else:
            conn.execute(text(f'ALTER TABLE {table} ADD COLUMN {column} {ddl}'))


def _run_legacy_migrations():
    from sqlalchemy import text, inspect
    # Per-user permission overrides. Existing rows remain NULL and therefore
    # continue using the legacy role defaults until an Owner explicitly edits them.
    _add_column_if_missing('users', 'permissions_json', 'TEXT')
    _add_column_if_missing('site_settings', 'header_logo_position', "VARCHAR(10) DEFAULT 'left'")
    _add_column_if_missing('site_settings', 'body_font', "VARCHAR(40) DEFAULT 'inter'")
    _add_column_if_missing('site_settings', 'heading_font', "VARCHAR(40) DEFAULT 'poppins'")
    _add_column_if_missing('site_settings', 'base_font_size', 'INTEGER DEFAULT 16')
    _add_column_if_missing('site_settings', 'heading_scale', 'INTEGER DEFAULT 100')
    _add_column_if_missing('site_settings', 'body_text_color', "VARCHAR(20) DEFAULT '#1f2937'")
    _add_column_if_missing('site_settings', 'heading_text_color', "VARCHAR(20) DEFAULT '#14532d'")
    _add_column_if_missing('site_settings', 'link_text_color', "VARCHAR(20) DEFAULT '#166534'")
    _add_column_if_missing('about_content', 'hero_image', 'VARCHAR(500)')
    _add_column_if_missing('site_settings', 'public_config_json', 'TEXT')
    fields = [
        ('slug', 'VARCHAR(240)'), ('location', 'VARCHAR(200)'), ('duration', 'VARCHAR(100)'),
        ('price', 'VARCHAR(100)'), ('category', 'VARCHAR(100)'), ('best_season', 'VARCHAR(200)'),
        ('difficulty', 'VARCHAR(50)'), ('itinerary', 'TEXT'), ('included', 'TEXT'), ('excluded', 'TEXT'),
        ('published', 'BOOLEAN'), ('featured', 'BOOLEAN'), ('sort_order', 'INTEGER'),
        ('created_at', 'TIMESTAMP'), ('updated_at', 'TIMESTAMP'),
    ]
    for column, ddl in fields:
        _add_column_if_missing('packages', column, ddl)
    for column, ddl in [('phone', 'VARCHAR(40)'), ('travel_dates', 'VARCHAR(120)'), ('travellers', 'INTEGER'), ('tour_interest', 'VARCHAR(200)')]:
        _add_column_if_missing('messages', column, ddl)
    # Lightweight indexes for inquiry analytics. Safe on repeated deployments.
    with db.engine.begin() as conn:
        if db.engine.dialect.name == 'postgresql':
            conn.execute(text('CREATE INDEX IF NOT EXISTS ix_messages_created_at ON messages (created_at)'))
            conn.execute(text('CREATE INDEX IF NOT EXISTS ix_messages_email_lower ON messages (LOWER(email))'))
        else:
            try:
                conn.execute(text('CREATE INDEX IF NOT EXISTS ix_messages_created_at ON messages (created_at)'))
                conn.execute(text('CREATE INDEX IF NOT EXISTS ix_messages_email ON messages (email)'))
            except Exception:
                pass
    for column, ddl in [('role_type', "VARCHAR(40)"), ('sort_order', 'INTEGER')]:
        _add_column_if_missing('team_members', column, ddl)

    rows = Package.query.order_by(Package.id.asc()).all()
    for index, pkg in enumerate(rows, start=1):
        if not pkg.slug or pkg.slug == 'tour':
            pkg.slug = unique_slug(pkg.title, current_id=pkg.id)
        if pkg.published is None:
            pkg.published = True
        if pkg.featured is None:
            pkg.featured = index <= 6
        if pkg.sort_order is None:
            pkg.sort_order = index
        if pkg.created_at is None:
            pkg.created_at = datetime.utcnow()
        if pkg.updated_at is None:
            pkg.updated_at = pkg.created_at
    if rows:
        db.session.commit()

    # Backfill team role/order so existing profiles get the intended default sequence.
    role_rank = {'founder': 1, 'co_founder': 2, 'designer': 3, 'team_member': 4, 'custom': 5}
    team_rows = TeamMember.query.order_by(TeamMember.id.asc()).all()
    for member in team_rows:
        if not member.role_type or member.role_type not in role_rank:
            label = f'{member.position or ''}'.lower()
            if 'co-founder' in label or 'cofounder' in label or 'co founder' in label:
                member.role_type = 'co_founder'
            elif 'founder' in label:
                member.role_type = 'founder'
            elif 'designer' in label:
                member.role_type = 'designer'
            else:
                member.role_type = 'team_member'
    ordered_team = sorted(team_rows, key=lambda m: (role_rank.get(m.role_type, 5), m.sort_order or 999999, m.id))
    for idx, member in enumerate(ordered_team, start=1):
        member.sort_order = idx
    if team_rows:
        db.session.commit()

    settings = db.session.get(SiteSettings, 1)
    if settings is not None:
        changed = False
        if not settings.header_logo_position:
            settings.header_logo_position = 'left'; changed = True
        if not settings.body_font:
            settings.body_font = 'inter'; changed = True
        if not settings.heading_font:
            settings.heading_font = 'poppins'; changed = True
        if not settings.base_font_size:
            settings.base_font_size = 16; changed = True
        if not settings.heading_scale:
            settings.heading_scale = 100; changed = True
        if not settings.body_text_color:
            settings.body_text_color = '#1f2937'; changed = True
        if not settings.heading_text_color:
            settings.heading_text_color = '#14532d'; changed = True
        if not settings.link_text_color:
            settings.link_text_color = '#166534'; changed = True
        if not settings.public_config_json:
            settings.public_config_json = json.dumps(PUBLIC_SITE_DEFAULTS, ensure_ascii=False)
            changed = True
        if changed:
            db.session.commit()

def _create_initial_owner_if_missing():
    """Create the configured bootstrap Owner only when the username is absent.

    Existing accounts are deliberately left untouched. In particular, deploys
    must never reactivate, re-promote, rename, or change the email/password of
    an account that an administrator has already managed.
    """
    if not initial_password_hash or not inspect(db.engine).has_table('users'):
        return False

    owner = User.query.filter_by(username=initial_owner_username).first()
    if owner is not None:
        return False

    try:
        # Validate the configured bootstrap hash only when it is actually
        # needed to create the first Owner account.
        check_password_hash(initial_password_hash, '__ri_burom_hash_validation__')
    except (ValueError, TypeError):
        raise RuntimeError(
            'ADMIN_PASSWORD_HASH is not a valid Werkzeug password hash. '
            'Generate it with generate_password_hash.py and replace the Render environment variable.'
        ) from None

    owner = User(
        username=initial_owner_username,
        full_name=initial_owner_name,
        email=initial_owner_email,
        password_hash=initial_password_hash,
        role='owner',
        is_active=True,
    )
    db.session.add(owner)
    db.session.flush()
    add_audit(
        'initial_owner_created',
        'user',
        owner.id,
        'Initial Owner created from ADMIN_PASSWORD_HASH'
    )
    db.session.commit()
    return True


def run_deploy_bootstrap():
    """Run RI BUROM's explicit deploy-time compatibility/bootstrap work.

    This function is intentionally *not* called while importing app.py.
    Render's deploy preparation script invokes it explicitly before Alembic.
    Keeping the call explicit prevents Gunicorn imports/restarts from mutating
    Neon while preserving the compatibility work the current production
    database still relies on.
    """
    with app.app_context():
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
        db.create_all()
        _run_legacy_migrations()
        seed_defaults()
        return {
            'initial_owner_created': _create_initial_owner_if_missing(),
        }


# ------------------------------------------------------------
# Authentication / authorization
# ------------------------------------------------------------
def login_required(view_func):
    @wraps(view_func)
    def wrapped(*args, **kwargs):
        user = get_current_user()
        if user is None:
            flash('Please log in to access the control room.', 'error')
            return redirect(url_for('admin_login', next=request.path))
        return view_func(*args, **kwargs)
    return wrapped


def permission_required(permission):
    def decorator(view_func):
        @wraps(view_func)
        def wrapped(*args, **kwargs):
            user = get_current_user()
            if user is None:
                flash('Please log in to access the control room.', 'error')
                return redirect(url_for('admin_login', next=request.path))
            if not user.has_permission(permission):
                abort(403)
            return view_func(*args, **kwargs)
        return wrapped
    return decorator


def owner_required(view_func):
    @wraps(view_func)
    def wrapped(*args, **kwargs):
        user = get_current_user()
        if user is None:
            flash('Please log in to access the control room.', 'error')
            return redirect(url_for('admin_login', next=request.path))
        # User management is deliberately Owner-only. It must never be
        # delegable through the ordinary permission checkboxes, otherwise a
        # delegated user could grant themselves the Owner role.
        if user.role != 'owner':
            abort(403)
        return view_func(*args, **kwargs)
    return wrapped


# ------------------------------------------------------------
# Public routes
# ------------------------------------------------------------
@app.route('/')
def home():
    about_row = db.session.get(AboutContent, 1)
    settings = get_site_settings()
    featured = Package.query.filter_by(published=True, featured=True).order_by(Package.sort_order.asc(), Package.id.desc()).limit(6).all()
    if not featured:
        featured = Package.query.filter_by(published=True).order_by(Package.sort_order.asc(), Package.id.desc()).limit(6).all()
    total_published = Package.query.filter_by(published=True).count()
    hero_logo = settings.hero_logo or settings.header_mark or settings.header_wordmark
    return render_template('index.html', hero_image=about_row.hero_image if about_row else None, hero_logo=hero_logo, packages=featured, has_more=total_published > len(featured), settings=settings)


@app.route('/admin/customers')
@permission_required('view_customer_analytics')
def customer_analytics():
    total_inquiries = Message.query.count()
    unread = Message.query.filter_by(is_read=False).count()
    unique_customers = db.session.query(func.count(func.distinct(func.lower(Message.email)))).scalar() or 0
    repeat_subquery = (
        db.session.query(func.lower(Message.email).label('email'), func.count(Message.id).label('n'))
        .group_by(func.lower(Message.email))
        .having(func.count(Message.id) > 1)
        .subquery()
    )
    repeat_customers = db.session.query(func.count()).select_from(repeat_subquery).scalar() or 0

    now = datetime.utcnow()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    last_30 = now - timedelta(days=30)
    this_month = Message.query.filter(Message.created_at >= month_start).count()
    last_30_count = Message.query.filter(Message.created_at >= last_30).count()
    avg_travellers = db.session.query(func.avg(Message.travellers)).filter(Message.travellers.isnot(None)).scalar()

    interests = (
        db.session.query(Message.tour_interest, func.count(Message.id))
        .filter(Message.tour_interest.isnot(None), Message.tour_interest != '')
        .group_by(Message.tour_interest)
        .order_by(desc(func.count(Message.id)))
        .limit(10)
        .all()
    )

    year_ago = now - timedelta(days=365)
    created_rows = Message.query.with_entities(Message.created_at).filter(Message.created_at >= year_ago).all()
    month_counter = Counter(row[0].strftime('%Y-%m') for row in created_rows if row[0])
    month_labels = []
    cursor = month_start.replace(day=1)
    for _ in range(12):
        key = cursor.strftime('%Y-%m')
        month_labels.append((cursor.strftime('%b %Y'), month_counter.get(key, 0)))
        if cursor.month == 1:
            cursor = cursor.replace(year=cursor.year - 1, month=12)
        else:
            cursor = cursor.replace(month=cursor.month - 1)
    month_labels.reverse()

    recent = Message.query.order_by(Message.created_at.desc()).limit(25).all()
    return render_template(
        'customer_analytics.html',
        total_inquiries=total_inquiries,
        unique_customers=unique_customers,
        repeat_customers=repeat_customers,
        unread=unread,
        this_month=this_month,
        last_30_count=last_30_count,
        avg_travellers=round(float(avg_travellers), 1) if avg_travellers is not None else 0,
        interests=interests,
        month_labels=month_labels,
        max_month_count=max([count for _, count in month_labels] or [1]),
        recent=recent,
    )


# Characters that spreadsheet apps (Excel, Google Sheets, LibreOffice) treat
# as the start of a formula when a cell is opened. Any user-supplied field
# (this data comes from the public, unauthenticated contact form) that starts
# with one of these is defused by prefixing a single quote, which forces the
# cell to be read as literal text without changing what is displayed.
# See CWE-1236 (Improper Neutralization of Formula Elements in a CSV File).
_CSV_FORMULA_TRIGGERS = ('=', '+', '-', '@', '\t', '\r', '\n')


def csv_safe(value):
    """Return `value` as a string, neutralized against CSV/formula injection."""
    text = '' if value is None else str(value)
    if text and text[0] in _CSV_FORMULA_TRIGGERS:
        text = "'" + text
    return text


@app.route('/admin/customers/export.csv')
@permission_required('view_customer_analytics')
def export_customer_inquiries():
    import csv
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Date', 'Name', 'Email', 'Phone', 'Travel Dates', 'Travellers', 'Tour / Experience', 'Message', 'Read'])
    for msg in Message.query.order_by(Message.created_at.desc()).all():
        writer.writerow([
            msg.created_at.strftime('%Y-%m-%d %H:%M:%S') if msg.created_at else '',
            csv_safe(msg.name), csv_safe(msg.email), csv_safe(msg.phone), csv_safe(msg.travel_dates),
            csv_safe(msg.travellers), csv_safe(msg.tour_interest), csv_safe(msg.message),
            'Yes' if msg.is_read else 'No',
        ])
    return Response(
        '\ufeff' + output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment; filename="ri-burom-customer-inquiries.csv"'},
    )


PUBLIC_PROVIDER_STATUSES = {'APPROVED', 'PUBLISHED', 'ACTIVE'}
PUBLIC_SERVICE_STATUSES = {'PUBLISHED', 'ACTIVE'}


def _public_provider_query():
    return Provider.query.filter(
        Provider.is_active.is_(True),
        Provider.status.in_(PUBLIC_PROVIDER_STATUSES),
    )


@app.route('/marketplace')
def marketplace_public_index():
    providers = _public_provider_query().order_by(
        Provider.name.asc(),
        Provider.id.asc(),
    ).all()

    for provider in providers:
        provider.public_services = [
            service
            for service in provider.services
            if service.is_active and service.status in PUBLIC_SERVICE_STATUSES
        ]

    return render_template(
        'marketplace_public.html',
        providers=providers,
    )


@app.route('/marketplace/providers/<slug>')
def marketplace_public_provider(slug):
    provider = _public_provider_query().filter_by(slug=slug).first_or_404()

    services = [
        service
        for service in provider.services
        if service.is_active and service.status in PUBLIC_SERVICE_STATUSES
    ]
    services.sort(key=lambda item: (item.name.lower(), item.id))

    return render_template(
        'marketplace_provider.html',
        provider=provider,
        services=services,
    )

@app.route('/all_tours')
def all_tours():
    packages = Package.query.filter_by(published=True).order_by(Package.sort_order.asc(), Package.id.desc()).all()
    return render_template('tours.html', packages=packages)


@app.route('/tours/<slug>')
def tour_detail(slug):
    pkg = Package.query.filter_by(slug=slug, published=True).first_or_404()
    return render_template('tour_detail.html', pkg=pkg)


@app.route('/about')
def about():
    about_row = db.session.get(AboutContent, 1)
    settings = get_site_settings()
    sections = AboutSection.query.filter_by(enabled=True).order_by(AboutSection.sort_order.asc(), AboutSection.id.asc()).all()
    team = TeamMember.query.order_by(TeamMember.sort_order.asc(), TeamMember.id.asc()).all()
    return render_template('about.html', about=about_row, team=team, settings=settings, sections=sections)


@app.route('/send_message', methods=['POST'])
@limiter.limit('5 per minute')
def send_message():
    name = (request.form.get('name') or '').strip()
    email = (request.form.get('email') or '').strip()
    phone = (request.form.get('phone') or '').strip()
    travel_dates = (request.form.get('travel_dates') or '').strip()
    tour_interest = (request.form.get('tour_interest') or '').strip()
    message = (request.form.get('message') or '').strip()
    travellers_raw = (request.form.get('travellers') or '').strip()
    if not name or len(name) > 120:
        flash('Please provide a valid name.', 'error'); return redirect('/#contact')
    if not email or len(email) > 254 or not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', email):
        flash('Please provide a valid email address.', 'error'); return redirect('/#contact')
    if len(phone) > 40 or len(travel_dates) > 120 or len(tour_interest) > 200 or len(message) > 5000 or not message:
        flash('One of the fields is invalid or too long. Please try again.', 'error'); return redirect('/#contact')
    travellers = None
    if travellers_raw:
        try:
            travellers = int(travellers_raw)
            if travellers < 1 or travellers > 999: raise ValueError
        except ValueError:
            flash('Number of travellers must be a whole number between 1 and 999.', 'error'); return redirect('/#contact')
    db.session.add(Message(name=name, email=email, phone=phone or None, travel_dates=travel_dates or None, travellers=travellers, tour_interest=tour_interest or None, message=message))
    db.session.commit()
    flash("Thanks! Your message has been sent — we'll get back to you soon.", 'success')
    return redirect('/#contact')


@app.route('/robots.txt')
def robots_txt():
    return send_from_directory('static', 'robots.txt') if os.path.exists(os.path.join(BASE_DIR, 'static', 'robots.txt')) else ("User-agent: *\nAllow: /\n", 200, {'Content-Type': 'text/plain'})


@app.route('/sitemap.xml')
def sitemap_xml():
    pages = ['/', '/all_tours', '/about']
    tours = Package.query.filter_by(published=True).all()
    xml = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for p in pages:
        xml.append(f'<url><loc>{escape(request.url_root.rstrip("/") + p)}</loc></url>')
    for pkg in tours:
        xml.append(f'<url><loc>{escape(url_for("tour_detail", slug=pkg.slug, _external=True))}</loc></url>')
    xml.append('</urlset>')
    return ('\n'.join(xml), 200, {'Content-Type': 'application/xml'})


# ------------------------------------------------------------
# Authentication routes
# ------------------------------------------------------------
@app.route('/admin/login', methods=['GET', 'POST'])
@limiter.limit('5 per minute', methods=['POST'])
def admin_login():
    if get_current_user():
        return redirect(url_for('admin'))
    if request.method == 'POST':
        username = (request.form.get('username') or '').strip().lower()
        password = request.form.get('password', '')
        user = User.query.filter_by(username=username).first()
        if user and user.is_active and check_password_hash(user.password_hash, password):
            session.clear()
            session['user_id'] = user.id
            user.last_login = datetime.utcnow()
            add_audit('login', 'user', user.id)
            db.session.commit()
            flash(f'Welcome, {user.full_name}.', 'success')
            next_url = request.args.get('next')
            return redirect(next_url if valid_local_redirect(next_url) else url_for('admin'))
        flash('Incorrect username or password.', 'error')
    return render_template('admin_login.html')


@app.route('/admin/logout', methods=['POST'])
@login_required
def admin_logout():
    user = get_current_user()
    add_audit('logout', 'user', user.id if user else None)
    db.session.commit()
    session.clear()
    flash('Logged out.', 'success')
    return redirect(url_for('admin_login'))


@app.route('/admin/account', methods=['GET', 'POST'])
@login_required
def account():
    user = get_current_user()
    if request.method == 'POST':
        current = request.form.get('current_password', '')
        new_password = request.form.get('new_password', '')
        confirm = request.form.get('confirm_password', '')
        if not check_password_hash(user.password_hash, current):
            flash('Current password is incorrect.', 'error'); return redirect(url_for('account'))
        if len(new_password) < 12:
            flash('New password must be at least 12 characters long.', 'error'); return redirect(url_for('account'))
        if new_password != confirm:
            flash('New passwords do not match.', 'error'); return redirect(url_for('account'))
        user.password_hash = generate_password_hash(new_password)
        add_audit('password_changed', 'user', user.id)
        db.session.commit()
        flash('Password changed successfully.', 'success')
        return redirect(url_for('admin'))
    return render_template('account.html', user=user)


# ------------------------------------------------------------
# Admin dashboard
# ------------------------------------------------------------
@app.route('/admin')
@login_required
def admin():
    packages = Package.query.order_by(Package.sort_order.asc(), Package.id.desc()).all()
    about_row = db.session.get(AboutContent, 1)
    settings = get_site_settings()
    team = TeamMember.query.order_by(TeamMember.sort_order.asc(), TeamMember.id.asc()).all()
    about_sections = AboutSection.query.order_by(AboutSection.sort_order.asc(), AboutSection.id.asc()).all()
    user = get_current_user()
    messages = Message.query.order_by(Message.id.desc()).all() if user.has_permission('view_messages') else []
    unread_count = Message.query.filter_by(is_read=False).count() if user.has_permission('view_messages') else 0
    users = User.query.order_by(User.username.asc()).all() if user.role == 'owner' else []
    user_count = User.query.count() if user.role == 'owner' else 0
    audits = AuditLog.query.order_by(AuditLog.id.desc()).limit(50).all() if user.has_permission('view_audit_log') else []
    return render_template('admin.html', user_count=user_count, packages=packages, about=about_row, team=team, about_sections=about_sections, settings=settings, messages=messages, unread_count=unread_count, users=users, audits=audits, storage_backend=STORAGE_BACKEND, permission_labels=PERMISSION_LABELS, permission_keys=PERMISSION_KEYS)


@app.route('/add_package', methods=['POST'])
@permission_required('manage_tours')
def add_package():
    title = request.form.get('title', '').strip(); description = request.form.get('description', '').strip()
    if not title or not description:
        flash('Tour name and description are required.', 'error'); return redirect('/admin')
    try:
        image_file = save_image(request.files.get('photo')) or 'default.jpg'
        pdf_file = save_pdf(request.files.get('pdf')) or ''
    except ValueError as e:
        flash(str(e), 'error'); return redirect('/admin')
    try: sort_order = int(request.form.get('sort_order') or 0)
    except ValueError: sort_order = 0
    pkg = Package(title=title, slug=unique_slug(title), description=description,
        location=(request.form.get('location') or '').strip() or None,
        duration=(request.form.get('duration') or '').strip() or None,
        price=(request.form.get('price') or '').strip() or None,
        category=(request.form.get('category') or '').strip() or None,
        best_season=(request.form.get('best_season') or '').strip() or None,
        difficulty=(request.form.get('difficulty') or '').strip() or None,
        itinerary=(request.form.get('itinerary') or '').strip() or None,
        included=(request.form.get('included') or '').strip() or None,
        excluded=(request.form.get('excluded') or '').strip() or None,
        image_file=image_file, pdf_file=pdf_file, published=bool(request.form.get('published')),
        featured=bool(request.form.get('featured')), sort_order=sort_order)
    db.session.add(pkg); db.session.flush()
    add_audit('created', 'package', pkg.id, pkg.title)
    db.session.commit()
    flash(f'"{title}" added.', 'success'); return redirect('/admin')


@app.route('/edit_package/<int:id>', methods=['GET'])
@permission_required('manage_tours')
def edit_package_form(id):
    pkg = db.session.get(Package, id)
    if pkg is None: abort(404)
    return render_template('edit_package.html', pkg=pkg)


@app.route('/edit_package/<int:id>', methods=['POST'])
@permission_required('manage_tours')
def edit_package(id):
    pkg = db.session.get(Package, id)
    if pkg is None: abort(404)
    title = request.form.get('title', '').strip(); description = request.form.get('description', '').strip()
    if not title or not description:
        flash('Tour name and description are required.', 'error'); return redirect(url_for('edit_package_form', id=id))
    old_image, old_pdf = pkg.image_file, pkg.pdf_file
    try:
        new_image = save_image(request.files.get('photo')); new_pdf = save_pdf(request.files.get('pdf'))
    except ValueError as e:
        flash(str(e), 'error'); return redirect(url_for('edit_package_form', id=id))
    pkg.title = title; pkg.slug = unique_slug(title, current_id=id); pkg.description = description
    for field in ('location','duration','price','category','best_season','difficulty','itinerary','included','excluded'):
        setattr(pkg, field, (request.form.get(field) or '').strip() or None)
    pkg.published = bool(request.form.get('published')); pkg.featured = bool(request.form.get('featured'))
    try: pkg.sort_order = int(request.form.get('sort_order') or 0)
    except ValueError: pkg.sort_order = 0
    if new_image: pkg.image_file = new_image
    elif request.form.get('remove_image'): pkg.image_file = None
    if new_pdf: pkg.pdf_file = new_pdf
    elif request.form.get('remove_pdf'): pkg.pdf_file = ''
    db.session.flush(); add_audit('updated', 'package', pkg.id, pkg.title); db.session.commit()
    if (new_image or request.form.get('remove_image')) and old_image != pkg.image_file: delete_media(old_image)
    if (new_pdf or request.form.get('remove_pdf')) and old_pdf != pkg.pdf_file: delete_media(old_pdf)
    flash(f'"{title}" updated.', 'success'); return redirect('/admin')


@app.route('/delete_package/<int:id>', methods=['POST'])
@permission_required('manage_tours')
def delete_package(id):
    pkg = db.session.get(Package, id)
    if pkg is not None:
        old_image, old_pdf, title = pkg.image_file, pkg.pdf_file, pkg.title
        db.session.delete(pkg); add_audit('deleted', 'package', id, title); db.session.commit(); delete_media(old_image); delete_media(old_pdf)
    flash('Package deleted.', 'success'); return redirect('/admin')


@app.route('/update_about_structure', methods=['POST'])
@permission_required('manage_structure')
def update_about_structure():
    try:
        ordered_keys = json.loads(request.form.get('section_order') or '[]')
        enabled_state = json.loads(request.form.get('section_state') or '{}')
        labels_state = json.loads(request.form.get('section_labels') or '{}')
    except (TypeError, ValueError, json.JSONDecodeError):
        flash('Invalid About Us page structure data.', 'error')
        return redirect('/admin#about-structure')

    sections = {row.key: row for row in AboutSection.query.all()}
    valid_keys = set(sections)
    ordered_keys = [key for key in ordered_keys if key in valid_keys]
    for key in sections:
        if key not in ordered_keys:
            ordered_keys.append(key)

    for idx, key in enumerate(ordered_keys, start=1):
        sections[key].sort_order = idx
        if key in enabled_state:
            sections[key].enabled = bool(enabled_state[key])
        if key in labels_state:
            label = str(labels_state[key]).strip()[:200]
            if label:
                sections[key].label = label

    add_audit('updated', 'about_structure', 1, ', '.join(ordered_keys))
    db.session.commit()
    flash('About Us page structure updated.', 'success')
    return redirect('/admin#about-structure')


@app.route('/update_team_order', methods=['POST'])
@permission_required('manage_structure')
def update_team_order():
    try:
        ordered_ids = json.loads(request.form.get('team_order') or '[]')
    except (TypeError, ValueError, json.JSONDecodeError):
        flash('Invalid team order data.', 'error')
        return redirect('/admin#team')

    members = {member.id: member for member in TeamMember.query.all()}
    valid_ids = set(members)
    ordered_ids = [int(value) for value in ordered_ids if str(value).isdigit() and int(value) in valid_ids]
    for member_id in sorted(valid_ids):
        if member_id not in ordered_ids:
            ordered_ids.append(member_id)

    for idx, member_id in enumerate(ordered_ids, start=1):
        members[member_id].sort_order = idx

    add_audit('updated', 'team_order', 1, ', '.join(map(str, ordered_ids)))
    db.session.commit()
    flash('Team profile order updated.', 'success')
    return redirect('/admin#team')


@app.route('/update_mission', methods=['POST'])
@permission_required('manage_about')
def update_mission():
    mission = request.form.get('mission', '').strip()
    if len(mission) > 10000: flash('Mission statement is too long.', 'error'); return redirect('/admin')
    about_row = db.session.get(AboutContent, 1)
    if about_row is None: about_row = AboutContent(id=1, mission=mission); db.session.add(about_row)
    else: about_row.mission = mission
    add_audit('updated', 'about', 1, 'mission'); db.session.commit()
    flash('Mission statement updated.', 'success'); return redirect('/admin')


@app.route('/update_about_content', methods=['POST'])
@permission_required('manage_about')
def update_about_content():
    mission = (request.form.get('mission') or '').strip()
    if len(mission) > 10000:
        flash('Mission statement is too long.', 'error')
        return redirect('/admin#about')

    about_row = db.session.get(AboutContent, 1)
    if about_row is None:
        about_row = AboutContent(id=1, mission=mission)
        db.session.add(about_row)
    else:
        about_row.mission = mission

    settings = get_site_settings()
    text_fields = [
        'nature_title', 'nature_text', 'culture_title', 'culture_text',
        'community_title', 'community_text',
        'about_extra1_title', 'about_extra1_text',
        'about_extra2_title', 'about_extra2_text',
        'logo_meaning_title', 'logo_meaning_text',
        'logo_designer_name', 'logo_designer_credit',
    ]
    max_lengths = {
        'nature_title': 200, 'culture_title': 200, 'community_title': 200,
        'about_extra1_title': 200, 'about_extra2_title': 200,
        'logo_meaning_title': 200, 'logo_designer_name': 200,
        'logo_designer_credit': 300,
        'nature_text': 5000, 'culture_text': 5000, 'community_text': 5000,
        'about_extra1_text': 10000, 'about_extra2_text': 10000,
        'logo_meaning_text': 15000,
    }
    for field in text_fields:
        value = (request.form.get(field) or '').strip()
        if len(value) > max_lengths[field]:
            flash(f'{field.replace("_", " ").title()} is too long.', 'error')
            return redirect('/admin#about')
        setattr(settings, field, value)

    settings.about_extra1_enabled = bool(request.form.get('about_extra1_enabled'))
    settings.about_extra2_enabled = bool(request.form.get('about_extra2_enabled'))
    settings.logo_meaning_enabled = bool(request.form.get('logo_meaning_enabled'))

    try:
        new_pdf = save_pdf(request.files.get('logo_meaning_pdf'))
    except ValueError as exc:
        flash(str(exc), 'error')
        return redirect('/admin#about')
    old_pdf = settings.logo_meaning_pdf
    if new_pdf:
        settings.logo_meaning_pdf = new_pdf
    elif request.form.get('remove_logo_meaning_pdf'):
        settings.logo_meaning_pdf = None

    add_audit('updated', 'about_content', 1, 'mission, pillars, editable sections, logo meaning')
    db.session.commit()
    if (new_pdf or request.form.get('remove_logo_meaning_pdf')) and old_pdf != settings.logo_meaning_pdf:
        delete_media(old_pdf)
    flash('About Us content updated.', 'success')
    return redirect('/admin#about')


@app.route('/update_branding', methods=['POST'])
@permission_required('manage_media')
def update_branding():
    settings = get_site_settings()
    previous = {
        'header_wordmark': settings.header_wordmark,
        'header_mark': settings.header_mark,
        'hero_logo': settings.hero_logo,
    }
    try:
        wordmark = save_image(request.files.get('header_wordmark'))
        mark = save_image(request.files.get('header_mark'))
        hero_logo = save_image(request.files.get('hero_logo'))
    except ValueError as exc:
        flash(str(exc), 'error')
        return redirect('/admin#branding')

    if wordmark:
        settings.header_wordmark = wordmark
    if mark:
        settings.header_mark = mark
    if hero_logo:
        settings.hero_logo = hero_logo

    for field in ('header_wordmark', 'header_mark', 'hero_logo'):
        if request.form.get(f'remove_{field}'):
            setattr(settings, field, None)

    add_audit('updated', 'branding', 1, 'header and hero logos')
    db.session.commit()

    for field, old_value in previous.items():
        new_value = getattr(settings, field)
        if new_value != old_value and (field in request.files or request.form.get(f'remove_{field}')):
            delete_media(old_value)

    flash('Logo images updated.', 'success')
    return redirect('/admin#branding')


@app.route('/update_logo_sizes', methods=['POST'])
@permission_required('manage_media')
def update_logo_sizes():
    settings = get_site_settings()
    settings.header_wordmark_width = clamp_int(request.form.get('header_wordmark_width'), settings.header_wordmark_width, 50, 260)
    settings.header_mark_width = clamp_int(request.form.get('header_mark_width'), settings.header_mark_width, 24, 160)
    settings.header_logo_gap = clamp_int(request.form.get('header_logo_gap'), settings.header_logo_gap, 0, 32)
    settings.hero_logo_width = clamp_int(request.form.get('hero_logo_width'), settings.hero_logo_width, 120, 520)
    add_audit('updated', 'branding_sizes', 1, 'logo display sizes')
    db.session.commit()
    flash('Logo sizes updated.', 'success')
    return redirect('/admin#branding')


@app.route('/reset_logo_sizes', methods=['POST'])
@permission_required('manage_media')
def reset_logo_sizes():
    settings = get_site_settings()
    settings.header_wordmark_width = 125
    settings.header_mark_width = 48
    settings.header_logo_gap = 8
    settings.hero_logo_width = 300
    settings.header_logo_position = 'left'
    add_audit('reset', 'branding_sizes', 1, 'logo display sizes and header position')
    db.session.commit()
    flash('Logo sizes reset to the default values.', 'success')
    return redirect('/admin#branding')


@app.route('/update_header_layout', methods=['POST'])
@permission_required('manage_media')
def update_header_layout():
    position = (request.form.get('header_logo_position') or 'left').strip().lower()
    if position not in {'left', 'center', 'right'}:
        position = 'left'
    settings = get_site_settings()
    settings.header_logo_position = position
    settings.header_logo_gap = clamp_int(request.form.get('header_logo_gap'), settings.header_logo_gap, 0, 32)
    settings.header_wordmark_width = clamp_int(request.form.get('header_wordmark_width'), settings.header_wordmark_width, 50, 320)
    settings.header_mark_width = clamp_int(request.form.get('header_mark_width'), settings.header_mark_width, 24, 180)
    settings.hero_logo_width = clamp_int(request.form.get('hero_logo_width'), settings.hero_logo_width, 120, 560)
    add_audit('updated', 'header_layout', 1, f'position={position}')
    db.session.commit()
    flash('Header and logo layout saved.', 'success')
    return redirect('/admin#branding')


@app.route('/update_typography', methods=['POST'])
@permission_required('manage_media')
def update_typography():
    settings = get_site_settings()
    body_font = (request.form.get('body_font') or 'inter').strip().lower()
    heading_font = (request.form.get('heading_font') or 'poppins').strip().lower()
    if body_font not in FONT_OPTIONS:
        body_font = 'inter'
    if heading_font not in FONT_OPTIONS:
        heading_font = 'poppins'
    settings.body_font = body_font
    settings.heading_font = heading_font
    settings.base_font_size = clamp_int(request.form.get('base_font_size'), 16, 14, 20)
    settings.heading_scale = clamp_int(request.form.get('heading_scale'), 100, 80, 130)
    for field in ('body_text_color', 'heading_text_color', 'link_text_color'):
        value = (request.form.get(field) or '').strip()
        if re.fullmatch(r'#[0-9a-fA-F]{6}', value):
            setattr(settings, field, value)
    add_audit('updated', 'typography', 1, f'body_font={body_font}; heading_font={heading_font}')
    db.session.commit()
    flash('Typography settings saved.', 'success')
    return redirect('/admin#typography')


@app.route('/admin/update_public_site', methods=['POST'])
@owner_required
def update_public_site():
    settings = get_site_settings()
    cfg = get_public_config(settings)
    content = cfg['content']
    theme = cfg['theme']
    home = cfg['home']

    content_fields = [
        'site_title','meta_description','og_title','og_description',
        'nav_home','nav_tours','nav_about','nav_contact','nav_login',
        'mobile_tours','mobile_about','mobile_contact','mobile_menu',
        'hero_eyebrow','hero_title','hero_subtitle','hero_primary_button','hero_secondary_button',
        'home_about_eyebrow','home_about_title','home_about_text','home_tours_eyebrow','home_tours_title','home_tours_all',
        'home_tour_button','home_tours_empty','home_why_eyebrow','home_why_title','home_why_text',
        'why1_title','why1_text','why2_title','why2_text','why3_title','why3_text','why4_title','why4_text',
        'blog_eyebrow','contact_title','contact_text','form_name','form_email','form_phone','form_travellers','form_dates',
        'form_tour','form_message','form_submit','form_dates_placeholder','form_tour_placeholder','whatsapp_text','whatsapp_message',
        'tours_page_title','tours_page_eyebrow','tours_page_heading','tours_page_intro','tours_empty','tours_view_button','tours_price_prefix',
        'about_page_title','about_page_eyebrow','about_page_intro','tour_detail_overview','tour_detail_itinerary',
        'tour_detail_included','tour_detail_excluded','tour_detail_starting','tour_detail_best_season','tour_detail_whatsapp',
        'tour_detail_enquiry','tour_detail_pdf','footer_explore','footer_contact','footer_qr',
    ]
    for field in content_fields:
        value = (request.form.get(field) or '').strip()
        if len(value) > 20000:
            flash(f'{field.replace("_", " ").title()} is too long.', 'error')
            return redirect('/admin#website')
        content[field] = value

    theme['primary_color'] = _safe_hex(request.form.get('primary_color'), theme['primary_color'])
    theme['secondary_color'] = _safe_hex(request.form.get('secondary_color'), theme['secondary_color'])
    theme['accent_color'] = _safe_hex(request.form.get('accent_color'), theme['accent_color'])
    theme['link_color'] = _safe_hex(request.form.get('link_color'), theme['link_color'])
    theme['header_bg_color'] = _safe_hex(request.form.get('header_bg_color'), theme['header_bg_color'])
    theme['footer_bg_color'] = _safe_hex(request.form.get('footer_bg_color'), theme['footer_bg_color'])
    theme['button_radius'] = clamp_int(request.form.get('button_radius'), theme.get('button_radius', 10), 0, 32)
    theme['section_spacing'] = clamp_int(request.form.get('section_spacing'), theme.get('section_spacing', 64), 32, 128)
    theme['hero_overlay_opacity'] = clamp_int(request.form.get('hero_overlay_opacity'), theme.get('hero_overlay_opacity', 55), 0, 90)
    theme['whatsapp_visible'] = bool(request.form.get('whatsapp_visible'))
    theme['show_login_button'] = bool(request.form.get('show_login_button'))

    valid_home = ['hero','about','tours','why','blog','contact']
    try:
        order = json.loads(request.form.get('home_section_order') or '[]')
    except (TypeError, ValueError, json.JSONDecodeError):
        order = []
    order = [item for item in order if item in valid_home]
    for item in valid_home:
        if item not in order:
            order.append(item)
    try:
        visibility = json.loads(request.form.get('home_section_visibility') or '{}')
    except (TypeError, ValueError, json.JSONDecodeError):
        visibility = {}
    home['order'] = order
    home['visibility'] = {item: bool(visibility.get(item, True)) for item in valid_home}

    settings.public_config_json = json.dumps(cfg, ensure_ascii=False)
    add_audit('updated', 'public_site', 1, 'global public content, theme, and homepage structure')
    db.session.commit()
    flash('Public website settings saved.', 'success')
    return redirect('/admin#website')


@app.route('/update_blog', methods=['POST'])
@permission_required('manage_about')
def update_blog():
    settings = get_site_settings()
    url = (request.form.get('blog_url') or '').strip()
    if url and not valid_external_url(url):
        flash('Blog URL must be a valid http/https link.', 'error')
        return redirect('/admin#blog')
    settings.blog_enabled = bool(request.form.get('blog_enabled'))
    settings.blog_show_home = bool(request.form.get('blog_show_home'))
    settings.blog_url = url
    settings.blog_title = (request.form.get('blog_title') or '').strip()[:300]
    settings.blog_excerpt = (request.form.get('blog_excerpt') or '').strip()[:10000]
    settings.blog_button_text = (request.form.get('blog_button_text') or 'Read the Story').strip()[:120] or 'Read the Story'

    old_image = settings.blog_image
    try:
        new_image = save_image(request.files.get('blog_image'))
    except ValueError as exc:
        flash(str(exc), 'error')
        return redirect('/admin#blog')
    if new_image:
        settings.blog_image = new_image
    elif request.form.get('remove_blog_image'):
        settings.blog_image = None

    add_audit('updated', 'blog', 1, 'featured external blog story')
    db.session.commit()
    if (new_image or request.form.get('remove_blog_image')) and old_image != settings.blog_image:
        delete_media(old_image)
    flash('Blog feature updated.', 'success')
    return redirect('/admin#blog')


@app.route('/update_footer', methods=['POST'])
@permission_required('manage_about')
def update_footer():
    settings = get_site_settings()
    fields = [
        ('footer_business_name', 200), ('footer_tagline', 300), ('footer_phone', 200),
        ('footer_email', 254), ('footer_address', 500), ('footer_copyright', 300),
        ('instagram_label', 120),
    ]
    for field, limit in fields:
        value = (request.form.get(field) or '').strip()
        if len(value) > limit:
            flash(f'{field.replace("_", " ").title()} is too long.', 'error')
            return redirect('/admin#footer')
        setattr(settings, field, value)

    instagram_url = (request.form.get('instagram_url') or '').strip()
    if instagram_url and not valid_external_url(instagram_url):
        flash('Instagram URL must be a valid http/https link.', 'error')
        return redirect('/admin#footer')

    old_url = settings.instagram_url
    old_qr = settings.instagram_qr
    settings.instagram_url = instagram_url
    settings.instagram_show_qr = bool(request.form.get('instagram_show_qr'))

    try:
        if instagram_url and (instagram_url != old_url or not old_qr):
            settings.instagram_qr = generate_instagram_qr(instagram_url)
        elif not instagram_url:
            settings.instagram_qr = None
    except Exception as exc:
        flash(f'Could not generate the Instagram QR code: {exc}', 'error')
        return redirect('/admin#footer')

    add_audit('updated', 'footer', 1, 'footer and Instagram settings')
    db.session.commit()
    if old_qr and old_qr != settings.instagram_qr:
        delete_media(old_qr)
    flash('Footer and Instagram settings updated.', 'success')
    return redirect('/admin#footer')


@app.route('/add_team_member', methods=['POST'])
@permission_required('manage_team')
def add_team_member():
    name = request.form.get('name', '').strip(); position = request.form.get('position', '').strip(); role_type = request.form.get('role_type', 'team_member').strip(); description = request.form.get('description', '').strip()
    valid_roles = {'founder','co_founder','designer','team_member','custom'}
    if role_type not in valid_roles: role_type = 'team_member'
    if not name or not position: flash('Name and position are required.', 'error'); return redirect('/admin')
    try: photo_file = save_image(request.files.get('photo')) or 'default.jpg'
    except ValueError as e: flash(str(e), 'error'); return redirect('/admin')
    max_order = db.session.query(db.func.max(TeamMember.sort_order)).scalar() or 0
    member = TeamMember(name=name, position=position, role_type=role_type, sort_order=max_order + 1, description=description, photo_file=photo_file)
    db.session.add(member); db.session.flush(); add_audit('created', 'team_member', member.id, f'{name} ({role_type})'); db.session.commit()
    flash(f'{name} added to the team.', 'success'); return redirect('/admin')


@app.route('/edit_team_member/<int:id>', methods=['GET'])
@permission_required('manage_team')
def edit_team_member_form(id):
    member = db.session.get(TeamMember, id)
    if member is None: abort(404)
    return render_template('edit_team_member.html', member=member)


@app.route('/edit_team_member/<int:id>', methods=['POST'])
@permission_required('manage_team')
def edit_team_member(id):
    member = db.session.get(TeamMember, id)
    if member is None: abort(404)
    name = request.form.get('name', '').strip(); position = request.form.get('position', '').strip(); role_type = request.form.get('role_type', 'team_member').strip(); description = request.form.get('description', '').strip()
    valid_roles = {'founder','co_founder','designer','team_member','custom'}
    if role_type not in valid_roles: role_type = 'team_member'
    if not name or not position: flash('Name and position are required.', 'error'); return redirect(url_for('edit_team_member_form', id=id))
    old_photo = member.photo_file
    try: new_photo = save_image(request.files.get('photo'))
    except ValueError as e: flash(str(e), 'error'); return redirect(url_for('edit_team_member_form', id=id))
    member.name = name; member.position = position; member.role_type = role_type; member.description = description
    if new_photo: member.photo_file = new_photo
    elif request.form.get('remove_photo'): member.photo_file = None
    db.session.flush(); add_audit('updated', 'team_member', member.id, name); db.session.commit()
    if (new_photo or request.form.get('remove_photo')) and old_photo != member.photo_file: delete_media(old_photo)
    flash(f'{name} updated.', 'success'); return redirect('/admin')


@app.route('/delete_team_member/<int:id>', methods=['POST'])
@permission_required('manage_team')
def delete_team_member(id):
    member = db.session.get(TeamMember, id)
    if member is not None:
        old_photo, name = member.photo_file, member.name
        db.session.delete(member); add_audit('deleted', 'team_member', id, name); db.session.commit(); delete_media(old_photo)
    flash('Team member removed.', 'success'); return redirect('/admin')


@app.route('/mark_message_read/<int:id>', methods=['POST'])
@permission_required('manage_messages')
def mark_message_read(id):
    msg = db.session.get(Message, id)
    if msg is not None:
        msg.is_read = True; add_audit('marked_read', 'message', id); db.session.commit()
    return redirect('/admin#inbox')


@app.route('/delete_message/<int:id>', methods=['POST'])
@permission_required('manage_messages')
def delete_message(id):
    msg = db.session.get(Message, id)
    if msg is not None:
        db.session.delete(msg); add_audit('deleted', 'message', id); db.session.commit()
    flash('Message deleted.', 'success'); return redirect('/admin#inbox')


@app.route('/upload_photo', methods=['POST'])
@permission_required('manage_media')
def upload_photo():
    file = request.files.get('photo')
    if not file or not file.filename: flash('No photo selected.', 'error'); return redirect('/admin')
    if not allowed_file(file.filename, ALLOWED_IMAGE_EXTENSIONS): flash('Please upload a jpg, png, or webp image.', 'error'); return redirect('/admin')
    old_hero = None
    try: hero_image = save_image(file)
    except ValueError as e: flash(str(e), 'error'); return redirect('/admin')
    about_row = db.session.get(AboutContent, 1)
    if about_row is None: about_row = AboutContent(id=1); db.session.add(about_row)
    else: old_hero = about_row.hero_image
    about_row.hero_image = hero_image; add_audit('updated', 'hero_image', 1); db.session.commit()
    if old_hero and old_hero != hero_image: delete_media(old_hero)
    flash('Homepage background updated.', 'success'); return redirect('/admin')


# ------------------------------------------------------------
# User management - Owner only
# ------------------------------------------------------------
def _normalize_role(role):
    role = re.sub(r'\s+', ' ', (role or '').strip())
    # "Owner" is a reserved role because the application uses it to enforce
    # the minimum-one-Owner safety rule. All other role names are open-ended.
    if role.lower() == 'owner':
        return 'owner'
    return role


def _validate_user_fields(username, full_name, email, role):
    if not re.fullmatch(r'[a-z0-9_.-]{3,80}', username):
        return 'Username must be 3–80 characters using lowercase letters, numbers, dots, underscores or hyphens.'
    if not full_name or len(full_name) > 160: return 'Full name is required and must be 160 characters or fewer.'
    if email and (len(email) > 254 or not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', email)): return 'Please provide a valid email address.'
    if not role or len(role) > 40: return 'Role is required and must be 40 characters or fewer.'
    return None


def _requested_permissions():
    requested = request.form.getlist('permissions')
    return sorted({permission for permission in requested if permission in PERMISSION_LABELS})


@app.route('/admin/users/new', methods=['POST'])
@owner_required
def create_user():
    username = (request.form.get('username') or '').strip().lower()
    full_name = (request.form.get('full_name') or '').strip()
    email = (request.form.get('email') or '').strip().lower() or None
    role = _normalize_role(request.form.get('role'))
    password = request.form.get('password') or ''
    permissions = _requested_permissions()

    error = _validate_user_fields(username, full_name, email, role)
    if error: flash(error, 'error'); return redirect('/admin#users')
    if len(password) < 12: flash('Password must be at least 12 characters long.', 'error'); return redirect('/admin#users')
    if User.query.filter_by(username=username).first(): flash('That username is already in use.', 'error'); return redirect('/admin#users')
    if email and User.query.filter_by(email=email).first(): flash('That email is already in use.', 'error'); return redirect('/admin#users')

    # Owners always have full access. For every other role, the Owner's
    # checkbox selection becomes the user's exact permission set.
    if role == 'owner':
        permissions = list(PERMISSION_KEYS)

    user = User(
        username=username,
        full_name=full_name,
        email=email,
        password_hash=generate_password_hash(password),
        role=role,
        permissions_json=json.dumps(permissions),
        is_active=True,
    )
    db.session.add(user); db.session.flush()
    add_audit('created', 'user', user.id, f'{username} ({role}) permissions={", ".join(permissions) or "none"}')
    db.session.commit()
    flash(f'User {username} created.', 'success'); return redirect('/admin#users')


@app.route('/admin/users/<int:id>/update', methods=['POST'])
@owner_required
def update_user(id):
    current = get_current_user(); user = db.session.get(User, id)
    if user is None: abort(404)

    username = (request.form.get('username') or '').strip().lower()
    full_name = (request.form.get('full_name') or '').strip()
    email = (request.form.get('email') or '').strip().lower() or None
    role = _normalize_role(request.form.get('role'))
    permissions = _requested_permissions()

    error = _validate_user_fields(username, full_name, email, role)
    if error: flash(error, 'error'); return redirect('/admin#users')
    if User.query.filter(User.username == username, User.id != id).first(): flash('That username is already in use.', 'error'); return redirect('/admin#users')
    if email and User.query.filter(User.email == email, User.id != id).first(): flash('That email is already in use.', 'error'); return redirect('/admin#users')
    if user.id == current.id and not user.is_active: flash('You cannot deactivate yourself.', 'error'); return redirect('/admin#users')
    if user.id == current.id and role != 'owner': flash('The current Owner cannot remove their own Owner role.', 'error'); return redirect('/admin#users')

    active_owners = User.query.filter_by(role='owner', is_active=True).count()
    if user.role == 'owner' and role != 'owner' and active_owners <= 1:
        flash('At least one active Owner must remain.', 'error'); return redirect('/admin#users')
    if user.role == 'owner' and role == 'owner' and not bool(request.form.get('is_active')) and active_owners <= 1:
        flash('At least one active Owner must remain.', 'error'); return redirect('/admin#users')

    if role == 'owner':
        permissions = list(PERMISSION_KEYS)

    user.username = username
    user.full_name = full_name
    user.email = email
    user.role = role
    user.permissions_json = json.dumps(permissions)
    user.is_active = bool(request.form.get('is_active'))
    if user.role == 'owner': user.is_active = True

    add_audit('updated', 'user', user.id, f'{username} ({role}) permissions={", ".join(permissions) or "none"}')
    db.session.commit()
    flash(f'User {username} updated.', 'success'); return redirect('/admin#users')


@app.route('/admin/users/<int:id>/reset-password', methods=['POST'])
@owner_required
def reset_user_password(id):
    user = db.session.get(User, id)
    if user is None: abort(404)
    password = request.form.get('new_password') or ''
    if len(password) < 12: flash('Password must be at least 12 characters long.', 'error'); return redirect('/admin#users')
    user.password_hash = generate_password_hash(password)
    add_audit('password_reset_by_owner', 'user', user.id); db.session.commit()
    flash(f'Password reset for {user.username}.', 'success'); return redirect('/admin#users')


@app.route('/admin/users/<int:id>/delete', methods=['POST'])
@owner_required
def delete_user(id):
    current = get_current_user(); user = db.session.get(User, id)
    if user is None: abort(404)
    if user.id == current.id: flash('You cannot delete your own account.', 'error'); return redirect('/admin#users')
    if user.role == 'owner' and User.query.filter_by(role='owner', is_active=True).count() <= 1: flash('At least one active Owner must remain.', 'error'); return redirect('/admin#users')
    username = user.username
    user.is_active = False
    add_audit('deactivated', 'user', id, username)
    db.session.commit()
    flash(f'User {username} deactivated.', 'success'); return redirect('/admin#users')


# ------------------------------------------------------------
# Security / error handling
# ------------------------------------------------------------
@app.after_request
def add_security_headers(response):
    response.headers.setdefault('X-Content-Type-Options', 'nosniff')
    response.headers.setdefault('X-Frame-Options', 'SAMEORIGIN')
    response.headers.setdefault('Referrer-Policy', 'strict-origin-when-cross-origin')
    response.headers.setdefault('Permissions-Policy', 'camera=(), microphone=(), geolocation=()')
    if request.is_secure:
        response.headers.setdefault('Strict-Transport-Security', 'max-age=31536000; includeSubDomains')
    return response


@app.errorhandler(CSRFError)
def handle_csrf_error(e):
    flash('The form expired or was submitted from an invalid session. Please try again.', 'error')
    return redirect(request.referrer or url_for('home'))


@app.errorhandler(403)
def forbidden(e):
    return render_template('errors/403.html'), 403


@app.errorhandler(404)
def not_found(e):
    return render_template('errors/404.html'), 404


@app.errorhandler(413)
def too_large(e):
    flash('That file is too large (16MB max).', 'error')
    return redirect(request.referrer or url_for('admin'))


@app.errorhandler(500)
def server_error(e):
    return render_template('errors/500.html'), 500


if __name__ == '__main__':
    app.run(debug=IS_DEVELOPMENT)
