"""Technical SEO helpers and public metadata for RI BUROM."""

import json
import re
from html import escape

from flask import Response, request, url_for

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
    if value.startswith(("http://", "https://")):
        return value
    if not value.startswith("/"):
        value = "/" + value
    return SEO_BASE_URL.rstrip("/") + value


def _clean_description(value, fallback=HOME_DESCRIPTION, limit=160):
    text = " ".join(str(value or "").split()) or fallback
    if len(text) <= limit:
        return text
    return text[:limit].rsplit(" ", 1)[0].rstrip(" .,-") + "…"


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


def _page_metadata(endpoint):
    from app import get_public_config, get_site_settings

    settings = get_site_settings()
    logo = settings.hero_logo or settings.header_mark or settings.header_wordmark
    metadata = {
        "title": HOME_TITLE,
        "description": HOME_DESCRIPTION,
        "canonical": SEO_BASE_URL + "/",
        "og_type": "website",
        "og_image": absolute_url(imgsrc(logo)),
        "schema": _business_schema(settings),
    }

    if endpoint == "about":
        public = get_public_config(settings)
        metadata.update(
            title=(public.get("content", {}).get("about_page_title") or "About RI BUROM | Meghalaya Tours & Experiences"),
            description=_clean_description(public.get("content", {}).get("about_page_intro")),
            canonical=SEO_BASE_URL + "/about",
        )
        return metadata

    if endpoint == "all_tours":
        public = get_public_config(settings)
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
        return metadata

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
    from xml.etree.ElementTree import Element, SubElement, tostring

    urlset = Element("urlset", {"xmlns": "http://www.sitemaps.org/schemas/sitemap/0.9"})
    public_urls = [SEO_BASE_URL + "/", SEO_BASE_URL + "/about", SEO_BASE_URL + "/all_tours"]
    public_urls.extend(
        SEO_BASE_URL + url_for("tour_detail", slug=pkg.slug)
        for pkg in Package.query.filter_by(published=True).order_by(Package.id.asc()).all()
    )
    for loc in dict.fromkeys(public_urls):
        item = SubElement(urlset, "url")
        SubElement(item, "loc").text = loc

    xml = tostring(urlset, encoding="utf-8", xml_declaration=True)
    return Response(xml, status=200, mimetype="application/xml")


def register_seo(flask_app):
    """Register technical SEO behavior without changing public page handlers."""
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
        lower = body.lower()
        if "<head" not in lower or "</head>" not in lower:
            return response

        # Remove existing SEO tags from legacy public templates so every page
        # has exactly one authoritative title/description/social/canonical set.
        patterns = [
            r"<title>.*?</title>",
            r'<meta\s+name=["\']description["\'][^>]*>\s*',
            r'<meta\s+property=["\']og:[^"\']+["\'][^>]*>\s*',
            r'<meta\s+name=["\']twitter:[^"\']+["\'][^>]*>\s*',
            r'<link\s+rel=["\']canonical["\'][^>]*>\s*',
            r'<script\s+type=["\']application/ld\+json["\'][^>]*>.*?</script>\s*',
        ]
        for pattern in patterns:
            body = re.sub(pattern, "", body, count=0, flags=re.I | re.S)
        marker = "</head>"
        body = body.replace(marker, _seo_markup(endpoint) + marker, 1)
        response.set_data(body)
        return response
