"""Page-oriented media editing, with bounded uploads and legacy fallbacks."""
import io
import json
from urllib.parse import urlsplit

from flask import abort, jsonify, render_template, request, g
from PIL import Image, UnidentifiedImageError
from sqlalchemy.orm.exc import StaleDataError

from models import db, Package, SiteSettings, AboutContent, TeamMember
from cms_media_models import MediaAsset, MediaCollection, MediaCollectionItem, PageSection
from storage import imgsrc, save_image

COLLECTIONS = {'hero': 'Hero photographs', 'home_gallery': 'Hero / River Gallery',
               'home_about_gallery': 'About RI BUROM', 'footer_partners': 'Partners & Certifications'}
PAGES = {'home': 'Home', 'tours': 'Explore All Tours', 'tour-detail': 'Tour Detail',
         'marketplace': 'Marketplace', 'provider': 'Provider Profile', 'about': 'About Us',
         'contact': 'Contact', 'footer': 'Footer / Global'}
HOME = [('hero', 'Hero'), ('home_gallery', 'Hero / River Gallery'),
        ('home_about_gallery', 'About RI BUROM'), ('home_tours', 'Signature Experiences'),
        ('home_why', 'Why RI BUROM'), ('home_blog', 'Blog / Stories'),
        ('home_contact', 'Enquiry'), ('footer_partners', 'Footer')]
MAX_BYTES = 12 * 1024 * 1024
CONTENT = {
    'hero': ['hero_eyebrow', 'hero_title', 'hero_subtitle', 'hero_primary_button', 'hero_secondary_button'],
    'home_about_gallery': ['home_about_eyebrow', 'home_about_title', 'home_about_text'],
    'home_tours': ['home_tours_eyebrow', 'home_tours_title', 'home_tours_all'],
    'home_why': ['home_why_eyebrow', 'home_why_title', 'home_why_text'] + [f'why{n}_{part}' for n in range(1, 5) for part in ('title', 'text')],
    'home_blog': ['blog_eyebrow'], 'home_contact': ['contact_title', 'contact_text'],
    'tours': ['tours_page_eyebrow', 'tours_page_heading', 'tours_page_intro', 'tours_empty'],
    'tour-detail': ['tour_detail_overview', 'tour_detail_itinerary', 'tour_detail_included', 'tour_detail_excluded'],
    'about': ['about_page_eyebrow', 'about_page_heading', 'about_page_intro'],
    'contact': ['contact_title', 'contact_text', 'form_submit'],
    'footer_partners': ['footer_explore', 'footer_contact', 'footer_qr', 'footer_instagram_button'],
}


def legacy_paths(key):
    from app import get_public_config, get_site_settings
    cfg = get_public_config(get_site_settings())
    theme = cfg.get('theme', {})
    if key in ('home_gallery', 'home_about_gallery'):
        values = theme.get('galleries', {}).get(key) or []
        if values:
            return values
        if key == 'home_about_gallery':
            return [theme.get('section_backgrounds', {}).get('home_about')]
    if key == 'hero':
        about = db.session.get(AboutContent, 1)
        return [theme.get('section_backgrounds', {}).get('hero') or (about.hero_image if about else None)]
    if key.startswith('tour-'):
        package = db.session.get(Package, int(key[5:]))
        return [package.image_file] if package else []
    return []


def delivery(path, width=1200):
    url = imgsrc(path)
    if urlsplit(url).hostname == 'res.cloudinary.com' and '/image/upload/' in url:
        return url.replace('/image/upload/', f'/image/upload/f_auto,q_auto,w_{width},c_limit/', 1)
    return url


