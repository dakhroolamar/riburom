"""Technical SEO helpers and public metadata for RI BUROM."""

import json
from html import escape
from urllib.parse import quote

from flask import request, url_for

from models import Package
from storage import imgsrc

SEO_BASE_URL = "https://riburom.onrender.com"
HOME_TITLE = "RI BUROM Tours & Travels | Meghalaya Tours & Experiences"
HOME_DESCRIPTION = (
    "RI BUROM Tours & Travels creates Meghalaya-rooted tours and travel experiences "
    "connecting travellers with nature, culture, local communities, and the places that make Meghalaya unique."
)
PUBLIC_ENDPOINTS = {"home", "about", "all_tours", "tour_detail"}


def absolute_url(path_or_url):
    value = str(path_or_url or "")
    if value.startswith("http://") or value.startswith("https://"):
        return value
    if not value.startswith("/"):
        value = "/" + value
    return SEO_BASE_URL.rstrip("/") + value


def _clean_description(value, fallback=HOME_DESCRIPTION, limit=160):
    text = " ".join(str(value or "").split()) or fallback
    return text[:limit].rstrip(" .,-")


def _safe_json(value):
    return json.dumps(value, ensure_ascii=False).replace("<", "\\u003c")


def _business_schema(settings):
    name = (settings.footer_business_name or "RI BUROM Tours & Travels").strip()
    schema = {
        "@context": "https://schema.org",
        "@type": "Organization",
        "name": name,
        "url": SEO_BASE_URL,
    }
    logo = settings.hero_logo or settings.header_mark or settings.header_wordmark
    if logo:
        schema["logo"] = absolute_url(imgsrc(logo))
    if settings.footer_phone:
        schema["telephone"] = settings.footer_phone.strip()
    if settings.footer_email:
        schema["email"] = settings.footer_email.strip()
    if settings.footer_address:
        schema["areaServed"] = settings.footer_address.strip()
    if settings.instagram_url and settings.instagram_url.startswith(("http://", "https://")):
        schema["sameAs"] = [settings.instagram_url.strip()]
    return schema


def _page_metadata(app, endpoint):
    settings = app.view_functions.get("get_site_settings") if False else None
    from app import get_site_settings

    site_settings = get_site_settings()
    logo = site_settings.hero_logo or site_settings.header_mark or site_settings.header_wordmark
    metadata = {
        "title": HOME_TITLE,
        "description": HOME_DESCRIPTION,
        "canonical": SEO_BASE_URL + "/",
        "og_type": "website",
        "og_image": absolute_url(imgsrc(logo)) if logo else absolute_url("/static/default.jpg"),
        "schema": _business_schema(site_settings),
    }

    if endpoint == "about":
        from app import get_public_config
        public = get_public_config(site_settings)
        metadata.update(
            title=(public.get("content", {}).get("about_page_title") or "About RI BUROM | Meghalaya Tours & Experiences"),
            description=_clean_description(public.get("content", {}).get("about_page_intro")),
            canonical=SEO_BASE_URL + "/about",
        )
        return metadata

    if endpoint == "all_tours":
        from app import get_public_config
        public = get_public_config(site_settings)
        metadata.update(
            title=(public.get("content", {}).get("tours_page_title") or "Meghalaya Tours & Experiences | RI BUROM"),
            description=_clean_description(public.get("content", {}).get("tours_page_intro")),
            canonical=SEO_BASE_URL + "/all_tours",
        )
        return metadata

    if endpoint == "tour_detail":
        slug = request.view_args.get("slug") if request.view_args else None
        pkg = Package.query.filter_by(slug=slug, published=True).first()
        if pkg:
            description = _clean_description(pkg.description)
            metadata.update(
                title=f"{pkg.title} | RI BUROM Meghalaya Experiences",
                description=description,
                canonical=SEO_BASE_URL + url_for("tour_detail", slug=pkg.slug),
                og_type="website",
                og_image=absolute_url(imgsrc(pkg.image_file)),
                schema={
                    "@context": "https://schema.org",
                    "@type": "TouristTrip",
                    "name": pkg.title,
                    "description": description,
                    "url": SEO_BASE_URL + url_for("tour_detail", slug=pkg.slug),
                    "image": [absolute_url(imgsrc(pkg.image_file))],
                    "provider": _business_schema(site_settings),
                },
            )
            if pkg.location:
                metadata["schema"]["location"] = {
                    "@type": "Place",
                    "name": pkg.location.strip(),
                }
            return metadata

    if endpoint == "home":
        return metadata
    return None


