"""Disposable, localhost-only CMS browser fixtures; all data is in memory."""
from tests.ui_preview import app, db
from flask import session, redirect
from models import User, SiteSettings
from cms_media_models import MediaAsset
from control_room_models import LibraryVideo

with app.app_context():
    for name, permissions in [('owner', None), ('media', '["manage_media"]'), ('content', '["manage_about"]')]:
        db.session.add(User(username='qa-' + name, full_name='QA ' + name,
            password_hash='disabled', role='owner' if name == 'owner' else 'content_manager',
            permissions_json=permissions))
    db.session.add_all([MediaAsset(path='default.jpg', title='QA shared photograph'),
                       MediaAsset(path='uploads/qa-second.jpg', title='QA second photograph'),
                       LibraryVideo(path='uploads/qa-live.mp4', title='QA live opening film', byte_size=20)])
    db.session.get(SiteSettings, 1).hero_animation_video = 'uploads/qa-live.mp4'
    db.session.commit()


@app.get('/__qa/session/<role>')
def qa_session(role):
    person = User.query.filter_by(username='qa-' + role).first_or_404()
    session.clear()
    session['user_id'] = person.id
    session['session_version'] = person.session_version
    return redirect('/workspace/control/media')


if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5055, use_reloader=False)