def collection_media(key, legacy=True):
    collection = MediaCollection.query.filter_by(key=key).first()
    if collection and collection.items:
        return [dict(id=i.id, src=delivery(i.asset.path), alt=i.asset.alt,
                     caption=i.asset.caption, credit=i.asset.credit,
                     focal_x=i.focal_x, focal_y=i.focal_y, organization=i.organization,
                     url=i.url, label=i.label, new_tab=i.new_tab)
                for i in collection.items if i.visible]
    if not legacy:
        return []
    return [dict(src=delivery(p), alt='', caption='', credit='', focal_x=50, focal_y=50)
            for p in legacy_paths(key) if p]


def tour_cover(package):
    if not hasattr(g, 'cms_tour_covers'):
        g.cms_tour_covers = {}
        for collection in MediaCollection.query.filter(MediaCollection.key.like('tour-%')).all():
            visible = next((item for item in collection.items if item.visible), None)
            if visible:
                g.cms_tour_covers[collection.key] = delivery(visible.asset.path, 800)
    return g.cms_tour_covers.get('tour-' + str(package.id), imgsrc(package.image_file))


def asset_usage(asset):
    uses = [c.title for c in MediaCollection.query.join(MediaCollectionItem)
            .filter(MediaCollectionItem.asset_id == asset.id).all()]
    # Include old CMS references, so registering an existing image never makes it deletable.
    for model, fields in ((Package, ['image_file']), (AboutContent, ['hero_image']),
                         (TeamMember, ['photo_file'])):
        for field in fields:
            if model.query.filter(getattr(model, field) == asset.path).first():
                uses.append('Existing website content')
    settings = db.session.get(SiteSettings, 1)
    if settings:
        for column in SiteSettings.__table__.columns:
            if column.name == 'hero_animation_video':
                continue
            value = getattr(settings, column.name)
            if isinstance(value, str) and asset.path in value:
                uses.append('Site settings')
                break
    from media_lifecycle import marketplace_media_is_referenced
    if marketplace_media_is_referenced(asset.path):
        uses.append('Marketplace')
    return sorted(set(uses))


