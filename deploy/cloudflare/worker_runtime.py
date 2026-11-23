"""Initialize the existing Flask application inside the Python Durable Object."""

import hashlib
import os

# Register the storage scheme before Flask-Limiter initializes.
import durable_rate_limits  # noqa: F401


_application = None
PROVIDER_SETTINGS = (
    "SECRET_KEY", "ADMIN_PASSWORD_HASH", "PUBLIC_BASE_URL",
    "CLOUDINARY_URL", "CLOUDINARY_CLOUD_NAME", "CLOUDINARY_API_KEY", "CLOUDINARY_API_SECRET",
    "BREVO_API_KEY", "BREVO_SENDER_EMAIL", "BREVO_SENDER_NAME", "NOTIFICATION_EMAIL",
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
    )


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
