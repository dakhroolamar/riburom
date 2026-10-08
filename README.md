# RI BUROM Tours & Travels

RI BUROM is a Flask application for the public tourism website, staff CMS/workspace,
tour/experience management, provider/service marketplace discovery, and structured
traveller enquiries.

The marketplace is currently **staff-assisted and enquiry-based**. It is not yet a
transactional booking platform: there is no inventory reservation, payment,
commission, cancellation/refund, traveller account, or provider self-service flow.

## Production architecture

| Layer | Production service |
| --- | --- |
| Source / deployment branch | GitHub `main` |
| Application hosting | Render, Gunicorn → `wsgi:app` |
| Database | Neon PostgreSQL via `DATABASE_URL` |
| Media | Cloudinary |
| Email notifications | Brevo HTTPS API |
| Optional messaging | Twilio integration when configured |
| Schema migrations | Flask-Migrate / Alembic |

Python is pinned to **3.14.3** in `.python-version`, and CI uses the same version.

## Main application areas

### Featured blog / story

In the Control Room, open **Website Manager → Blog / Stories**. Upload a PNG,
JPG or WebP (up to 12 MB), add a title and accessible story text, and select
**Publish story**. With no external link, readers open `/stories/featured`, where
the artwork is displayed in full. Select **Feature on homepage** and keep the
homepage Blog section visible to show its card. This editor manages one featured
story; saving replaces the previous feature. Clearing Publish story hides the
public story page. Existing external blog links remain supported.

- Public homepage, About page, experiences, tour details, and marketplace.
- Staff Operations workspace for tours, website enquiries, and team profiles.
- CMS for public copy, styling, media, backgrounds, typography, and structure.
- Marketplace administration for provider types, providers, service categories,
  services, galleries, publication state, and marketplace enquiries.
- Owner-only user/permission administration and audit history.
- Developer/System workspace for a read-only operational snapshot.

Public marketplace enquiries support one or multiple services and are stored separately
from the legacy website contact form.

## Security and reliability

The application currently includes:

- global CSRF protection for form submissions;
- secure/HttpOnly/SameSite session cookies in production;
- password hashing and Owner-only user administration;
- session-version revocation after password resets and security-sensitive user changes;
- fail-closed production configuration for `SECRET_KEY`, `DATABASE_URL`, and Cloudinary;
- per-user permission overrides;
- separate permissions for marketplace catalogue management and traveller enquiry PII;
- request IDs and baseline security response headers;
- rate limiting for login/public enquiry routes;
- upload validation, image re-encoding, generated filenames, and safe local-path handling;
- durable notification outbox rows with bounded retry attempts;
- CSV formula-injection neutralization;
- a database-independent 500 response.

The current Render service runs one instance / one Gunicorn worker, so the configured
`memory://` rate-limit store is sufficient for the present deployment. Configure a
shared Redis/Valkey `RATELIMIT_STORAGE_URI` before increasing worker or instance count.

## Health endpoints

- `GET /healthz` — process-level liveness; does not depend on PostgreSQL.
- `GET /readyz` — readiness check that verifies a database connection.

These endpoints expose only a small status response and no credentials or schema data.

## Deployment flow

Render auto-deploys the `main` branch.

Current build command:

```bash
pip install -r requirements.txt && python scripts/debug_migration.py
```

Current start command:

```bash
gunicorn wsgi:app
```

`app.py` imports are intentionally side-effect free. During deployment:

1. the migration gate verifies the PostgreSQL connection;
2. if `alembic_version` exists, legacy `db.create_all()`/schema repair is skipped;
3. Alembic upgrades to the repository migration head;
4. bounded application defaults/bootstrap data are checked after migration;
5. Gunicorn starts only after the build succeeds.

The first Owner is created only when the user table is empty. Normal deploys do not
re-create, reactivate, rename, or re-promote an existing account.

## Notification delivery

General contact and marketplace enquiries create `NotificationOutbox` rows in the same
database transaction as the enquiry.

Production notification recipients come from operational environment configuration,
not editable public footer fields:

- `NOTIFICATION_EMAIL`, falling back to `INITIAL_OWNER_EMAIL`;
- `NOTIFICATION_PHONE`, falling back to `WHATSAPP_PHONE`.

Email delivery uses Brevo when `BREVO_API_KEY` and `BREVO_SENDER_EMAIL` are
configured. Optional SMS/WhatsApp delivery uses Twilio configuration.

The request starts an asynchronous attempt for the exact committed outbox rows.
Failed rows remain durable and can be retried by later enquiry traffic or with:

```bash
python scripts/process_notification_outbox.py
```

## Production environment

Use Render environment variables. Never commit real secret values.

Required production configuration includes:

```text
APP_ENV=production
SECRET_KEY=...
ADMIN_PASSWORD_HASH=...
DATABASE_URL=postgresql://...
CLOUDINARY_CLOUD_NAME=...
CLOUDINARY_API_KEY=...
CLOUDINARY_API_SECRET=...
PUBLIC_BASE_URL=https://riburomtours.com
```

Operational notification configuration:

```text
INITIAL_OWNER_EMAIL=...
NOTIFICATION_EMAIL=...
BREVO_API_KEY=...
BREVO_SENDER_EMAIL=...
BREVO_SENDER_NAME=RI BUROM
```

Optional messaging configuration is documented in `.env.example`.

## Local development

Create a virtual environment using Python 3.14.3:

```bash
python -m venv .venv
```

Activate it and install dependencies:

```bash
# Windows PowerShell
.\.venv\Scripts\Activate.ps1

# macOS/Linux
source .venv/bin/activate

pip install -r requirements.txt
```

Copy `.env.example` to `.env` and use development settings. Local development may
use SQLite and local files under `static/uploads/`.

Generate a Werkzeug password hash with:

```bash
python generate_password_hash.py
```

Run locally:

```bash
python app.py
```

Then open `http://127.0.0.1:5000/admin/login`.

## Tests

The GitHub Actions workflow runs the complete Python test suite plus PostgreSQL 18
migration/reconciliation coverage.

Locally:

```bash
python -m unittest discover -s tests -p "test_*.py" -v
```

Tests are deliberately prevented from using PostgreSQL through the normal application
`DATABASE_URL`. PostgreSQL-specific tests use a separate disposable
`MARKETPLACE_TEST_DATABASE_URL`.

**Never point test configuration at the production Neon database.**

## Database maintenance safety

Normal schema changes belong in Alembic migrations. Do not use `db.create_all()` as a
production migration mechanism.

Two legacy maintenance utilities remain for exceptional recovery/migration work:

- `scripts/prepare_production_migrations.py`
- `migrate_to_postgres.py`

They now refuse to mutate a database unless explicit acknowledgement variables are
provided. Production use requires an additional acknowledgement that a backup exists.
These scripts are not part of routine deployment.

## Repository layout

```text
app.py                         Core Flask application and legacy/public routes
application_modules.py         Shared composition root for feature registration
wsgi.py                        Production WSGI entrypoint
config_concurrency.py          Optimistic locking for JSON-backed CMS settings
media_lifecycle.py             Reference-safe marketplace media cleanup
models.py                      Core application models
marketplace_models.py          Marketplace domain models
cms_*.py                       Workspace/CMS modules
marketplace_*.py               Marketplace routes and operations
notifications.py               Durable notification outbox/delivery
seo.py                         Canonicals, metadata, robots and sitemap
storage.py                     Cloudinary/local media abstraction
migrations/                    Alembic migration history
scripts/                       Deployment/maintenance workers
templates/                     Jinja templates
static/                        Local CSS/JS/system assets
tests/                         Unit/integration/migration tests
```

The old tracked `repo_from_git/` duplicate tree and temporary squash files were
removed from `main`. The pre-cleanup state is preserved on the GitHub branch
`archive/repo-from-git-before-cleanup`.

## Current product boundary

RI BUROM currently supports discovery and staff-assisted enquiry operations. A future
transactional marketplace would require separate work for availability/inventory,
provider accounts, traveller accounts, quotations/contracts, payment/commission,
cancellations/refunds, and transactional booking records. Those concerns should not be
represented by the current enquiry status field alone.