def _seo_markup(app, endpoint):
    metadata = _page_metadata(app, endpoint)
    if not metadata:
        return ""
    title = escape(metadata["title"], quote=True)
    description = escape(metadata["description"], quote=True)
    canonical = escape(metadata["canonical"], quote=True)
    og_image = escape(metadata["og_image"], quote=True)
    og_type = escape(metadata["og_type"], quote=True)
    schema = _safe_json(metadata["schema"])
    return (
        f'<title>{title}</title>'
        f'<meta name="description" content="{description}">'
        f'<link rel="canonical" href="{canonical}">'
        f'<meta property="og:title" content="{title}">'
        f'<meta property="og:description" content="{description}">'
        f'<meta property="og:url" content="{canonical}">'
        f'<meta property="og:type" content="{og_type}">'
        f'<meta property="og:image" content="{og_image}">'
        '<meta name="twitter:card" content="summary_large_image">'
        f'<meta name="twitter:title" content="{title}">'
        f'<meta name="twitter:description" content="{description}">'
        f'<meta name="twitter:image" content="{og_image}">'
        f'<script type="application/ld+json">{schema}</script>'
    )


def _robots_response():
    from flask import Response
    body = (
        "User-agent: *\n"
        "Allow: /\n"
        "Disallow: /admin\n"
        "Disallow: /admin/login\n"
        "Disallow: /workspace\n"
        "Disallow: /workspace/\n"
        "Disallow: /api/\n"
        f"Sitemap: {SEO_BASE_URL}/sitemap.xml\n"
    )
    return Response(body, status=200, mimetype="text/plain")


def _sitemap_response():
    from flask import Response
    from xml.etree.ElementTree import Element, SubElement, tostring

    urlset = Element("urlset", {"xmlns": "http://www.sitemaps.org/schemas/sitemap/0.9"})
    public_urls = [
        (SEO_BASE_URL + "/", None),
        (SEO_BASE_URL + "/about", None),
        (SEO_BASE_URL + "/all_tours", None),
    ]
    for pkg in Package.query.filter_by(published=True).order_by(Package.id.asc()).all():
        public_urls.append((SEO_BASE_URL + url_for("tour_detail", slug=pkg.slug), pkg.updated_at))

    seen = set()
    for loc, lastmod in public_urls:
        if loc in seen:
            continue
        seen.add(loc)
        item = SubElement(urlset, "url")
        SubElement(item, "loc").text = loc
        if lastmod:
            SubElement(item, "lastmod").text = lastmod.date().isoformat()

    xml = tostring(urlset, encoding="utf-8", xml_declaration=True)
    return Response(xml, status=200, mimetype="application/xml")


def register_seo(flask_app):
    """Register technical SEO behavior without changing public page rendering."""
    if getattr(flask_app, "_ri_burom_seo_registered", False):
        return
    flask_app._ri_burom_seo_registered = True

    # app.py already defines these endpoints; replacing their view functions
    # avoids duplicate URL rules and keeps the existing route map intact.
    flask_app.view_functions["robots_txt"] = _robots_response
    flask_app.view_functions["sitemap_xml"] = _sitemap_response

    @flask_app.after_request
    def add_public_seo(response):
        endpoint = request.endpoint
        if endpoint not in PUBLIC_ENDPOINTS or response.status_code != 200:
            return response
        content_type = response.headers.get("Content-Type", "")
        if "text/html" not in content_type:
            return response
        body = response.get_data(as_text=True)
        if "<head" not in body.lower() or "</head>" not in body.lower():
            return response
        marker = "</head>"
        markup = _seo_markup(flask_app, endpoint)
        body = body.replace(marker, markup + marker, 1)
        response.set_data(body)
        return response
