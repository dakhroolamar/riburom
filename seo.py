"""Technical SEO helpers and public metadata for RI BUROM."""

import json
import os
import re
from html import escape

from flask import Response, request, url_for

from marketplace_models import Provider
from models import Package
from storage import imgsrc


SEO_BASE_URL = (
    os.environ.get('PUBLIC_BASE_URL')
    or 'https://riburomtours.com'
).strip().rstrip('/')
HOME_TITLE = "RI BUROM Tours & Travels | Meghalaya Tours & Experiences"
HOME_DESCRIPTION = (
    "RI BUROM Tours & Travels creates Meghalaya-rooted tours and travel experiences "
    "connecting travellers with nature, culture, local communities, and the places that make Meghalaya unique."
)
PUBLIC_PROVIDER_STATUSES = {'APPROVED', 'PUBLISHED', 'ACTIVE'}
PUBLIC_ENDPOINTS = {
    "home", "about", "all_tours", "tour_detail",
    "marketplace_public_index", "marketplace_public_provider",
}


def absolute_url(path_or_url):
    value = str(path_or_url or "")
    if value.startswith(("http://", "https://")):
        return value
    if not value.startswith("/"):
        value = "/" + value
    return SEO_BASE_URL + value


def _clean_description(value, fallback=HOME_DESCRIPTION, limit=160):
    text = " ".join(str(value or "").split()) or fallback
    if len(text) <= limit:
        return text
    return text[:limit].rsplit(" ", 1)[0].rstrip(" .,-") + "…"


def _safe_json(value):
    return json.dumps(value, ensure_ascii=False).replace("<", "\\u003c")


def _business_schema(settings):
    name = (settings.footer_business_name or "RI BUROM Tours & Travels").strip()
    schema = {"@context": "https://schema.org", "@type": "Organization", "name": name, "url": SEO_BASE_URL}
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


def _page_metadata(endpoint):
    from app import get_public_config, get_site_settings

    settings = get_site_settings()
    public = get_public_config(settings)
    content = public.get("content", {})
    logo = settings.hero_logo or settings.header_mark or settings.header_wordmark
    metadata = {
        "title": content.get("site_title") or HOME_TITLE,
        "description": _clean_description(content.get("meta_description"), HOME_DESCRIPTION),
        "canonical": SEO_BASE_URL + "/",
        "og_type": "website",
        "og_image": absolute_url(imgsrc(logo)),
        "schema": _business_schema(settings),
    }

    if endpoint == "about":
        metadata.update(
            title=(content.get("about_page_title") or "About RI BUROM | Meghalaya Tours & Experiences"),
            description=_clean_description(content.get("about_page_intro")),
            canonical=SEO_BASE_URL + "/about",
        )
    elif endpoint == "all_tours":
        metadata.update(
            title=(content.get("tours_page_title") or "Meghalaya Tours & Experiences | RI BUROM"),
            description=_clean_description(content.get("tours_page_intro")),
            canonical=SEO_BASE_URL + "/all_tours",
        )
    elif endpoint == "tour_detail":
        slug = request.view_args.get("slug") if request.view_args else None
        pkg = Package.query.filter_by(slug=slug, published=True).first()
        if pkg:
            description = _clean_description(pkg.description)
            canonical = SEO_BASE_URL + url_for("tour_detail", slug=pkg.slug)
            metadata.update(
                title=f"{pkg.title} | RI BUROM Meghalaya Experiences",
                description=description,
                canonical=canonical,
                og_type="website",
                og_image=absolute_url(imgsrc(pkg.image_file)),
                schema={
                    "@context": "https://schema.org",
                    "@type": "TouristTrip",
                    "name": pkg.title,
                    "description": description,
                    "url": canonical,
                    "image": [absolute_url(imgsrc(pkg.image_file))],
                    "provider": _business_schema(settings),
                },
            )
            if pkg.location:
                metadata["schema"]["location"] = {"@type": "Place", "name": pkg.location.strip()}
    elif endpoint == "marketplace_public_index":
        canonical = SEO_BASE_URL + "/marketplace"
        metadata.update(
            title="Meghalaya Tourism Marketplace | RI BUROM",
            description=_clean_description(
                "Discover local tourism providers and services across Meghalaya and send a structured enquiry through RI BUROM."
            ),
            canonical=canonical,
            schema={
                "@context": "https://schema.org",
                "@type": "CollectionPage",
                "name": "RI BUROM Meghalaya Tourism Marketplace",
                "url": canonical,
                "isPartOf": _business_schema(settings),
            },
        )
    elif endpoint == "marketplace_public_provider":
        slug = request.view_args.get("slug") if request.view_args else None
        provider = Provider.query.filter(
            Provider.slug == slug,
            Provider.is_active.is_(True),
            Provider.status.in_(PUBLIC_PROVIDER_STATUSES),
        ).first()
        if provider:
            description = _clean_description(
                provider.description,
                f"Explore services from {provider.name} through the RI BUROM Meghalaya tourism marketplace.",
            )
            canonical = SEO_BASE_URL + url_for("marketplace_public_provider", slug=provider.slug)
            metadata.update(
                title=f"{provider.name} | RI BUROM Marketplace",
                description=description,
                canonical=canonical,
                og_image=absolute_url(imgsrc(provider.image_url)),
                schema={
                    "@context": "https://schema.org",
                    "@type": "Organization",
                    "name": provider.name,
                    "description": description,
                    "url": canonical,
                },
            )
            if provider.image_url:
                metadata["schema"]["image"] = absolute_url(imgsrc(provider.image_url))
    return metadata


