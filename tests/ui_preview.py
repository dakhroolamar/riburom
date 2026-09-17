"""Local-only visual fixtures. Run with python -m tests.ui_preview.

Never loads .env or a production connection. All data exists in memory.
"""
import os

for key in tuple(os.environ):
    if any(word in key for word in ('DATABASE', 'BREVO', 'SMTP', 'CLOUDINARY', 'OWNER', 'REDIS', 'NOTIFICATION', 'ADMIN_PASSWORD')):
        os.environ.pop(key)
os.environ.update(APP_ENV='testing', TESTING='1', DATABASE_URL='sqlite://',
                  SECRET_KEY='visual-preview-only', PYTHON_DOTENV_DISABLED='1',
                  RATELIMIT_STORAGE_URI='memory://')
import dotenv
dotenv.load_dotenv = lambda *args, **kwargs: False

from app import app, db

# Visual edits must be visible without restarting this isolated preview.
app.config['TEMPLATES_AUTO_RELOAD'] = True
app.jinja_env.auto_reload = True

@app.after_request
def visual_no_cache(response):
    response.headers['Cache-Control'] = 'no-store'
    return response

import wsgi  # Compose the same feature modules as production, on the local DB.
from flask import Response, render_template
from models import Package, SiteSettings, seed_defaults
from marketplace_models import Provider, Service, ServiceCategory

with app.app_context():
    db.create_all()
    seed_defaults()
    settings = SiteSettings.query.first()
    settings.blog_enabled = True
    settings.blog_show_home = True
    settings.blog_title = 'Stories from the hills'
    settings.blog_excerpt = 'A local preview of the community story, supplied through the existing CMS fields.'
    settings.blog_url = '/about'
    settings.blog_image = 'default.jpg'
    titles = ['True Colours of the Jaintia', 'Sacred Forest Trail',
              'Meghalaya Adventure & Discovery – Seven Nights Eight Days']
    for i, title in enumerate(titles):
        db.session.add(Package(title=title, slug=f'visual-tour-{i}',
            description='A journey through the landscapes and living traditions of Meghalaya. Take time to explore, meet local people and discover the stories of the hills.',
            location='Meghalaya', duration='4 N / 5 D', difficulty='Easy',
            category='Adventure & cultural tour', price='19,999', best_season='July',
            itinerary='Arrive and settle in.\nExplore with a local guide.\nReturn at your own pace.',
            included='Local guiding and accommodation', excluded='Flights and personal expenses',
            image_file='http://127.0.0.1:5055/__visual/poster.svg', published=True, featured=True))
    provider = Provider(name='Meghalaya Community Journeys', slug='visual-provider',
        description='Local knowledge, thoughtful journeys and a warm welcome to the hills.',
        status='APPROVED', is_active=True, image_url='default.jpg')
    db.session.add(provider)
    category = ServiceCategory(name='Local guiding', slug='local-guiding', is_active=True)
    db.session.add(category)
    db.session.flush()
    db.session.add(Service(provider_id=provider.id, category_id=category.id,
        name='A day in the hills', slug='day-in-hills',
        description='Explore at your own pace with a local guide.', status='PUBLISHED'))
    db.session.commit()

@app.get('/__visual/poster.svg')
def visual_poster():
    # Deliberately busy artwork stresses separation of image typography and H1.
    return Response('''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 600">
      <path fill="#cfb677" d="M0 0h1000v600H0z"/>
      <path fill="#24523c" d="m0 450 250-400 190 240 210-200 350 360v150H0z"/>
      <path fill="#61afc6" d="M540 190 390 600h220z"/>
      <g font-family="Georgia" text-anchor="middle" fill="#f7f4e9">
        <text x="500" y="115" font-size="58">RI BUROM · VISUAL TEST</text>
        <text x="500" y="380" font-size="85">JULY SPECIAL</text>
        <text x="500" y="485" font-size="62">TRUE COLOURS</text>
        <text x="500" y="550" font-size="36">4 NIGHTS · 5 DAYS · 19,999</text>
      </g></svg>''', mimetype='image/svg+xml')

@app.get('/__visual/empty-marketplace')
def visual_empty_marketplace():
    return render_template('marketplace_public.html', providers=[])

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5055, use_reloader=False)