def register_cms_pages(app):
    from app import add_audit, get_site_settings
    from cms_routes import cms_access_required, cms_media_required

    app.config.setdefault('CMS_COLLECTION_LIMIT', 10)
    app.jinja_env.globals.update(cms_collection_media=collection_media, cms_tour_cover=tour_cover)

    @app.route('/workspace/pages')
    @app.route('/workspace/pages/<page>')
    @cms_access_required
    def cms_pages(page='home'):
        if page not in PAGES:
            abort(404)
        from app import get_public_config
        config = get_public_config(get_site_settings())
        order = config.get('home', {}).get('order', ['hero', 'about', 'tours', 'why', 'blog', 'contact'])
        groups = {'hero': HOME[:2], 'about': HOME[2:3], 'tours': HOME[3:4],
                  'why': HOME[4:5], 'blog': HOME[5:6], 'contact': HOME[6:7]}
        home_sections = [entry for group in dict.fromkeys(order + list(groups)) for entry in groups.get(group, [])] + HOME[7:]
        return render_template('cms_pages.html', pages=PAGES, page=page,
                               sections=home_sections if page == 'home' else [],
                               collections=COLLECTIONS, packages=Package.query.order_by(Package.sort_order).all(),
                               settings=get_site_settings())

    @app.route('/workspace/library')
    @cms_media_required
    def cms_library():
        return render_template('cms_library.html')

    @app.route('/workspace/media-api/content/<section>', methods=['GET', 'POST'])
    def cms_section_content(section):
        from cms_routes import cms_content_required, MAX_TEXT_LENGTHS
        from app import get_public_config
        from config_concurrency import public_config_token, public_config_token_matches
        @cms_content_required
        def handle():
            fields = CONTENT.get(section, [])
            settings = get_site_settings()
            cfg = get_public_config(settings)
            if request.method == 'POST':
                data = request.get_json() or {}
                if not public_config_token_matches(settings, data.get('token')):
                    return jsonify(error='Page content changed. Reload before saving.'), 409
                for name, value in data.get('values', {}).items():
                    if name not in fields or not isinstance(value, str) or len(value) > MAX_TEXT_LENGTHS.get(name, 20000):
                        abort(400)
                    cfg.setdefault('content', {})[name] = value.strip()
                settings.public_config_json = json.dumps(cfg, ensure_ascii=False)
                add_audit('updated', 'cms_content', section, 'Page section text')
                db.session.commit()
            def label(name):
                for prefix in ('home_about_', 'home_tours_', 'home_why_', 'tours_page_', 'about_page_', 'tour_detail_', 'hero_', 'footer_', 'contact_'):
                    if name.startswith(prefix):
                        return name[len(prefix):].replace('_', ' ').capitalize()
                return name.replace('_', ' ').capitalize()
            return jsonify(fields=[dict(name=name, label=label(name), value=cfg.get('content', {}).get(name, '')) for name in fields], token=public_config_token(settings))
        return handle()

    @app.route('/workspace/media-api/assets', methods=['GET', 'POST'])
    @cms_media_required
    def cms_assets():
        if request.method == 'GET':
            query = MediaAsset.query
            term = request.args.get('q', '').strip()[:240]
            if term:
                query = query.filter(MediaAsset.title.ilike('%' + term + '%'))
            rows = query.order_by(MediaAsset.created_at.desc()).limit(200).all()
            return jsonify([dict(id=a.id, title=a.title, src=delivery(a.path, 400),
                                 alt=a.alt, caption=a.caption, credit=a.credit,
                                 width=a.width, height=a.height, byte_size=a.byte_size,
                                 created_at=a.created_at.isoformat(), usage=asset_usage(a)) for a in rows])
        file = request.files.get('image')
        if not file or not file.filename:
            abort(400, 'Choose an image.')
        raw = file.stream.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES:
            abort(413, 'Each photograph must be 12 MB or smaller.')
        try:
            with Image.open(io.BytesIO(raw)) as image:
                width, height = image.size
                if width * height > 40_000_000 or min(width, height) < 16:
                    raise ValueError('Use an image between 16 pixels and 40 megapixels.')
                image.verify()
            file.stream.seek(0)
            path = save_image(file)
        except (ValueError, UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
            abort(400, str(exc))
        except Exception:
            app.logger.exception('CMS image storage failed')
            return jsonify(error='Upload failed. Your existing images are unchanged. Try again.'), 502
        asset = MediaAsset(path=path, title=file.filename[:240], width=width, height=height, byte_size=len(raw))
        db.session.add(asset)
        add_audit('uploaded', 'cms_media', None, asset.title)
        db.session.commit()
        return jsonify(id=asset.id, src=delivery(path, 400)), 201

    @app.route('/workspace/media-api/assets/<int:asset_id>', methods=['POST', 'DELETE'])
    @cms_media_required
    def cms_asset(asset_id):
        asset = db.get_or_404(MediaAsset, asset_id)
        if request.method == 'DELETE':
            if asset_usage(asset):
                return jsonify(error='This image is in use. Remove it from its collections first.'), 409
            # Keep the blob: legacy screens may still reference media outside this registry.
            # Removing a library record must never destroy website media.
            db.session.delete(asset)
        else:
            data = request.get_json() or {}
            for field, limit in [('title', 240), ('alt', 500), ('caption', 1000), ('credit', 500)]:
                if field in data:
                    if not isinstance(data[field], str) or len(data[field]) > limit:
                        abort(400)
                    setattr(asset, field, data[field].strip())
        add_audit('updated', 'cms_media', asset_id, 'Media library updated')
        db.session.commit()
        return jsonify(ok=True)

    @app.route('/workspace/media-api/collections/<key>', methods=['GET', 'POST'])
    @cms_media_required
    def cms_collection(key):
        title = COLLECTIONS.get(key)
        if key.startswith('tour-') and key[5:].isdigit():
            package = db.get_or_404(Package, int(key[5:]))
            title = package.title
        if not title:
            abort(404)
        collection = MediaCollection.query.filter_by(key=key).first()
        if request.method == 'GET':
            return jsonify(version=collection.version if collection else 0,
                           limit=app.config['CMS_COLLECTION_LIMIT'],
                           legacy=[delivery(p, 400) for p in legacy_paths(key) if p],
                           items=[dict(id=i.id, asset_id=i.asset_id, src=delivery(i.asset.path, 400),
                                       alt=i.asset.alt, caption=i.asset.caption, credit=i.asset.credit,
                                       focal_x=i.focal_x, focal_y=i.focal_y, organization=i.organization,
                                       url=i.url, label=i.label, visible=i.visible, new_tab=i.new_tab)
                                  for i in collection.items] if collection else [])
        data = request.get_json() or {}
        if data.get('version') != (collection.version if collection else 0):
            return jsonify(error='Another editor changed this gallery. Reload before saving.'), 409
        items = data.get('items')
        if not isinstance(items, list) or len(items) > app.config['CMS_COLLECTION_LIMIT']:
            abort(400, 'Too many gallery images.')
        validated = []
        for item in items:
            if not isinstance(item, dict):
                abort(400)
            asset = db.session.get(MediaAsset, item.get('asset_id'))
            if not asset:
                abort(400, 'An image is no longer in the library.')
            values = {'asset_id': asset.id}
            for field in ('focal_x', 'focal_y'):
                value = item.get(field, 50)
                if type(value) is not int or not 0 <= value <= 100:
                    abort(400)
                values[field] = value
            for field, limit in [('organization', 240), ('url', 1000), ('label', 240)]:
                value = item.get(field, '')
                if not isinstance(value, str) or len(value) > limit:
                    abort(400)
                values[field] = value.strip()
            url = urlsplit(values['url'])
            if values['url'] and (url.scheme not in ('http', 'https') or not url.netloc):
                abort(400, 'Use a complete https:// website address.')
            for field, default in [('visible', True), ('new_tab', False)]:
                if type(item.get(field, default)) is not bool:
                    abort(400)
                values[field] = item.get(field, default)
            validated.append(values)
        if not collection:
            collection = MediaCollection(key=key, title=title)
            db.session.add(collection)
        else:
            collection.version += 1
        collection.items = [MediaCollectionItem(position=n, **values) for n, values in enumerate(validated)]
        add_audit('updated', 'cms_collection', key, f'{len(items)} gallery images')
        try:
            db.session.commit()
        except StaleDataError:
            db.session.rollback()
            return jsonify(error='Another editor saved first. Reload before saving.'), 409
        return jsonify(ok=True, version=collection.version)

    @app.route('/workspace/media-api/hero-placement', methods=['GET', 'POST'])
    @cms_media_required
    def cms_hero_placement():
        section = PageSection.query.filter_by(page='home', key='hero').first()
        if request.method == 'GET':
            return jsonify(settings=section.settings if section else {}, version=section.version if section else 0)
        data = request.get_json() or {}
        if data.get('version') != (section.version if section else 0):
            return jsonify(error='The logo placement changed. Reload before saving.'), 409
        values = {}
        for device in ('desktop', 'tablet', 'mobile'):
            values[device] = {}
            for field, default, low, high in [('x', 50, 0, 100), ('y', 50, 0, 100), ('size', 60, 20, 90)]:
                value = data.get('settings', {}).get(device, {}).get(field, default)
                if type(value) is not int or not low <= value <= high:
                    abort(400)
                values[device][field] = value
        if not section:
            section = PageSection(page='home', key='hero')
            db.session.add(section)
        section.settings = values
        try:
            db.session.commit()
        except StaleDataError:
            db.session.rollback()
            return jsonify(error='Another editor saved first. Reload before saving.'), 409
        return jsonify(ok=True, version=section.version)

    @app.context_processor
    def cms_public_helpers():
        def placement():
            section = PageSection.query.filter_by(page='home', key='hero').first()
            return section.settings if section else {}
        return {'cms_logo_placement': placement}
