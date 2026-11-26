from base64 import b64encode
from hmac import compare_digest
from urllib.parse import urlsplit

from workers import DurableObject, Response, WorkerEntrypoint, wsgi
from outbox_handoff import PRODUCTION_CANDIDATE_HOST
from production_brevo_probe import PRODUCTION_BREVO_PATH, probe_denial


APP_INSTANCE = "web"
PUBLIC_COMPARISON_PATHS = {
    "/", "/all_tours", "/about", "/marketplace", "/stories",
    "/healthz", "/readyz", "/favicon.ico", "/robots.txt", "/sitemap.xml",
    "/api/public-section-backgrounds", "/stories/featured", "/__comparison/readiness",
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
        and (not request.headers.get("Authorization")
             or getattr(env, "RIBUROM_STAGING_ACCESS_REQUIRED", None) == "true")
    ):
        return await flask_stub(env).fetch(request)

    from js import Request as JSRequest, Response as JSResponse, caches
    cache = caches.default
    key = JSRequest.new(request.url)
    try:
        hit = await cache.match(key)
        if hit is not None:
            # Cache-Control public is for the Worker's private cache entry.
            # Downstream clients must re-enter the auth and cookie guards.
            outgoing = JSResponse.new(hit.body, hit)
            outgoing.headers.set("Cache-Control", "private, no-store")
            outgoing.headers.delete("X-Riburom-Staging-First-Request")
            outgoing.headers.delete("Server-Timing")
            outgoing.headers.delete("X-Riburom-Staging-SQL-Count")
            return outgoing
    except Exception:
        pass

    response = await flask_stub(env).fetch(request)
    if response.status != 200:
        return response
    raw = getattr(response, "js_object", None)
    if (raw is None or raw.headers.get("set-cookie")
            or not (raw.headers.get("content-type") or "").lower().startswith("text/html")):
        return response
    # Flask reads the session for navigation and emits "Vary: Cookie".
    # We cache *only requests without a Cookie* and bypass all cookie-bearing
    # requests, so that particular Vary is safe; reject every other Vary.
    vary = (raw.headers.get("vary") or "").lower()
    if any(value.strip() != "cookie" for value in vary.split(",") if value.strip()):
        return response
    if raw.headers.get("cache-control") and (
        "private" in raw.headers.get("cache-control").lower()
        or "no-cache" in raw.headers.get("cache-control").lower()
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
        if mode == "application" and self.env.RIBUROM_HOST == PRODUCTION_CANDIDATE_HOST:
            if (getattr(self.env, "RIBUROM_STAGING_ACCESS_REQUIRED", None) != "true"
                    or path.startswith(("/__staging/", "/__comparison/"))):
                return Response("Unavailable", status=404, headers={"Cache-Control": "no-store"})
            # Render is the only host accepting business submissions during rehearsal.
            if request.method not in ("GET", "HEAD") and not (
                request.method == "POST" and path in ("/admin/login", "/admin/logout", PRODUCTION_BREVO_PATH)
            ):
                return Response("Production candidate is in preview", status=405,
                                headers={"Allow": "GET, HEAD", "Cache-Control": "no-store"})
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
        if path == PRODUCTION_BREVO_PATH:
            if reason := probe_denial(self.env, request):
                if self.env.RIBUROM_HOST == PRODUCTION_CANDIDATE_HOST:
                    return Response.json({"status": reason}, status=404, headers={"Cache-Control": "no-store"})
                return Response("Unavailable", status=404, headers={"Cache-Control": "no-store"})
            return await flask_stub(self.env).fetch(request)
        if mode == "application" and path.startswith("/static/"):
            # This runs only after staging HTTP Basic was validated, and also
            # serves assets on any future public Worker without invoking Flask.
            return await self.env.ASSETS.fetch(request.js_object)
        if mode == "application" and path in (
            "/__staging/bootstrap", "/__staging/brevo-check", "/__staging/brevo-send"
        ):
            if request.method != "POST":
                return Response("Method not allowed", status=405)
            return await flask_stub(self.env).fetch(request)
        return await cache_public_or_forward(self.env, request, path)

    async def scheduled(self, controller, env, ctx):
        # Fail closed: only synthetic probe mail tests, or an explicitly
        # approved *production* handoff, may drain notifications.
        from outbox_handoff import scheduled_outbox_allowed
        if scheduled_outbox_allowed(self.env):
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
        from worker_runtime import ProductionMediaBindingMissing, get_application
        from durable_rate_limits import request_sql

        # Candidate-only sanitized startup diagnostics. The Worker is protected
        # by HTTP Basic and never shares exception messages, SQL or credentials.
        try:
            app = get_application(self.env)
        except Exception as exc:
            if getattr(self.env, "RIBUROM_HOST", None) == PRODUCTION_CANDIDATE_HOST:
                # Report only predefined check *names*, never SQL, role names,
                # connection strings, exception messages or secret values.
                payload = {"status": "candidate_startup_failed", "exception": type(exc).__name__}
                if type(exc).__name__ == "ProductionGuardMismatch":
                    payload["failed_checks"] = list(exc.failed_checks)
                elif isinstance(exc, ProductionMediaBindingMissing):
                    payload["reason"] = "cloudinary_binding_missing"
                elif type(exc).__name__ == "RuntimeError":
                    message = str(exc)
                    if message.startswith("SECRET_KEY must be configured"):
                        payload["reason"] = "session_secret_missing"
                    elif message.startswith("ADMIN_PASSWORD_HASH must be configured"):
                        payload["reason"] = "admin_hash_missing"
                    elif message.startswith("Cloudinary must be configured in production"):
                        payload["reason"] = "cloudinary_config_missing"
                # Only static source basenames and line numbers; no exception
                # messages, trace locals, file paths, SQL, or provider errors.
                source_names = {"worker.py", "worker_runtime.py", "app.py",
                                "wsgi.py", "application_modules.py",
                                "models.py", "notifications.py", "control_room.py", "storage.py"}
                trace = []
                frame = exc.__traceback__
                while frame:
                    path = frame.tb_frame.f_code.co_filename
                    name = path.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
                    if name in source_names:
                        trace.append(f"{name}:{frame.tb_lineno}")
                    frame = frame.tb_next
                payload["source_trace"] = trace[-8:]
                return Response.json(
                    payload,
                    status=503,
                    headers={"Cache-Control": "no-store", "X-Robots-Tag": "noindex, nofollow"},
                )
            raise
        token = request_sql.set(self.ctx.storage.sql)
        try:
            if urlsplit(request.url).path == PRODUCTION_BREVO_PATH:
                if reason := probe_denial(self.env, request):
                    return Response.json({"status": reason, "stage": "durable_object"}, status=404,
                                         headers={"Cache-Control": "no-store"})
                from production_brevo_probe import run_probe

                payload, status = run_probe(app, self.ctx.storage.sql)
                return Response.json(payload, status=status,
                                     headers={"Cache-Control": "no-store", "X-Robots-Tag": "noindex"})
            if self.env.RIBUROM_MODE == "fixture" and urlsplit(request.url).path == "/__staging/outbox":
                from worker_fixture import fixture_status
                return Response.json(fixture_status(self.ctx.storage.sql), headers={"X-Robots-Tag": "noindex"})
            if (
                self.env.RIBUROM_MODE == "application"
                and getattr(self.env, "RIBUROM_READ_ONLY", None) == "true"
                and urlsplit(request.url).path == "/__comparison/readiness"
            ):
                # Every new comparison connection passes the policy in worker_runtime.
                from sqlalchemy import text
                from models import db

                with app.app_context():
                    db.session.execute(text("SELECT 1"))
                return Response.json(
                    {"read_only_role": True},
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
            if (
                self.env.RIBUROM_MODE == "application"
                and urlsplit(request.url).path in ("/__staging/brevo-check", "/__staging/brevo-send")
            ):
                from staging_brevo_test import run_staging_brevo_test

                deliver = urlsplit(request.url).path == "/__staging/brevo-send"
                payload, status = run_staging_brevo_test(app, self.env, deliver=deliver)
                return Response.json(
                    payload, status=status,
                    headers={"Cache-Control": "no-store", "X-Robots-Tag": "noindex, nofollow"},
                )
            try:
                return await wsgi.fetch(app, request, self.env)
            except Exception as exc:
                if getattr(self.env, "RIBUROM_HOST", None) == PRODUCTION_CANDIDATE_HOST:
                    return Response.json(
                        {"status": "candidate_wsgi_failed", "exception": type(exc).__name__},
                        status=503,
                        headers={"Cache-Control": "no-store", "X-Robots-Tag": "noindex, nofollow"},
                    )
                raise
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
