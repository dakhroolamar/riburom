"""IndexNow verification and URL submission helpers for RI BUROM.

IndexNow is opt-in. Set INDEXNOW_KEY in the deployment environment to enable
key-file verification and submissions. The key file is exposed at the site root
as required by the IndexNow protocol.
"""

import json
import os
import re
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from flask import Response


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
