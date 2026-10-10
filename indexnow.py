"""IndexNow verification and URL submission helpers for RI BUROM.

IndexNow is opt-in. Set INDEXNOW_KEY in the deployment environment to enable
key-file verification and submissions. The key file is exposed at the site root
as required by the IndexNow protocol.
"""

import json
import logging
import os
import re
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from flask import Response, has_request_context, has_app_context, current_app
from sqlalchemy import event
from sqlalchemy.orm import Session


logger = logging.getLogger(__name__)


@event.listens_for(Session, 'after_commit')
def _wake_committed_indexing(session):
    if session.info.pop('indexnow_staged', False) and has_app_context():
        wakeup = getattr(current_app, '_outbox_wakeup', None)
        if wakeup:
            wakeup.set()


@event.listens_for(Session, 'after_rollback')
def _clear_rolled_back_indexing(session):
    session.info.pop('indexnow_staged', None)


INDEXNOW_ENDPOINT = "https://api.indexnow.org/indexnow"
PUBLIC_BASE_URL = (
    os.environ.get("PUBLIC_BASE_URL")
    or "https://riburomtours.com"
).strip().rstrip("/")
_INDEXNOW_KEY_RE = re.compile(r"^[A-Za-z0-9-]{8,128}$")
_MAX_URLS_PER_REQUEST = 10_000


def get_indexnow_key():
    """Return the configured IndexNow key, or None when disabled.

    IndexNow allows 8-128 characters using letters, digits, and dashes.
    Invalid configuration is rejected rather than serving a malformed key file.
    """
    key = (os.environ.get("INDEXNOW_KEY") or "").strip()
    if not key:
        return None
    if not _INDEXNOW_KEY_RE.fullmatch(key):
        raise ValueError(
            "INDEXNOW_KEY must be 8-128 characters containing only letters, digits, or dashes."
        )
    return key


def indexnow_key_url():
    key = get_indexnow_key()
    if not key:
        return None
    return f"{PUBLIC_BASE_URL}/{key}.txt"


def _canonicalize_urls(urls):
    expected = urlparse(PUBLIC_BASE_URL)
    accepted = []
    seen = set()

    for value in urls or []:
        url = str(value or "").strip()
        if not url or url in seen:
            continue

        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"}:
            raise ValueError(f"IndexNow URL must be absolute http/https: {url}")
        if parsed.netloc.lower() != expected.netloc.lower():
            raise ValueError(
                f"IndexNow URL host must match {expected.netloc}: {url}"
            )

        seen.add(url)
        accepted.append(url)

    if not accepted:
        raise ValueError("At least one URL is required for IndexNow submission.")
    if len(accepted) > _MAX_URLS_PER_REQUEST:
        raise ValueError(
            f"IndexNow accepts at most {_MAX_URLS_PER_REQUEST} URLs per request."
        )
    return accepted


def build_indexnow_payload(urls):
    """Build the protocol payload without performing network I/O."""
    key = get_indexnow_key()
    if not key:
        raise RuntimeError("INDEXNOW_KEY is not configured.")

    canonical_urls = _canonicalize_urls(urls)
    return {
        "host": urlparse(PUBLIC_BASE_URL).netloc,
        "key": key,
        "keyLocation": indexnow_key_url(),
        "urlList": canonical_urls,
    }


def submit_indexnow_urls(urls, timeout=8):
    """Submit one or more changed canonical URLs to IndexNow.

    Returns a small result dictionary. HTTP 200 means accepted; HTTP 202 means
    received while key validation is pending. Transport/protocol failures are
    returned to the caller so publishing flows can log them without failing.
    """
    payload = build_indexnow_payload(urls)
    data = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    request = Request(
        INDEXNOW_ENDPOINT,
        data=data,
        method="POST",
        headers={
            "Content-Type": "application/json; charset=utf-8",
            "User-Agent": "RI-BUROM-IndexNow/1.0",
        },
    )

    try:
        with urlopen(request, timeout=timeout) as response:
            status = response.getcode()
            body = response.read().decode("utf-8", errors="replace")
            return {
                "ok": status in {200, 202},
                "status": status,
                "body": body,
                "submitted": len(payload["urlList"]),
            }
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        return {
            "ok": False,
            "status": exc.code,
            "body": body,
            "submitted": len(payload["urlList"]),
        }
    except URLError as exc:
        return {
            "ok": False,
            "status": None,
            "body": str(exc.reason),
            "submitted": len(payload["urlList"]),
        }


