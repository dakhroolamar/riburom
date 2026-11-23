from base64 import b64encode
from hmac import compare_digest
from urllib.parse import urlsplit

from workers import DurableObject, Response, WorkerEntrypoint, wsgi


APP_INSTANCE = "web"
PUBLIC_COMPARISON_PATHS = {
    "/", "/all_tours", "/about", "/marketplace", "/stories",
    "/healthz", "/readyz", "/favicon.ico", "/robots.txt", "/__comparison/readiness",
}


def is_comparison_path(path):
    return (
        path in PUBLIC_COMPARISON_PATHS
        or path.startswith(("/tours/", "/marketplace/providers/", "/reviews/media/", "/static/"))
    )




def flask_stub(env):
    """Stably route Flask to its Durable Object, optionally hinting first placement.

    Location hints affect *only a newly created object*. Keeping the same name
    on later deployments preserves the rate-limit state and its placement.
    """
    name = getattr(env, "RIBUROM_DO_NAME", None) or APP_INSTANCE
    hint = getattr(env, "RIBUROM_DO_LOCATION", None)
    if not hint:
        return env.FLASK_APP.getByName(name)
    if hint not in ("apac", "apac-se"):
        raise RuntimeError("Unsupported Durable Object location hint")
    from js import Object
    from pyodide.ffi import to_js

    options = to_js({"locationHint": hint}, dict_converter=Object.fromEntries)
    return env.FLASK_APP.getByName(name, options)
async def cache_public_or_forward(env, request, path):
    """Cache only invariant, anonymous HTML; fail open to Flask on cache errors.

    Cache lookup happens *after* Basic auth and only without visitor cookies.
    Never cache the homepage (CSRF form), account pages, responses with
    Set-Cookie, or anything other than exact public GET paths.
    """
    if not (
        getattr(env, "RIBUROM_PUBLIC_CACHE", None) == "true"
        and request.method == "GET"
        and path in ("/all_tours", "/about", "/stories", "/marketplace")
        and not urlsplit(request.url).query
        and not request.headers.get("Cookie")
        and not request.headers.get("Range")
    ):
        return await flask_stub(env).fetch(request)

    from js import Request as JSRequest, Response as JSResponse, caches
    cache = caches.default
    key = JSRequest.new(request.url)
    try:
        hit = await cache.match(key)
        if hit is not None:
            return hit
    except Exception:
        pass

    response = await flask_stub(env).fetch(request)
    if response.status != 200:
        return response
    raw = getattr(response, "js_object", None)
    if raw is None or raw.headers.get("set-cookie") or raw.headers.get("vary"):
        return response
    if raw.headers.get("cache-control") and (
        "private" in raw.headers.get("cache-control").lower()
        or "no-store" in raw.headers.get("cache-control").lower()
    ):
        return response
    try:
        copy = raw.clone()
        cached = JSResponse.new(copy.body, copy)
        cached.headers.set("Cache-Control", "public, max-age=30")
        cached.headers.set("X-Riburom-Cache", "HIT")
        await cache.put(key, cached)
    except Exception:
        # A cache failure must never prevent delivery of fresh content.
        pass
    return response


FIXTURE_ROUTES = {"/", "/healthz", "/readyz", "/favicon.ico", "/__staging/outbox"}


class Default(WorkerEntrypoint):
    async def fetch(self, request):
        path = urlsplit(request.url).path
        mode = self.env.RIBUROM_MODE
        if mode == "fixture":
            if request.method != "GET" or path not in FIXTURE_ROUTES:
                return Response("Preview route unavailable", status=404)
        elif mode != "application" or urlsplit(request.url).hostname != self.env.RIBUROM_HOST:
            return Response("Unknown site", status=404)
        if getattr(self.env, "RIBUROM_READ_ONLY", None) == "true":
            # The parallel site may point at live Neon, so reject *all*
            # writes before Flask and hide private or administrative routes.
            if request.method not in ("GET", "HEAD") or not is_comparison_path(path):
                return Response("Read-only public comparison", status=404, headers={
                    "Cache-Control": "no-store", "X-Robots-Tag": "noindex, nofollow"
                })
            if path == "/robots.txt":
                return Response("User-agent: *\\nDisallow: /\\n", headers={
                    "Content-Type": "text/plain", "X-Robots-Tag": "noindex, nofollow"
                })
        if getattr(self.env, "RIBUROM_STAGING_ACCESS_REQUIRED", None) == "true":
            secret = getattr(self.env, "RIBUROM_STAGING_ACCESS_TOKEN", None)
            if not secret:
                return Response("Staging access unavailable", status=404)
            encoded = b64encode(f"rehearsal:{secret}".encode("utf-8"))
            authorization = (request.headers.get("Authorization") or "").encode("utf-8")
            if not compare_digest(authorization, b"Basic " + encoded):
                return Response("Authentication required", status=401, headers={
                    "WWW-Authenticate": 'Basic realm="RI BUROM staging", charset="UTF-8"',
                    "Cache-Control": "no-store",
                    "X-Robots-Tag": "noindex, nofollow",
                })
        if mode == "application" and path.startswith("/static/"):
            # This runs only after staging HTTP Basic was validated, and also
            # serves assets on any future public Worker without invoking Flask.
            return await self.env.ASSETS.fetch(request.js_object)
        if mode == "application" and path == "/__staging/bootstrap":
            if request.method != "POST":
                return Response("Method not allowed", status=405)
            return await flask_stub(self.env).fetch(request)
        return await cache_public_or_forward(self.env, request, path)

    async def scheduled(self, controller, env, ctx):
        if self.env.OUTBOX_SCHEDULED == "true":
            await flask_stub(self.env).run_outbox()


