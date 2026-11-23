"""Initialize the existing Flask application inside the Python Durable Object."""

import hashlib
import os

# Register the storage scheme before Flask-Limiter initializes.
import durable_rate_limits  # noqa: F401


_application = None
PROVIDER_SETTINGS = (
    "SECRET_KEY", "ADMIN_PASSWORD_HASH", "PUBLIC_BASE_URL",
    "CLOUDINARY_URL", "CLOUDINARY_CLOUD_NAME", "CLOUDINARY_API_KEY", "CLOUDINARY_API_SECRET",
    "CLOUDINARY_STAGING_FOLDER",
    "BREVO_API_KEY", "BREVO_SENDER_EMAIL", "BREVO_SENDER_NAME", "NOTIFICATION_EMAIL",
    "BREVO_CLIENT_ID", "BREVO_CLIENT_SECRET",
    "INITIAL_OWNER_EMAIL", "INDEXNOW_KEY", "GOOGLE_SITE_VERIFICATION", "BING_SITE_VERIFICATION",
    "TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN", "TWILIO_WHATSAPP_FROM", "TWILIO_FROM_NUMBER",
    "NOTIFICATION_PHONE", "WHATSAPP_PHONE",
)


def worker_scrypt(password, *, salt, n, r, p, maxmem=0, dklen=64):
    from Crypto.Protocol.KDF import scrypt

    if 128 * n * r > (maxmem or 32 * 1024 * 1024):
        raise ValueError("scrypt memory limit exceeded")
    return scrypt(password, salt, dklen, n, r, p)


def hyperdrive_url(connection):
    from sqlalchemy import URL

    return URL.create(
        "postgresql+pg8000", username=connection.user, password=connection.password,
        host=connection.host, port=int(connection.port), database=connection.database,
    )


def configure_application(env):
    database = hyperdrive_url(env.HYPERDRIVE)
    os.environ.update({
        key: value for key in PROVIDER_SETTINGS
        if (value := getattr(env, key, None)) is not None
    })
    os.environ.update(
        APP_ENV="production", DATABASE_URL=database.render_as_string(hide_password=False),
        RIBUROM_HYPERDRIVE="1",
        RIBUROM_READ_ONLY=getattr(env, "RIBUROM_READ_ONLY", "false"),
    )


def worker_brevo_http(request, *, read_body=False):
    from js import AbortSignal, Object, fetch
    from pyodide.ffi import run_sync, to_js

    options = to_js({
        "method": request.get_method(),
        "headers": dict(request.header_items()),
        "body": request.data.decode("utf-8"),
        "redirect": "manual",
        "signal": AbortSignal.timeout(10_000),
    }, dict_converter=Object.fromEntries)
    response = run_sync(fetch(request.full_url, options))
    body = run_sync(response.text()) if read_body and response.status == 200 else None
    return response.status, body



def install_staging_timing(app):
    """Numeric timings only, for the protected comparison hostname."""
    from time import perf_counter
    from flask import g, has_request_context, request
    from sqlalchemy import event
    from sqlalchemy.engine import Engine

    def profiled():
        return (
            has_request_context()
            and request.host == "riburom-application-staging.dakhroo.workers.dev"
        )

    @app.before_request
    def _start_staging_profile():
        if profiled():
            g._ri_started = perf_counter()
            g._ri_sql_ms = 0.0
            g._ri_sql_count = 0

    @event.listens_for(Engine, "before_cursor_execute")
    def _before_sql(conn, cursor, statement, parameters, context, executemany):
        if profiled() and hasattr(g, "_ri_started"):
            context._ri_started_sql = perf_counter()

    @event.listens_for(Engine, "after_cursor_execute")
    def _after_sql(conn, cursor, statement, parameters, context, executemany):
        started = getattr(context, "_ri_started_sql", None)
        if started is not None and profiled() and hasattr(g, "_ri_started"):
            g._ri_sql_count += 1
            g._ri_sql_ms += (perf_counter() - started) * 1000.0

    @app.after_request
    def _send_staging_profile(response):
        if profiled() and hasattr(g, "_ri_started"):
            elapsed_ms = (perf_counter() - g._ri_started) * 1000.0
            response.headers["Server-Timing"] = (
                f"flask;dur={elapsed_ms:.1f}, "
                f"sql;dur={g._ri_sql_ms:.1f}"
            )
            response.headers["X-Riburom-Staging-SQL-Count"] = str(g._ri_sql_count)
        return response


def get_application(env):
    global _application
    if _application is not None:
        return _application

    os.environ.update(
        PYTHON_DOTENV_DISABLED="1", OUTBOX_WORKER_ENABLED="false",
        RATELIMIT_STORAGE_URI="durable-sqlite://",
    )
    if env.RIBUROM_MODE == "fixture":
        os.environ.update(APP_ENV="testing", TESTING="1", DATABASE_URL="sqlite://",
                          SECRET_KEY="synthetic-worker-preview")
    elif env.RIBUROM_MODE == "application":
        configure_application(env)
    else:
        raise RuntimeError("Unknown RI BUROM Worker mode")

    if not hasattr(hashlib, "scrypt"):
        hashlib.scrypt = worker_scrypt

    from wsgi import app

    if env.RIBUROM_MODE == "application":
        app.config["BREVO_HTTP_TRANSPORT"] = worker_brevo_http
        install_staging_timing(app)

    flask_wsgi = app.wsgi_app

    def cloudflare_wsgi(environ, start_response):
        # Cloudflare supplies the visitor address on requests to the public entrypoint.
        environ["REMOTE_ADDR"] = environ.get("HTTP_CF_CONNECTING_IP") or "unknown"
        return flask_wsgi(environ, start_response)

    app.wsgi_app = cloudflare_wsgi
    if env.RIBUROM_MODE == "fixture":
        from worker_fixture import setup_fixture
        setup_fixture(app)
    _application = app
    return app