def submit_indexnow_url(url, timeout=8):
    return submit_indexnow_urls([url], timeout=timeout)


PUBLIC_PROVIDER_STATUSES = {"APPROVED", "PUBLISHED", "ACTIVE"}

_HOME_CMS_KEYS = {
    "home", "hero", "home_gallery", "home_about", "home_about_gallery",
    "home_tours", "home_why", "home_blog", "home_contact", "contact",
}
_ABOUT_CMS_KEYS = {
    "about", "about_header", "about_belief", "about_pillars",
    "about_extra1", "about_extra2", "about_team", "about_logo", "about_blog",
}
_GLOBAL_CMS_KEYS = {"global", "site", "footer", "footer_partners", "branding"}


def current_public_paths():
    """Return all canonical public RI BUROM paths currently eligible for indexing."""
    from marketplace_models import Provider
    from models import Package

    paths = ["/", "/about", "/all_tours", "/marketplace"]

    packages = Package.query.filter_by(published=True).order_by(Package.id.asc()).all()
    paths.extend(f"/tours/{pkg.slug}" for pkg in packages if pkg.slug)

    providers = Provider.query.filter(
        Provider.is_active.is_(True),
        Provider.status.in_(PUBLIC_PROVIDER_STATUSES),
    ).order_by(Provider.id.asc()).all()
    paths.extend(
        f"/marketplace/providers/{provider.slug}"
        for provider in providers
        if provider.slug
    )
    return list(dict.fromkeys(paths))


def public_paths_for_cms_change(key):
    """Map a CMS/public-content change to the canonical pages it affects."""
    from models import Package
    from marketplace_models import Provider

    value = str(key or "").strip()
    if not value:
        return []

    if value in _GLOBAL_CMS_KEYS:
        return current_public_paths()
    if value in _HOME_CMS_KEYS:
        return ["/"]
    if value in _ABOUT_CMS_KEYS:
        return ["/about"]
    if value == "tours":
        return ["/all_tours"]
    if value == "tour-detail":
        packages = Package.query.filter_by(published=True).order_by(Package.id.asc()).all()
        return ["/all_tours"] + [f"/tours/{pkg.slug}" for pkg in packages if pkg.slug]
    if value == "marketplace":
        return ["/marketplace"]
    if value == "provider":
        providers = Provider.query.filter(
            Provider.is_active.is_(True),
            Provider.status.in_(PUBLIC_PROVIDER_STATUSES),
        ).order_by(Provider.id.asc()).all()
        return ["/marketplace"] + [
            f"/marketplace/providers/{provider.slug}"
            for provider in providers
            if provider.slug
        ]
    if value.startswith("tour-") and value[5:].isdigit():
        pkg = Package.query.get(int(value[5:]))
        if pkg and pkg.published and pkg.slug:
            return ["/all_tours", f"/tours/{pkg.slug}"]
        return ["/all_tours"]
    return []


def notify_indexnow_cms_change(key, timeout=3, *, stage_only=False):
    """Best-effort notification for one public CMS change."""
    if not get_indexnow_key():
        return {"ok": False, "skipped": True, "reason": "INDEXNOW_KEY not configured"}
    paths = public_paths_for_cms_change(key)
    if not paths:
        return {"ok": False, "skipped": True, "reason": "no public URLs"}
    return notify_indexnow_paths(paths, timeout=timeout, stage_only=stage_only)


def notify_indexnow_public_site(timeout=8, *, stage_only=False):
    """Submit every currently indexable canonical RI BUROM URL in one batch."""
    if not get_indexnow_key():
        return {"ok": False, "skipped": True, "reason": "INDEXNOW_KEY not configured"}
    return notify_indexnow_paths(current_public_paths(), timeout=timeout, stage_only=stage_only)


