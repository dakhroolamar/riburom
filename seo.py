"""Technical SEO, structured data, and public discovery helpers for RI BUROM."""

import json
import os
from html import escape
from xml.etree.ElementTree import Element, SubElement, tostring

from flask import Response, g, request, url_for

from marketplace_models import Provider
from models import Package
from storage import imgsrc


SEO_BASE_URL = (
    os.environ.get("PUBLIC_BASE_URL")
    or "https://riburomtours.com"
).strip().rstrip("/")

SITE_NAME = "RI BUROM Tours & Travels"
HOME_TITLE = "RI BUROM Tours & Travels | Meghalaya Tours & Experiences"
HOME_DESCRIPTION = (
    "RI BUROM Tours & Travels creates Meghalaya-rooted tours and travel experiences "
    "connecting travellers with nature, culture, local communities, and the places that make Meghalaya unique."
)
PUBLIC_PROVIDER_STATUSES = {"APPROVED", "PUBLISHED", "ACTIVE"}
PUBLIC_ENDPOINTS = {
    "home",
    "about",
    "all_tours",
    "tour_detail",
    "marketplace_public_index",
    "marketplace_public_provider",
}
PRIVATE_PATH_PREFIXES = (
    "/admin",
    "/workspace",
    "/api/",
)
INDEX_ROBOTS = "index,follow,max-image-preview:large,max-snippet:-1,max-video-preview:-1"


def absolute_url(path_or_url):
    value = str(path_or_url or "").strip()
    if not value:
        return ""
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
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")


def _image_url(value):
    if not value:
        return ""
    return absolute_url(imgsrc(value))


def _business_schema(settings):
    name = (settings.footer_business_name or SITE_NAME).strip()
    schema = {
        "@type": ["TravelAgency", "Organization"],
        "@id": f"{SEO_BASE_URL}/#organization",
        "name": name,
        "url": SEO_BASE_URL + "/",
        "description": HOME_DESCRIPTION,
        "areaServed": {
            "@type": "AdministrativeArea",
            "name": "Meghalaya, India",
        },
    }
    logo = settings.hero_logo or settings.header_mark or settings.header_wordmark
    if logo:
        schema["logo"] = {
            "@type": "ImageObject",
            "url": _image_url(logo),
        }
    if settings.footer_tagline:
        schema["slogan"] = settings.footer_tagline.strip()
    if settings.footer_phone or settings.footer_email:
        contact = {
            "@type": "ContactPoint",
            "contactType": "customer service",
        }
        if settings.footer_phone:
            contact["telephone"] = settings.footer_phone.strip()
        if settings.footer_email:
            contact["email"] = settings.footer_email.strip()
        schema["contactPoint"] = contact
    if settings.footer_address:
        schema["address"] = settings.footer_address.strip()
    if settings.instagram_url and settings.instagram_url.startswith(("http://", "https://")):
        schema["sameAs"] = [settings.instagram_url.strip()]
    return schema


def _website_schema():
    return {
        "@type": "WebSite",
        "@id": f"{SEO_BASE_URL}/#website",
        "url": SEO_BASE_URL + "/",
        "name": SITE_NAME,
        "description": HOME_DESCRIPTION,
        "publisher": {"@id": f"{SEO_BASE_URL}/#organization"},
        "inLanguage": "en-IN",
    }


def _breadcrumb_schema(items, canonical):
    if not items:
        return None
    return {
        "@type": "BreadcrumbList",
        "@id": canonical + "#breadcrumb",
        "itemListElement": [
            {
                "@type": "ListItem",
                "position": position,
                "name": name,
                "item": url,
            }
            for position, (name, url) in enumerate(items, start=1)
        ],
    }


def _webpage_schema(title, description, canonical, page_type="WebPage", breadcrumbs=None, main_entity=None):
    page = {
        "@type": page_type,
        "@id": canonical + "#webpage",
        "url": canonical,
        "name": title,
        "description": description,
        "isPartOf": {"@id": f"{SEO_BASE_URL}/#website"},
        "about": {"@id": f"{SEO_BASE_URL}/#organization"},
        "inLanguage": "en-IN",
    }
    if breadcrumbs:
        page["breadcrumb"] = {"@id": canonical + "#breadcrumb"}
    if main_entity:
        page["mainEntity"] = main_entity
    return page


