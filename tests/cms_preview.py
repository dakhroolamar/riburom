"""Disposable localhost-only CMS visual fixture; never registered in production."""
from tests.ui_preview import app, db
from models import User, SiteSettings
from cms_media_models import MediaAsset, MediaCollection, MediaCollectionItem
from flask import redirect, session, Response

with app.app_context():
    owner = User(username='visual-editor', full_name='Preview Editor', role='owner', password_hash='disabled')
    db.session.add(owner)
    settings = db.session.get(SiteSettings, 1)
    settings.hero_logo = 'http://127.0.0.1:5055/__visual/logo.svg'
    for n in range(3):
        asset = MediaAsset(path=f'http://127.0.0.1:5055/__visual/poster.svg?image={n}', title=f'Meghalaya photograph {n+1}', alt='Mountain landscape preview', width=1000, height=600)
        db.session.add(asset)
    db.session.flush()
    for key in ('hero', 'home_gallery', 'home_about_gallery', 'tour-1'):
        collection = MediaCollection(key=key,title=key)
        collection.items = [MediaCollectionItem(asset_id=a.id,position=n) for n,a in enumerate(MediaAsset.query.all())]
        db.session.add(collection)
    db.session.commit()
    owner_id = owner.id

@app.get('/__visual/cms')
def cms_login_fixture():
    session['user_id'] = owner_id
    session['session_version'] = 0
    return redirect('/workspace/pages')

@app.get('/__visual/logo.svg')
def cms_logo_fixture():
    return Response('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 600 200"><text x="300" y="110" text-anchor="middle" fill="#185432" font-size="84" font-family="Georgia">RI BUROM</text><text x="300" y="155" text-anchor="middle" fill="#185432" font-size="20">TOURS &amp; TRAVELS · PREVIEW</text></svg>', mimetype='image/svg+xml')

@app.get('/__visual/mobile')
def cms_mobile_fixture():
    return Response('<!doctype html><title>390px homepage QA</title><iframe title="390 pixel homepage" src="/" style="width:390px;height:844px;border:0"></iframe>', mimetype='text/html')

if __name__ == '__main__':
    # The fixture uses a single in-memory SQLite database. Keep the disposable
    # browser server single-threaded so parallel XHRs cannot race one connection.
    app.run(host='127.0.0.1', port=5055, use_reloader=False, threaded=False)