def notify_indexnow_paths(paths, timeout=3, *, stage_only=False):
    """Stage a durable CMS intent, or send an independent best-effort notice.

    With stage_only=True, database failures propagate and the caller commits
    the intent with its content. Network delivery remains outside that save.
    Independent notifications retain the legacy best-effort behavior.
    """
    if not get_indexnow_key():
        return {"ok": False, "skipped": True, "reason": "INDEXNOW_KEY not configured"}

    urls = []
    for path in paths or []:
        value = str(path or "").strip()
        if not value:
            continue
        if value.startswith(("http://", "https://")):
            urls.append(value)
        else:
            urls.append(PUBLIC_BASE_URL + (value if value.startswith("/") else "/" + value))

    if not urls:
        return {"ok": False, "skipped": True, "reason": "no URLs"}

    if stage_only:
        # Stage the durable intent in the caller's content transaction. Failures
        # must propagate so a save cannot acknowledge content without its intent.
        from models import db, NotificationOutbox
        from uuid import uuid4
        canonical = _canonicalize_urls(urls)
        body = json.dumps(canonical, separators=(',', ':'))
        with db.session.no_autoflush:
            pending = NotificationOutbox.query.filter_by(channel='indexnow', status='PENDING', body=body).first()
        staged = any(isinstance(row, NotificationOutbox) and row.channel == 'indexnow' and
                     row.status == 'PENDING' and row.body == body for row in db.session.new)
        if pending is None and not staged:
            db.session.add(NotificationOutbox(source_type='indexnow', source_id=uuid4().hex,
                event_type='public_update', channel='indexnow', recipient=INDEXNOW_ENDPOINT,
                body=body, status='PENDING'))
        db.session.info['indexnow_staged'] = True
        return {'ok': True, 'queued': True, 'submitted': len(canonical)}

    # HTTP saves acknowledge their commit without waiting for search engines.
    # The shared durable worker also retries indexing after a restart/outage.
    if has_request_context():
        try:
            from models import db, NotificationOutbox
            from uuid import uuid4
            canonical = _canonicalize_urls(urls)
            body = json.dumps(canonical, separators=(',', ':'))
            pending = NotificationOutbox.query.filter_by(channel='indexnow', status='PENDING', body=body).first()
            if pending is None:
                db.session.add(NotificationOutbox(source_type='indexnow', source_id=uuid4().hex,
                    event_type='public_update', channel='indexnow', recipient=INDEXNOW_ENDPOINT, body=body))
                db.session.commit()
            wakeup = getattr(current_app, '_outbox_wakeup', None)
            if wakeup:
                wakeup.set()
            return {'ok': True, 'queued': True, 'submitted': len(canonical)}
        except Exception:
            db.session.rollback()
            logger.exception('Could not queue IndexNow update')
            return {'ok': False, 'queued': False, 'status': None, 'submitted': 0}

    try:
        result = submit_indexnow_urls(urls, timeout=timeout)
        if not result.get("ok"):
            logger.warning(
                "IndexNow submission failed status=%s body=%s",
                result.get("status"),
                result.get("body"),
            )
        return result
    except Exception:
        logger.exception("IndexNow submission failed unexpectedly")
        return {"ok": False, "status": None, "submitted": 0}


def register_indexnow(flask_app):
    """Register the root IndexNow verification file when a key is configured."""
    if getattr(flask_app, "_ri_burom_indexnow_registered", False):
        return
    flask_app._ri_burom_indexnow_registered = True

    key = get_indexnow_key()
    if not key:
        return

    path = f"/{key}.txt"

    def indexnow_key_file():
        response = Response(
            key + "\n",
            status=200,
            content_type="text/plain; charset=utf-8",
        )
        response.headers["Cache-Control"] = "public, max-age=3600"
        response.headers["X-Robots-Tag"] = "noindex, nofollow"
        return response

    flask_app.add_url_rule(
        path,
        endpoint="indexnow_key_file",
        view_func=indexnow_key_file,
        methods=["GET", "HEAD"],
    )