def _page_metadata(endpoint):
    from app import get_public_config, get_site_settings

    settings = get_site_settings()
    public = get_public_config(settings)
    content = public.get("content", {})
    logo = settings.hero_logo or settings.header_mark or settings.header_wordmark

    title = content.get("site_title") or HOME_TITLE
    description = _clean_description(content.get("meta_description"), HOME_DESCRIPTION)
    canonical = SEO_BASE_URL + "/"
    metadata = {
        "title": title,
        "description": description,
        "canonical": canonical,
        "og_type": "website",
        "og_image": _image_url(logo) or absolute_url("/static/default.jpg"),
        "schemas": [],
    }

    page_type = "WebPage"
    breadcrumbs = None
    main_entity = None
    extra_schemas = []

    if endpoint == "about":
        title = content.get("about_page_title") or "About RI BUROM | Community-Based Tourism in Meghalaya"
        description = _clean_description(content.get("about_page_intro"))
        canonical = SEO_BASE_URL + "/about"
        page_type = "AboutPage"
        breadcrumbs = [
            ("Home", SEO_BASE_URL + "/"),
            ("About", canonical),
        ]

    elif endpoint == "all_tours":
        title = content.get("tours_page_title") or "Meghalaya Tours & Experiences | RI BUROM"
        description = _clean_description(content.get("tours_page_intro"))
        canonical = SEO_BASE_URL + "/all_tours"
        page_type = "CollectionPage"
        breadcrumbs = [
            ("Home", SEO_BASE_URL + "/"),
            ("Tours & Experiences", canonical),
        ]
        packages = Package.query.filter_by(published=True).order_by(
            Package.sort_order.asc(), Package.id.asc()
        ).all()
        if packages:
            item_list_id = canonical + "#experiences"
            main_entity = {"@id": item_list_id}
            extra_schemas.append({
                "@type": "ItemList",
                "@id": item_list_id,
                "name": "RI BUROM Meghalaya tours and experiences",
                "numberOfItems": len(packages),
                "itemListElement": [
                    {
                        "@type": "ListItem",
                        "position": position,
                        "name": pkg.title,
                        "url": SEO_BASE_URL + url_for("tour_detail", slug=pkg.slug),
                    }
                    for position, pkg in enumerate(packages, start=1)
                ],
            })

    elif endpoint == "tour_detail":
        slug = request.view_args.get("slug") if request.view_args else None
        pkg = getattr(g, "seo_package", None)
        if pkg is None:
            pkg = Package.query.filter_by(slug=slug, published=True).first()
        if pkg:
            title = f"{pkg.title} | RI BUROM Meghalaya Experiences"
            description = _clean_description(pkg.description)
            canonical = SEO_BASE_URL + url_for("tour_detail", slug=pkg.slug)
            metadata["og_type"] = "website"
            metadata["og_image"] = _image_url(pkg.image_file) or metadata["og_image"]
            breadcrumbs = [
                ("Home", SEO_BASE_URL + "/"),
                ("Tours & Experiences", SEO_BASE_URL + "/all_tours"),
                (pkg.title, canonical),
            ]
            trip_id = canonical + "#tour"
            main_entity = {"@id": trip_id}
            tourist_trip = {
                "@type": "TouristTrip",
                "@id": trip_id,
                "name": pkg.title,
                "description": description,
                "url": canonical,
                "provider": {"@id": f"{SEO_BASE_URL}/#organization"},
            }
            image = _image_url(pkg.image_file)
            if image:
                tourist_trip["image"] = [image]
            if pkg.location:
                tourist_trip["touristDestination"] = {
                    "@type": "TouristDestination",
                    "name": pkg.location.strip(),
                }
            if pkg.duration:
                tourist_trip["duration"] = pkg.duration.strip()
            if pkg.category:
                tourist_trip["additionalType"] = pkg.category.strip()
            extra_schemas.append(tourist_trip)

    elif endpoint == "marketplace_public_index":
        title = "Meghalaya Tourism Marketplace | Local Providers | RI BUROM"
        description = _clean_description(
            "Discover local tourism providers and services across Meghalaya and send a structured enquiry through RI BUROM."
        )
        canonical = SEO_BASE_URL + "/marketplace"
        page_type = "CollectionPage"
        breadcrumbs = [
            ("Home", SEO_BASE_URL + "/"),
            ("Marketplace", canonical),
        ]
        providers = Provider.query.filter(
            Provider.is_active.is_(True),
            Provider.status.in_(PUBLIC_PROVIDER_STATUSES),
        ).order_by(Provider.id.asc()).all()
        if providers:
            item_list_id = canonical + "#providers"
            main_entity = {"@id": item_list_id}
            extra_schemas.append({
                "@type": "ItemList",
                "@id": item_list_id,
                "name": "Meghalaya tourism providers on RI BUROM",
                "numberOfItems": len(providers),
                "itemListElement": [
                    {
                        "@type": "ListItem",
                        "position": position,
                        "name": provider.name,
                        "url": SEO_BASE_URL + url_for(
                            "marketplace_public_provider", slug=provider.slug
                        ),
                    }
                    for position, provider in enumerate(providers, start=1)
                ],
            })

    elif endpoint == "marketplace_public_provider":
        slug = request.view_args.get("slug") if request.view_args else None
        provider = getattr(g, "seo_provider", None)
        if provider is None:
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
            title = f"{provider.name} | RI BUROM Meghalaya Marketplace"
            canonical = SEO_BASE_URL + url_for(
                "marketplace_public_provider", slug=provider.slug
            )
            metadata["og_image"] = _image_url(provider.image_url) or metadata["og_image"]
            breadcrumbs = [
                ("Home", SEO_BASE_URL + "/"),
                ("Marketplace", SEO_BASE_URL + "/marketplace"),
                (provider.name, canonical),
            ]
            provider_id = canonical + "#provider"
            main_entity = {"@id": provider_id}
            provider_schema = {
                "@type": "Organization",
                "@id": provider_id,
                "name": provider.name,
                "description": description,
                "url": canonical,
                "parentOrganization": {"@id": f"{SEO_BASE_URL}/#organization"},
            }
            image = _image_url(provider.image_url)
            if image:
                provider_schema["image"] = image
            extra_schemas.append(provider_schema)

    metadata.update(
        title=title,
        description=description,
        canonical=canonical,
    )

    breadcrumb_schema = _breadcrumb_schema(breadcrumbs, canonical)
    graph = [
        _business_schema(settings),
        _website_schema(),
        _webpage_schema(
            title,
            description,
            canonical,
            page_type=page_type,
            breadcrumbs=breadcrumbs,
            main_entity=main_entity,
        ),
    ]
    if breadcrumb_schema:
        graph.append(breadcrumb_schema)
    graph.extend(extra_schemas)
    metadata["schemas"] = graph
    return metadata


