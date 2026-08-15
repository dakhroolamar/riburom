"""Separated RI BUROM workspace routes.

This layer intentionally sits beside the legacy /admin endpoints.  The legacy
forms remain available for compatibility, while GET /admin is redirected to
these cleaner workspaces.
"""

from copy import deepcopy
from functools import wraps
import json

from flask import abort, flash, redirect, render_template, request, url_for

from app import (
    PERMISSION_KEYS,
    PERMISSION_LABELS,
    ROLE_LABELS,
    _safe_hex,
    add_audit,
    app,
    get_current_user,
    get_public_config,
    get_site_settings,
)
from models import AuditLog, AboutContent, AboutSection, Message, Package, TeamMember, User


CONTENT_FIELDS = [
    # Browser/meta/navigation
    'site_title', 'meta_description', 'og_title', 'og_description',
    'nav_home', 'nav_tours', 'nav_about', 'nav_contact', 'nav_login',
    'mobile_tours', 'mobile_about', 'mobile_contact', 'mobile_menu',
    # Hero
    'hero_eyebrow', 'hero_title', 'hero_subtitle', 'hero_primary_button', 'hero_secondary_button',
    # Home text
    'home_about_eyebrow', 'home_about_title', 'home_about_text',
    'home_tours_eyebrow', 'home_tours_title', 'home_tours_all', 'home_tour_button', 'home_tours_empty',
    'home_why_eyebrow', 'home_why_title', 'home_why_text',
    'why1_title', 'why1_text', 'why2_title', 'why2_text', 'why3_title', 'why3_text', 'why4_title', 'why4_text',
    'blog_eyebrow', 'contact_title', 'contact_text',
    # Forms / CTAs
    'form_name', 'form_email', 'form_phone', 'form_travellers', 'form_dates', 'form_tour', 'form_message',
    'form_submit', 'form_dates_placeholder', 'form_tour_placeholder', 'whatsapp_text', 'whatsapp_message',
    # Tours page
    'tours_page_title', 'tours_page_eyebrow', 'tours_page_heading', 'tours_page_intro', 'tours_empty',
    'tours_view_button', 'tours_price_prefix',
    # About page
    'about_page_title', 'about_page_eyebrow', 'about_page_heading', 'about_page_intro', 'about_team_empty',
    'about_logo_pdf', 'about_logo_created',
    # Tour detail page
    'tour_detail_overview', 'tour_detail_itinerary', 'tour_detail_included', 'tour_detail_excluded',
    'tour_detail_starting', 'tour_detail_best_season', 'tour_detail_whatsapp', 'tour_detail_enquiry',
    'tour_detail_pdf', 'tour_detail_category_fallback',
    # Footer / public labels
    'footer_explore', 'footer_contact', 'footer_qr', 'footer_instagram_button',
]

MAX_TEXT_LENGTHS = {
    'site_title': 300,
    'meta_description': 500,
    'og_title': 300,
    'og_description': 1000,
    'hero_title': 300,
    'hero_subtitle': 3000,
    'home_about_text': 5000,
    'home_why_text': 5000,
    'contact_text': 5000,
    'whatsapp_message': 2000,
}

