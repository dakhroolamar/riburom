from base64 import b64encode
from hmac import compare_digest
from urllib.parse import urlsplit

from workers import DurableObject, Request, Response, WorkerEntrypoint, wsgi


APP_INSTANCE = "web"
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
            if path.startswith("/static/"):
                return await self.env.ASSETS.fetch(Request.new(f"https://assets.local{path}"))
        if mode == "application" and path == "/__staging/bootstrap":
            if request.method != "POST":
                return Response("Method not allowed", status=405)
            return await self.env.FLASK_APP.getByName(APP_INSTANCE).fetch(request)
        return await self.env.FLASK_APP.getByName(APP_INSTANCE).fetch(request)

    async def scheduled(self, controller, env, ctx):
        if self.env.OUTBOX_SCHEDULED == "true":
            await self.env.FLASK_APP.getByName(APP_INSTANCE).run_outbox()


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