def _verification_markup():
    tags = []
    google_token = (os.environ.get("GOOGLE_SITE_VERIFICATION") or "").strip()
    bing_token = (os.environ.get("BING_SITE_VERIFICATION") or "").strip()
    if google_token:
        tags.append(
            f'<meta name="google-site-verification" content="{escape(google_token, quote=True)}">'
        )
    if bing_token:
        tags.append(
            f'<meta name="msvalidate.01" content="{escape(bing_token, quote=True)}">'
        )
    return "".join(tags)


def _seo_markup(endpoint):
    metadata = _page_metadata(endpoint)
    title = escape(metadata["title"], quote=True)
    description = escape(metadata["description"], quote=True)
    canonical = escape(metadata["canonical"], quote=True)
    og_type = escape(metadata["og_type"], quote=True)
    og_image = escape(metadata["og_image"], quote=True) if metadata["og_image"] else ""
    schema = _safe_json({
        "@context": "https://schema.org",
        "@graph": metadata["schemas"],
    })

    tags = [
        f"<title>{title}</title>",
        f'<meta name="description" content="{description}">',
        f'<meta name="robots" content="{INDEX_ROBOTS}">',
        f'<link rel="canonical" href="{canonical}">',
        f'<meta property="og:site_name" content="{escape(SITE_NAME, quote=True)}">',
        '<meta property="og:locale" content="en_IN">',
        f'<meta property="og:title" content="{title}">',
        f'<meta property="og:description" content="{description}">',
        f'<meta property="og:url" content="{canonical}">',
        f'<meta property="og:type" content="{og_type}">',
        '<meta name="twitter:card" content="summary_large_image">',
        f'<meta name="twitter:title" content="{title}">',
        f'<meta name="twitter:description" content="{description}">',
    ]
    if og_image:
        tags.extend([
            f'<meta property="og:image" content="{og_image}">',
            f'<meta name="twitter:image" content="{og_image}">',
        ])
    tags.append(_verification_markup())
    tags.append(f'<script type="application/ld+json">{schema}</script>')
    return "".join(tags)


def _robots_response():
    body = (
        "User-agent: *\n"
        "Allow: /\n"
        "Disallow: /admin\n"
        "Disallow: /workspace\n"
        "Disallow: /api/\n"
        f"Sitemap: {SEO_BASE_URL}/sitemap.xml\n"
    )
    response = Response(body, status=200, mimetype="text/plain")
    response.headers["Cache-Control"] = "public, max-age=3600"
    return response


