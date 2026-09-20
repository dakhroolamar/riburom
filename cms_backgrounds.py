"""Per-section public background and gallery image controls for the RI BUROM CMS."""

from functools import wraps
import json

from flask import abort, flash, jsonify, redirect, render_template, request, url_for

from app import add_audit, get_current_user, get_public_config, get_site_settings
from config_concurrency import public_config_token, public_config_token_matches
from indexnow import notify_indexnow_cms_change
from models import db
from storage import delete_media, imgsrc, save_image

SECTION_BACKGROUND_LABELS = {
    'hero': 'Home — Hero', 'home_about': 'Home — About', 'home_tours': 'Home — Experiences',
    'home_why': 'Home — Why RI BUROM', 'home_blog': 'Home — Blog', 'home_contact': 'Home — Contact',
    'about_header': 'About — Header', 'about_belief': 'About — Belief / Mission',
    'about_pillars': 'About — Nature / Culture / Community', 'about_extra1': 'About — Extra Section 1',
    'about_extra2': 'About — Extra Section 2', 'about_team': 'About — Team',
    'about_logo': 'About — Logo Meaning', 'about_blog': 'About — Blog', 'footer': 'Footer',
}

GALLERY_LABELS = {
    'home_gallery': 'Home — River Photo Gallery',
    'home_about_gallery': 'Home — About Flip Gallery',
}
GALLERY_LIMIT = 10


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


def _get_galleries(settings):
    cfg = get_public_config(settings)
    galleries = cfg.get('theme', {}).get('galleries') or {}
    return {
        key: [value for value in (galleries.get(key) or []) if value]
        for key in GALLERY_LABELS
    }