class FlaskApplication(DurableObject):
    def __init__(self, ctx, env):
        super().__init__(ctx, env)
        self.ctx.storage.sql.exec(
            "CREATE TABLE IF NOT EXISTS rate_limits "
            "(key TEXT PRIMARY KEY, hits INTEGER NOT NULL, expires INTEGER NOT NULL)"
        )
        self.ctx.storage.sql.exec("CREATE INDEX IF NOT EXISTS rate_limits_expiry ON rate_limits (expires)")

    async def fetch(self, request):
        from worker_runtime import get_application
        from durable_rate_limits import request_sql

        app = get_application(self.env)
        token = request_sql.set(self.ctx.storage.sql)
        try:
            if self.env.RIBUROM_MODE == "fixture" and urlsplit(request.url).path == "/__staging/outbox":
                from worker_fixture import fixture_status
                return Response.json(fixture_status(self.ctx.storage.sql), headers={"X-Robots-Tag": "noindex"})
            if (
                self.env.RIBUROM_MODE == "application"
                and getattr(self.env, "RIBUROM_READ_ONLY", None) == "true"
                and urlsplit(request.url).path == "/__comparison/readiness"
            ):
                # This read-only probe fails closed unless the Hyperdrive
                # database role lacks write grants on live business tables.
                from sqlalchemy import text
                from models import db

                with app.app_context():
                    writable = db.session.execute(text(
                        "SELECT bool_or(has_table_privilege(current_user, "
                        "t.table_name, 'INSERT,UPDATE,DELETE')) "
                        "FROM (VALUES ('public.users'), ('public.messages'), "
                        "('public.packages'), ('public.notification_outbox'), "
                        "('public.marketplace_inquiries')) AS t(table_name)"
                    )).scalar()
                    db.session.remove()
                return Response.json(
                    {"read_only_role": writable is False},
                    status=200 if writable is False else 503,
                    headers={"Cache-Control": "no-store", "X-Robots-Tag": "noindex"},
                )
            if self.env.RIBUROM_MODE == "application" and urlsplit(request.url).path == "/__staging/bootstrap":
                if not (
                    request.method == "POST"
                    and self.env.RIBUROM_HOST == "riburom-application-staging.dakhroo.workers.dev"
                    and self.env.RIBUROM_STAGING_ACCESS_REQUIRED == "true"
                ):
                    return Response("Unavailable", status=404)
                try:
                    from staging_setup import initialize_staging
                    payload, status = initialize_staging(
                        app, self.env.RIBUROM_STAGING_ACCESS_TOKEN
                    )
                    return Response.json(payload, status=status)
                except Exception as exc:
                    return Response.json(
                        {"status": "bootstrap_failed", "exception": type(exc).__name__},
                        status=503,
                    )
            return await wsgi.fetch(app, request, self.env)
        finally:
            request_sql.reset(token)

    async def run_outbox(self):
        from worker_runtime import get_application

        sql = self.ctx.storage.sql
        sql.exec("DELETE FROM rate_limits WHERE expires <= unixepoch()")
        app = get_application(self.env)
        with app.app_context():
            if self.env.RIBUROM_MODE == "fixture":
                from worker_fixture import check_fixture_database, process_fixture_outbox
                result = process_fixture_outbox(sql)
                if connection := getattr(self.env, "HYPERDRIVE", None):
                    check_fixture_database(sql, connection)
            else:
                from notifications import process_pending_notifications
                result = process_pending_notifications(limit=2)
        print(f"Outbox processed: sent={result['sent']} failed={result['failed']} skipped={result['skipped']}")