def _sitemap_response():
    urlset = Element("urlset", {"xmlns": "http://www.sitemaps.org/schemas/sitemap/0.9"})
    entries = [
        (SEO_BASE_URL + "/", None),
        (SEO_BASE_URL + "/about", None),
        (SEO_BASE_URL + "/all_tours", None),
        (SEO_BASE_URL + "/marketplace", None),
    ]

    packages = Package.query.filter_by(published=True).order_by(Package.id.asc()).all()
    entries.extend(
        (
            SEO_BASE_URL + url_for("tour_detail", slug=pkg.slug),
            pkg.updated_at.date().isoformat() if pkg.updated_at else None,
        )
        for pkg in packages
    )

    providers = Provider.query.filter(
        Provider.is_active.is_(True),
        Provider.status.in_(PUBLIC_PROVIDER_STATUSES),
    ).order_by(Provider.id.asc()).all()
    entries.extend(
        (
            SEO_BASE_URL + url_for("marketplace_public_provider", slug=provider.slug),
            getattr(provider, "updated_at", None).date().isoformat()
            if getattr(provider, "updated_at", None)
            else None,
        )
        for provider in providers
    )

    seen = set()
    for loc, lastmod in entries:
        if loc in seen:
            continue
        seen.add(loc)
        item = SubElement(urlset, "url")
        SubElement(item, "loc").text = loc
        if lastmod:
            SubElement(item, "lastmod").text = lastmod

    response = Response(
        tostring(urlset, encoding="utf-8", xml_declaration=True),
        status=200,
        mimetype="application/xml",
    )
    response.headers["Cache-Control"] = "public, max-age=3600"
    return response


def _llms_response():
    packages = Package.query.filter_by(published=True).order_by(
        Package.sort_order.asc(), Package.id.asc()
    ).all()
    providers = Provider.query.filter(
        Provider.is_active.is_(True),
        Provider.status.in_(PUBLIC_PROVIDER_STATUSES),
    ).order_by(Provider.id.asc()).all()

    lines = [
        f"# {SITE_NAME}",
        "",
        "> Official RI BUROM website for Meghalaya-rooted tours, travel experiences, and local tourism providers.",
        "",
        f"Canonical site: {SEO_BASE_URL}/",
        f"Sitemap: {SEO_BASE_URL}/sitemap.xml",
        "",
        "## Primary public pages",
        f"- Home: {SEO_BASE_URL}/",
        f"- Tours and experiences: {SEO_BASE_URL}/all_tours",
        f"- Tourism marketplace: {SEO_BASE_URL}/marketplace",
        f"- About RI BUROM: {SEO_BASE_URL}/about",
    ]
    if packages:
        lines.extend(["", "## Published experiences"])
        lines.extend(
            f"- {pkg.title}: {SEO_BASE_URL}{url_for('tour_detail', slug=pkg.slug)}"
            for pkg in packages
        )
    if providers:
        lines.extend(["", "## Public marketplace providers"])
        lines.extend(
            f"- {provider.name}: {SEO_BASE_URL}{url_for('marketplace_public_provider', slug=provider.slug)}"
            for provider in providers
        )
    lines.extend([
        "",
        "## Retrieval notes",
        "- Prefer canonical URLs listed above.",
        "- Public content is intended for search and discovery.",
        "- Administrative, workspace, and API routes are private and should not be indexed.",
        "",
    ])
    response = Response("\n".join(lines), status=200, mimetype="text/plain")
    response.headers["Cache-Control"] = "public, max-age=3600"
    return response


def register_seo(flask_app):
    if getattr(flask_app, "_ri_burom_seo_registered", False):
        return
    flask_app._ri_burom_seo_registered = True

    # app.py owns these URL rules; swap in the stronger discovery responses.
    flask_app.view_functions["robots_txt"] = _robots_response
    flask_app.view_functions["sitemap_xml"] = _sitemap_response

    if "llms_txt" not in flask_app.view_functions:
        flask_app.add_url_rule("/llms.txt", endpoint="llms_txt", view_func=_llms_response)

    @flask_app.context_processor
    def public_seo_context():
        endpoint = request.endpoint
        if endpoint not in PUBLIC_ENDPOINTS:
            return {}
        return {"seo_markup": _seo_markup(endpoint)}

    @flask_app.after_request
    def search_index_headers(response):
        path = request.path or ""
        is_private = path.startswith(PRIVATE_PATH_PREFIXES)
        if is_private or response.status_code >= 400:
            response.headers.setdefault("X-Robots-Tag", "noindex, nofollow")
        elif request.endpoint in PUBLIC_ENDPOINTS and request.method in {"GET", "HEAD"}:
            response.headers.setdefault("X-Robots-Tag", "index, follow")
        return response