SECTION_STYLE_DEFAULTS = {
    'hero': {
        'background_color': '#14532d', 'heading_color': '#ffffff', 'body_color': '#f3f4f6',
        'eyebrow_color': '#fde68a', 'heading_weight': 800, 'body_weight': 400,
        'heading_italic': False, 'body_italic': False, 'overlay_color': '#000000', 'overlay_opacity': 55,
    },
    'home_about': {
        'background_color': '#ffffff', 'heading_color': '#78350f', 'body_color': '#374151',
        'eyebrow_color': '#166534', 'heading_weight': 800, 'body_weight': 400,
        'heading_italic': False, 'body_italic': False, 'overlay_color': '#000000', 'overlay_opacity': 0,
    },
    'home_tours': {
        'background_color': '#ffffff', 'heading_color': '#166534', 'body_color': '#4b5563',
        'eyebrow_color': '#166534', 'heading_weight': 800, 'body_weight': 400,
        'heading_italic': False, 'body_italic': False, 'overlay_color': '#000000', 'overlay_opacity': 0,
    },
    'home_why': {
        'background_color': '#14532d', 'heading_color': '#ffffff', 'body_color': '#dcfce7',
        'eyebrow_color': '#fcd34d', 'heading_weight': 800, 'body_weight': 400,
        'heading_italic': False, 'body_italic': False, 'overlay_color': '#000000', 'overlay_opacity': 0,
    },
    'home_blog': {
        'background_color': '#ffffff', 'heading_color': '#166534', 'body_color': '#4b5563',
        'eyebrow_color': '#78350f', 'heading_weight': 800, 'body_weight': 400,
        'heading_italic': False, 'body_italic': False, 'overlay_color': '#000000', 'overlay_opacity': 0,
    },
    'home_contact': {
        'background_color': '#e5e7eb', 'heading_color': '#166534', 'body_color': '#4b5563',
        'eyebrow_color': '#166534', 'heading_weight': 800, 'body_weight': 400,
        'heading_italic': False, 'body_italic': False, 'overlay_color': '#000000', 'overlay_opacity': 0,
    },
    'about_header': {
        'background_color': '#14532d', 'heading_color': '#ffffff', 'body_color': '#dcfce7',
        'eyebrow_color': '#fcd34d', 'heading_weight': 800, 'body_weight': 400,
        'heading_italic': False, 'body_italic': False, 'overlay_color': '#000000', 'overlay_opacity': 0,
    },
    'about_belief': {
        'background_color': '#ffffff', 'heading_color': '#78350f', 'body_color': '#374151',
        'eyebrow_color': '#92400e', 'heading_weight': 800, 'body_weight': 400,
        'heading_italic': False, 'body_italic': False, 'overlay_color': '#000000', 'overlay_opacity': 0,
    },
    'about_pillars': {
        'background_color': '#ffffff', 'heading_color': '#14532d', 'body_color': '#4b5563',
        'eyebrow_color': '#166534', 'heading_weight': 800, 'body_weight': 400,
        'heading_italic': False, 'body_italic': False, 'overlay_color': '#000000', 'overlay_opacity': 0,
    },
    'about_extra1': {
        'background_color': '#ffffff', 'heading_color': '#166534', 'body_color': '#374151',
        'eyebrow_color': '#166534', 'heading_weight': 800, 'body_weight': 400,
        'heading_italic': False, 'body_italic': False, 'overlay_color': '#000000', 'overlay_opacity': 0,
    },
    'about_extra2': {
        'background_color': '#14532d', 'heading_color': '#ffffff', 'body_color': '#dcfce7',
        'eyebrow_color': '#fcd34d', 'heading_weight': 800, 'body_weight': 400,
        'heading_italic': False, 'body_italic': False, 'overlay_color': '#000000', 'overlay_opacity': 0,
    },
    'about_team': {
        'background_color': '#ffffff', 'heading_color': '#166534', 'body_color': '#4b5563',
        'eyebrow_color': '#1d4ed8', 'heading_weight': 800, 'body_weight': 400,
        'heading_italic': False, 'body_italic': False, 'overlay_color': '#000000', 'overlay_opacity': 0,
    },
    'about_logo': {
        'background_color': '#ffffff', 'heading_color': '#78350f', 'body_color': '#374151',
        'eyebrow_color': '#6b21a8', 'heading_weight': 800, 'body_weight': 400,
        'heading_italic': False, 'body_italic': False, 'overlay_color': '#000000', 'overlay_opacity': 0,
    },
    'about_blog': {
        'background_color': '#ffffff', 'heading_color': '#78350f', 'body_color': '#374151',
        'eyebrow_color': '#1d4ed8', 'heading_weight': 800, 'body_weight': 400,
        'heading_italic': False, 'body_italic': False, 'overlay_color': '#000000', 'overlay_opacity': 0,
    },
    'footer': {
        'background_color': '#78350f', 'heading_color': '#ffffff', 'body_color': '#fef3c7',
        'eyebrow_color': '#fef3c7', 'heading_weight': 800, 'body_weight': 400,
        'heading_italic': False, 'body_italic': False, 'overlay_color': '#000000', 'overlay_opacity': 0,
    },
}

