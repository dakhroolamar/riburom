"""Per-section public background image controls for the RI BUROM CMS."""

from functools import wraps
import json

from flask import abort, flash, jsonify, redirect, render_template, request, url_for

from app import add_audit, get_current_user, get_public_config, get_site_settings
from models import db
from storage import delete_media, save_image

SECTION_BACKGROUND_LABELS = {
    'hero': 'Home — Hero', 'home_about': 'Home — About', 'home_tours': 'Home — Experiences',
    'home_why': 'Home — Why RI BUROM', 'home_blog': 'Home — Blog', 'home_contact': 'Home — Contact',
    'about_header': 'About — Header', 'about_belief': 'About — Belief / Mission',
    'about_pillars': 'About — Nature / Culture / Community', 'about_extra1': 'About — Extra Section 1',
    'about_extra2': 'About — Extra Section 2', 'about_team': 'About — Team',
    'about_logo': 'About — Logo Meaning', 'about_blog': 'About — Blog', 'footer': 'Footer',
}


def _media_required(view_func):
    @wraps(view_func)
    def wrapped(*args, **kwargs):
        user = get_current_user()
        if user is None:
            return redirect(url_for('admin_login', next=request.path))
        if user.role != 'owner' and not user.has_permission('manage_media'):
            abort(403)
        return view_func(*args, **kwargs)
    return wrapped


def _get_backgrounds(settings):
    cfg = get_public_config(settings)
    return cfg.get('theme', {}).get('section_backgrounds') or {}


def register_section_backgrounds(flask_app):
    if getattr(flask_app, '_ri_burom_section_backgrounds_registered', False):
        return
    flask_app._ri_burom_section_backgrounds_registered = True

    @flask_app.route('/api/public-section-backgrounds')
    def public_section_backgrounds():
        settings = get_site_settings()
        cfg = get_public_config(settings)
        sections = cfg.get('theme', {}).get('sections') or {}
        return jsonify({
            'backgrounds': _get_backgrounds(settings),
            'styles': {
                key: {
                    'overlay_color': value.get('overlay_color', '#000000'),
                    'overlay_opacity': value.get('overlay_opacity', 0),
                }
                for key, value in sections.items()
            },
        })

    @flask_app.route('/workspace/cms/backgrounds')
    @_media_required
    def workspace_cms_backgrounds():
        settings = get_site_settings()
        return render_template('cms_backgrounds.html', section_labels=SECTION_BACKGROUND_LABELS,
                               section_backgrounds=_get_backgrounds(settings), settings=settings)

    @flask_app.route('/workspace/cms/backgrounds/save', methods=['POST'])
    @_media_required
    def workspace_cms_backgrounds_save():
        section_key = (request.form.get('section_key') or '').strip()
        if section_key not in SECTION_BACKGROUND_LABELS:
            abort(400)
        settings = get_site_settings()
        cfg = get_public_config(settings)
        theme = cfg.setdefault('theme', {})
        backgrounds = theme.setdefault('section_backgrounds', {})
        old_value = backgrounds.get(section_key)
        if request.form.get('remove_background'):
            backgrounds.pop(section_key, None)
            action_detail = f'removed background image for {section_key}'
        else:
            try:
                new_value = save_image(request.files.get('image'))
            except ValueError as exc:
                flash(str(exc), 'error')
                return redirect(url_for('workspace_cms_backgrounds'))
            if not new_value:
                flash('Please select an image to upload.', 'error')
                return redirect(url_for('workspace_cms_backgrounds'))
            backgrounds[section_key] = new_value
            action_detail = f'updated background image for {section_key}'
        settings.public_config_json = json.dumps(cfg, ensure_ascii=False)
        add_audit('updated', 'cms_section_background', 1, action_detail)
        db.session.commit()
        new_value = backgrounds.get(section_key)
        if old_value and old_value != new_value:
            delete_media(old_value)
        flash(f'{SECTION_BACKGROUND_LABELS[section_key]} background updated.', 'success')
        return redirect(url_for('workspace_cms_backgrounds'))
