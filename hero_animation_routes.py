"""CMS controls for the optional homepage hero animation video."""

from flask import flash, redirect, request, url_for

from app import add_audit, app, get_site_settings, permission_required
from models import db
from storage import delete_media, save_video


def register_hero_animation_routes(flask_app):
    @flask_app.route('/workspace/cms/save-hero-animation-video', methods=['POST'])
    @permission_required('manage_media')
    def workspace_cms_save_hero_animation_video():
        settings = get_site_settings()
        old_value = settings.hero_animation_video
        remove_video = bool(request.form.get('remove_hero_animation_video'))

        try:
            new_value = save_video(request.files.get('hero_animation_video'))
        except ValueError as exc:
            flash(str(exc), 'error')
            return redirect(url_for('workspace_cms_media'))

        if new_value:
            settings.hero_animation_video = new_value
            action_details = 'Hero animation video replaced'
        elif remove_video:
            settings.hero_animation_video = None
            action_details = 'Hero animation video removed'
        else:
            flash('Choose a supported video file or use Remove Video.', 'error')
            return redirect(url_for('workspace_cms_media'))

        add_audit('updated', 'hero_animation_video', 1, action_details)
        db.session.commit()

        if old_value and old_value != settings.hero_animation_video:
            delete_media(old_value)

        flash(
            'Hero animation video updated.' if new_value else 'Hero animation video removed.',
            'success',
        )
        return redirect(url_for('workspace_cms_media'))