SECTION_LABELS = {
    'hero': 'Home — Hero', 'home_about': 'Home — About', 'home_tours': 'Home — Experiences',
    'home_why': 'Home — Why RI BUROM', 'home_blog': 'Home — Blog', 'home_contact': 'Home — Contact',
    'about_header': 'About — Header', 'about_belief': 'About — Belief / Mission',
    'about_pillars': 'About — Nature / Culture / Community', 'about_extra1': 'About — Extra Section 1',
    'about_extra2': 'About — Extra Section 2', 'about_team': 'About — Team',
    'about_logo': 'About — Logo Meaning', 'about_blog': 'About — Blog', 'footer': 'Footer',
}


def _with_defaults(cfg):
    cfg.setdefault('theme', {})
    cfg['theme'].setdefault('sections', {})
    for key, defaults in SECTION_STYLE_DEFAULTS.items():
        cfg['theme']['sections'][key] = {**deepcopy(defaults), **(cfg['theme']['sections'].get(key) or {})}
    cfg.setdefault('content', {})
    cfg['content'].setdefault('about_page_heading', '')
    cfg['content'].setdefault('footer_instagram_button', 'Follow us on Instagram')
    return cfg


def owner_required(fn):
    @wraps(fn)
    def wrapped(*args, **kwargs):
        user = get_current_user()
        if user is None:
            return redirect(url_for('admin_login', next=request.path))
        if user.role != 'owner':
            abort(403)
        return fn(*args, **kwargs)
    return wrapped


def login_required(fn):
    @wraps(fn)
    def wrapped(*args, **kwargs):
        user = get_current_user()
        if user is None:
            return redirect(url_for('admin_login', next=request.path))
        return fn(*args, **kwargs)
    return wrapped


def _get_context(area):
    user = get_current_user()
    packages = Package.query.order_by(Package.sort_order.asc(), Package.id.desc()).all()
    messages = Message.query.order_by(Message.id.desc()).all() if user.has_permission('view_messages') else []
    unread = Message.query.filter_by(is_read=False).count() if user.has_permission('view_messages') else 0
    team = TeamMember.query.order_by(TeamMember.sort_order.asc(), TeamMember.id.asc()).all() if user.has_permission('manage_team') else []
    return {
        'area': area,
        'current_user': user,
        'packages': packages,
        'messages': messages,
        'unread_count': unread,
        'team': team,
        'settings': get_site_settings(),
        'about': db_get(AboutContent, 1),
        'about_sections': AboutSection.query.order_by(AboutSection.sort_order.asc(), AboutSection.id.asc()).all(),
        'user_count': User.query.count() if user.role == 'owner' else 0,
        'users': User.query.order_by(User.username.asc()).all() if user.role == 'owner' else [],
        'audits': AuditLog.query.order_by(AuditLog.id.desc()).limit(50).all() if user.has_permission('view_audit_log') else [],
        'storage_backend': __import__('storage').STORAGE_BACKEND,
        'permission_labels': PERMISSION_LABELS,
        'permission_keys': PERMISSION_KEYS,
        'role_labels': ROLE_LABELS,
    }


def db_get(model, ident):
    return model.query.get(ident)


def _normalize_sections(cfg):
    cfg = _with_defaults(cfg)
    return cfg