def register_section_backgrounds(flask_app):
    if getattr(flask_app, '_ri_burom_section_backgrounds_registered', False):
        return
    flask_app._ri_burom_section_backgrounds_registered = True

    @flask_app.route('/api/public-section-backgrounds')
    def public_section_backgrounds():
        settings = get_site_settings()
        cfg = get_public_config(settings)
        sections = cfg.get('theme', {}).get('sections') or {}
        galleries = _get_galleries(settings)
        from cms_pages import collection_media
        media_details = {key: collection_media(key) for key in GALLERY_LABELS}
        for key, items in media_details.items():
            if items:
                galleries[key] = [item['src'] for item in items]
        return jsonify({
            'media_details': media_details,
            'backgrounds': {
                key: imgsrc(value)
                for key, value in _get_backgrounds(settings).items()
                if value
            },
            'galleries': {
                key: [imgsrc(value) for value in values if value]
                for key, values in galleries.items()
            },
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
        return render_template(
            'cms_backgrounds.html',
            section_labels=SECTION_BACKGROUND_LABELS,
            section_backgrounds=_get_backgrounds(settings),
            gallery_labels=GALLERY_LABELS,
            section_galleries=_get_galleries(settings),
            gallery_limit=GALLERY_LIMIT,
            settings=settings,
            public_config_token=public_config_token(settings),
        )

    @flask_app.route('/workspace/cms/backgrounds/save', methods=['POST'])
    @_media_required
    def workspace_cms_backgrounds_save():
        section_key = (request.form.get('section_key') or '').strip()
        if section_key not in SECTION_BACKGROUND_LABELS:
            abort(400)
        settings = get_site_settings()
        if not public_config_token_matches(settings, request.form.get('public_config_token')):
            flash('The public configuration changed after this page was opened. Reload the background editor and apply your change again.', 'error')
            return redirect(url_for('workspace_cms_backgrounds'))
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
        notify_indexnow_cms_change(section_key)
        new_value = backgrounds.get(section_key)
        if old_value and old_value != new_value:
            delete_media(old_value)
        flash(f'{SECTION_BACKGROUND_LABELS[section_key]} background updated.', 'success')
        return redirect(url_for('workspace_cms_backgrounds'))

    @flask_app.route('/workspace/cms/galleries/save', methods=['POST'])
    @_media_required
    def workspace_cms_galleries_save():
        gallery_key = (request.form.get('gallery_key') or '').strip()
        if gallery_key not in GALLERY_LABELS:
            abort(400)
        settings = get_site_settings()
        if not public_config_token_matches(settings, request.form.get('public_config_token')):
            flash('The public configuration changed after this page was opened. Reload the gallery editor and apply your change again.', 'error')
            return redirect(url_for('workspace_cms_backgrounds'))

        files = [item for item in request.files.getlist('images') if item and item.filename]
        if not files:
            flash('Please select at least one gallery image to upload.', 'error')
            return redirect(url_for('workspace_cms_backgrounds'))

        cfg = get_public_config(settings)
        theme = cfg.setdefault('theme', {})
        galleries = theme.setdefault('galleries', {})
        current = [value for value in (galleries.get(gallery_key) or []) if value]
        replace_gallery = bool(request.form.get('replace_gallery'))
        target_count = len(files) if replace_gallery else len(current) + len(files)
        if target_count > GALLERY_LIMIT:
            remaining = GALLERY_LIMIT if replace_gallery else max(0, GALLERY_LIMIT - len(current))
            flash(f'{GALLERY_LABELS[gallery_key]} accepts up to {GALLERY_LIMIT} images. You can add {remaining} more right now.', 'error')
            return redirect(url_for('workspace_cms_backgrounds'))

        saved = []
        try:
            for file_storage in files:
                value = save_image(file_storage)
                if not value:
                    raise ValueError('One of the selected files could not be saved.')
                saved.append(value)
        except ValueError as exc:
            for value in saved:
                delete_media(value)
            flash(str(exc), 'error')
            return redirect(url_for('workspace_cms_backgrounds'))

        old_values = list(current)
        new_values = saved if replace_gallery else current + saved
        galleries[gallery_key] = new_values
        settings.public_config_json = json.dumps(cfg, ensure_ascii=False)
        add_audit('updated', 'cms_gallery', 1, f'updated {gallery_key} with {len(new_values)} images')
        db.session.commit()
        notify_indexnow_cms_change(gallery_key)

        if replace_gallery:
            for value in old_values:
                if value not in new_values:
                    delete_media(value)

        flash(f'{GALLERY_LABELS[gallery_key]} updated with {len(new_values)} image(s).', 'success')
        return redirect(url_for('workspace_cms_backgrounds'))

    @flask_app.route('/workspace/cms/galleries/remove', methods=['POST'])
    @_media_required
    def workspace_cms_galleries_remove():
        gallery_key = (request.form.get('gallery_key') or '').strip()
        if gallery_key not in GALLERY_LABELS:
            abort(400)
        try:
            image_index = int(request.form.get('image_index', '-1'))
        except ValueError:
            abort(400)

        settings = get_site_settings()
        if not public_config_token_matches(settings, request.form.get('public_config_token')):
            flash('The public configuration changed after this page was opened. Reload the gallery editor and apply your change again.', 'error')
            return redirect(url_for('workspace_cms_backgrounds'))

        cfg = get_public_config(settings)
        theme = cfg.setdefault('theme', {})
        galleries = theme.setdefault('galleries', {})
        current = [value for value in (galleries.get(gallery_key) or []) if value]
        if image_index < 0 or image_index >= len(current):
            abort(400)
        removed = current.pop(image_index)
        if current:
            galleries[gallery_key] = current
        else:
            galleries.pop(gallery_key, None)
        settings.public_config_json = json.dumps(cfg, ensure_ascii=False)
        add_audit('updated', 'cms_gallery', 1, f'removed image {image_index + 1} from {gallery_key}')
        db.session.commit()
        notify_indexnow_cms_change(gallery_key)
        delete_media(removed)
        flash(f'Image removed from {GALLERY_LABELS[gallery_key]}.', 'success')
        return redirect(url_for('workspace_cms_backgrounds'))
