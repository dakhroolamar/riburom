"""Shared appearance controls for the public RI BUROM marketplace."""

import json
from functools import wraps

from flask import abort, flash, redirect, render_template, request, url_for

from app import _safe_hex, add_audit, get_current_user, get_public_config, get_site_settings
from config_concurrency import public_config_token, public_config_token_matches
from models import db


DEFAULT_MARKETPLACE_STYLE = {
    'background_color': '#f8faf8',
    'heading_color': '#173b1d',
    'body_color': '#334155',
    'eyebrow_color': '#166534',
    'heading_weight': 700,
    'body_weight': 400,
    'heading_italic': False,
    'body_italic': False,
    'input_text_color': '#111827',
    'input_border_color': '#cbd5e1',
    'input_focus_color': '#166534',
    'help_color': '#475569',
}


def _style_context():
    settings = get_site_settings()
    cfg = get_public_config(settings) or {}
    theme = cfg.setdefault('theme', {})
    current = {**DEFAULT_MARKETPLACE_STYLE, **(theme.get('marketplace') or {})}
    return settings, cfg, current


def _allowed(permission):
    user = get_current_user()
    return user is not None and (user.role == 'owner' or user.has_permission(permission))


def _permission_required(permission):
    def decorator(fn):
        @wraps(fn)
        def wrapped(*args, **kwargs):
            if get_current_user() is None:
                return redirect(url_for('admin_login', next=request.path))
            if not _allowed(permission):
                abort(403)
            return fn(*args, **kwargs)
        return wrapped
    return decorator


def _save_marketplace_style(success_redirect_endpoint):
    settings, cfg, current = _style_context()
    if not public_config_token_matches(settings, request.form.get('public_config_token')):
        flash('The public configuration changed after this page was opened. Reload the appearance editor and apply your change again.', 'error')
        return redirect(url_for(success_redirect_endpoint))
    section = cfg['theme']['marketplace'] = current

    for field in ('background_color', 'heading_color', 'body_color', 'eyebrow_color',
                  'input_text_color', 'input_border_color', 'input_focus_color', 'help_color'):
        value = request.form.get(field)
        if value:
            section[field] = _safe_hex(value, section[field])

    for field in ('heading_weight', 'body_weight'):
        try:
            value = int(request.form.get(field, section[field]))
        except (TypeError, ValueError):
            value = section[field]
        section[field] = max(300, min(900, value))

    section['heading_italic'] = bool(request.form.get('heading_italic'))
    section['body_italic'] = bool(request.form.get('body_italic'))

    settings.public_config_json = json.dumps(cfg, ensure_ascii=False)
    add_audit('updated', 'marketplace_appearance', 1, 'Public marketplace typography and colour controls')
    db.session.commit()
    flash('Marketplace appearance settings saved.', 'success')
    return redirect(url_for(success_redirect_endpoint))


def register_marketplace_appearance(flask_app):
    if getattr(flask_app, '_ri_burom_marketplace_appearance_registered', False):
        return
    flask_app._ri_burom_marketplace_appearance_registered = True

    @flask_app.context_processor
    def _marketplace_appearance_context():
        return {'marketplace_style': _style_context()[2]}

    @flask_app.route('/workspace/cms/marketplace-appearance')
    @_permission_required('manage_media')
    def workspace_cms_marketplace_appearance():
        settings, _, style = _style_context()
        return render_template(
            'marketplace_appearance.html',
            current_user=get_current_user(),
            style=style,
            public_config_token=public_config_token(settings),
            save_url=url_for('workspace_cms_save_marketplace_appearance'),
            back_url=url_for('workspace_cms'),
            back_label='Content & Appearance',
        )

    @flask_app.route('/workspace/cms/marketplace-appearance/save', methods=['POST'])
    @_permission_required('manage_media')
    def workspace_cms_save_marketplace_appearance():
        return _save_marketplace_style('workspace_cms_marketplace_appearance')

    @flask_app.route('/workspace/marketplace/appearance')
    @_permission_required('manage_marketplace')
    def workspace_marketplace_appearance():
        settings, _, style = _style_context()
        return render_template(
            'marketplace_appearance.html',
            current_user=get_current_user(),
            style=style,
            public_config_token=public_config_token(settings),
            save_url=url_for('workspace_marketplace_save_appearance'),
            back_url=url_for('workspace_marketplace'),
            back_label='Marketplace Control Room',
        )

    @flask_app.route('/workspace/marketplace/appearance/save', methods=['POST'])
    @_permission_required('manage_marketplace')
    def workspace_marketplace_save_appearance():
        return _save_marketplace_style('workspace_marketplace_appearance')