def register_workspace(flask_app):
    if getattr(flask_app, '_ri_burom_workspace_registered', False):
        return
    flask_app._ri_burom_workspace_registered = True

    @flask_app.before_request
    def _redirect_legacy_admin():
        if request.path == '/admin' and request.method == 'GET':
            if get_current_user() is not None:
                return redirect(url_for('workspace_operations'))

    @flask_app.route('/workspace')
    @login_required
    def workspace_operations():
        context = _get_context('operations')
        return render_template('workspace.html', **context)

    @flask_app.route('/workspace/cms')
    @owner_required
    def workspace_cms():
        settings = get_site_settings()
        public = _normalize_sections(get_public_config(settings))
        context = _get_context('cms')
        context.update({'public': public, 'section_styles': public['theme']['sections'], 'section_labels': SECTION_LABELS})
        return render_template('workspace.html', **context)

    @flask_app.route('/workspace/administration')
    @owner_required
    def workspace_administration():
        context = _get_context('administration')
        return render_template('workspace.html', **context)

    @flask_app.route('/workspace/developer')
    @owner_required
    def workspace_developer():
        context = _get_context('developer')
        context['public'] = _normalize_sections(get_public_config(get_site_settings()))
        return render_template('workspace.html', **context)

    @flask_app.route('/workspace/cms/save-content', methods=['POST'])
    @owner_required
    def workspace_cms_save_content():
        settings = get_site_settings()
        cfg = _normalize_sections(get_public_config(settings))
        for field in CONTENT_FIELDS:
            if field in request.form:
                value = (request.form.get(field) or '').strip()
                if len(value) > MAX_TEXT_LENGTHS.get(field, 20000):
                    flash(f'{field.replace("_", " ").title()} is too long.', 'error')
                    return redirect(url_for('workspace_cms'))
                cfg['content'][field] = value
        cfg['content'].setdefault('about_page_heading', '')
        cfg['content'].setdefault('footer_instagram_button', 'Follow us on Instagram')
        settings.public_config_json = json.dumps(cfg, ensure_ascii=False)
        add_audit('updated', 'cms_content', 1, 'Public-facing text content')
        db.session.commit()
        flash('Public website text saved.', 'success')
        return redirect(url_for('workspace_cms'))

    @flask_app.route('/workspace/cms/save-sections', methods=['POST'])
    @owner_required
    def workspace_cms_save_sections():
        settings = get_site_settings()
        cfg = _normalize_sections(get_public_config(settings))
        sections = cfg['theme']['sections']
        for key in SECTION_STYLE_DEFAULTS:
            current = sections[key]
            for field in ('background_color', 'heading_color', 'body_color', 'eyebrow_color', 'overlay_color'):
                value = request.form.get(f'{key}__{field}')
                if value:
                    current[field] = _safe_hex(value, current[field])
            for field in ('heading_weight', 'body_weight', 'overlay_opacity'):
                value = request.form.get(f'{key}__{field}')
                try:
                    number = int(value)
                except (TypeError, ValueError):
                    number = current[field]
                if field == 'overlay_opacity':
                    number = max(0, min(90, number))
                else:
                    number = max(300, min(900, number))
                current[field] = number
            current['heading_italic'] = bool(request.form.get(f'{key}__heading_italic'))
            current['body_italic'] = bool(request.form.get(f'{key}__body_italic'))
        settings.public_config_json = json.dumps(cfg, ensure_ascii=False)
        add_audit('updated', 'cms_section_styles', 1, 'Section-specific colours, weight and italic settings')
        db.session.commit()
        flash('Section appearance settings saved.', 'success')
        return redirect(url_for('workspace_cms'))

    @flask_app.route('/workspace/cms/save-home-structure', methods=['POST'])
    @owner_required
    def workspace_cms_save_home_structure():
        settings = get_site_settings()
        cfg = _normalize_sections(get_public_config(settings))
        valid = ['hero', 'about', 'tours', 'why', 'blog', 'contact']
        try:
            order = json.loads(request.form.get('home_section_order') or '[]')
        except (TypeError, ValueError, json.JSONDecodeError):
            order = []
        order = [key for key in order if key in valid]
        order.extend([key for key in valid if key not in order])
        try:
            visibility = json.loads(request.form.get('home_section_visibility') or '{}')
        except (TypeError, ValueError, json.JSONDecodeError):
            visibility = {}
        cfg.setdefault('home', {})
        cfg['home']['order'] = order
        cfg['home']['visibility'] = {key: bool(visibility.get(key, True)) for key in valid}
        settings.public_config_json = json.dumps(cfg, ensure_ascii=False)
        add_audit('updated', 'cms_home_structure', 1, ', '.join(order))
        db.session.commit()
        flash('Homepage structure saved.', 'success')
        return redirect(url_for('workspace_cms'))