def _seo_markup(endpoint):
    metadata = _page_metadata(endpoint)
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
    body = (
        "User-agent: *\nAllow: /\nDisallow: /admin\nDisallow: /admin/login\n"
        "Disallow: /workspace\nDisallow: /workspace/\nDisallow: /api/\n"
        f"Sitemap: {SEO_BASE_URL}/sitemap.xml\n"
    )
    return Response(body, status=200, mimetype="text/plain")


def _sitemap_response():
    from xml.etree.ElementTree import Element, SubElement, tostring

    urlset = Element("urlset", {"xmlns": "http://www.sitemaps.org/schemas/sitemap/0.9"})
    public_urls = [
        SEO_BASE_URL + "/", SEO_BASE_URL + "/about",
        SEO_BASE_URL + "/all_tours", SEO_BASE_URL + "/marketplace",
    ]
    public_urls.extend(
        SEO_BASE_URL + url_for("tour_detail", slug=pkg.slug)
        for pkg in Package.query.filter_by(published=True).order_by(Package.id.asc()).all()
    )
    public_urls.extend(
        SEO_BASE_URL + url_for("marketplace_public_provider", slug=provider.slug)
        for provider in Provider.query.filter(
            Provider.is_active.is_(True),
            Provider.status.in_(PUBLIC_PROVIDER_STATUSES),
        ).order_by(Provider.id.asc()).all()
    )
    for loc in dict.fromkeys(public_urls):
        item = SubElement(urlset, "url")
        SubElement(item, "loc").text = loc
    return Response(tostring(urlset, encoding="utf-8", xml_declaration=True), status=200, mimetype="application/xml")


def register_seo(flask_app):
    if getattr(flask_app, "_ri_burom_seo_registered", False):
        return
    flask_app._ri_burom_seo_registered = True
    flask_app.view_functions["robots_txt"] = _robots_response
    flask_app.view_functions["sitemap_xml"] = _sitemap_response

    @flask_app.after_request
    def add_public_seo(response):
        endpoint = request.endpoint
        if endpoint not in PUBLIC_ENDPOINTS or response.status_code != 200:
            return response
        if "text/html" not in response.headers.get("Content-Type", ""):
            return response
        body = response.get_data(as_text=True)
        if "<head" not in body.lower() or "</head>" not in body.lower():
            return response
        patterns = [
            r"<title>.*?</title>",
            r'<meta\s+name=["\']description["\'][^>]*>\s*',
            r'<meta\s+property=["\']og:[^"\']+["\'][^>]*>\s*',
            r'<meta\s+name=["\']twitter:[^"\']+["\'][^>]*>\s*',
            r'<link\s+rel=["\']canonical["\'][^>]*>\s*',
            r'<script\s+type=["\']application/ld\+json["\'][^>]*>.*?</script>\s*',
        ]
        for pattern in patterns:
            body = re.sub(pattern, "", body, flags=re.I | re.S)
        body = body.replace("</head>", _seo_markup(endpoint) + "</head>", 1)
        response.set_data(body)
        return response
