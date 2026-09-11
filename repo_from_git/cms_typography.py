"""Global public typography controls for the separated CMS workspace."""

from functools import wraps

from flask import abort, flash, redirect, request, url_for

from app import FONT_OPTIONS, _safe_hex, add_audit, app, get_current_user, get_site_settings
from models import db


def _cms_access(fn):
    @wraps(fn)
    def wrapped(*args, **kwargs):
        user = get_current_user()
        if user is None:
            return redirect(url_for('admin_login', next=request.path))
        if user.role != 'owner' and not user.has_permission('manage_media'):
            abort(403)
        return fn(*args, **kwargs)
    return wrapped


def register_typography(flask_app):
    if getattr(flask_app, '_ri_burom_cms_typography_registered', False):
        return
    flask_app._ri_burom_cms_typography_registered = True

    @flask_app.route('/workspace/cms/save-typography', methods=['POST'])
    @_cms_access
    def workspace_cms_save_typography():
        settings = get_site_settings()

        body_font = (request.form.get('body_font') or settings.body_font or 'inter').strip().lower()
        heading_font = (request.form.get('heading_font') or settings.heading_font or 'poppins').strip().lower()
        if body_font not in FONT_OPTIONS:
            body_font = 'inter'
        if heading_font not in FONT_OPTIONS:
            heading_font = 'poppins'

        def bounded_int(name, default, minimum, maximum):
            try:
                return max(minimum, min(maximum, int(request.form.get(name))))
            except (TypeError, ValueError):
                return default

        settings.body_font = body_font
        settings.heading_font = heading_font
        settings.base_font_size = bounded_int('base_font_size', settings.base_font_size or 16, 14, 20)
        settings.heading_scale = bounded_int('heading_scale', settings.heading_scale or 100, 80, 130)
        settings.body_text_color = _safe_hex(request.form.get('body_text_color'), settings.body_text_color or '#1f2937')
        settings.heading_text_color = _safe_hex(request.form.get('heading_text_color'), settings.heading_text_color or '#14532d')
        settings.link_text_color = _safe_hex(request.form.get('link_text_color'), settings.link_text_color or '#166534')

        add_audit(
            'updated',
            'cms_typography',
            1,
            f'body_font={body_font}; heading_font={heading_font}; base={settings.base_font_size}; scale={settings.heading_scale}',
        )
        db.session.commit()
        flash('Global typography saved.', 'success')
        return redirect(url_for('workspace_cms'))
