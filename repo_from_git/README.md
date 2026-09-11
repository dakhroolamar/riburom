# RI BUROM Tours & Travels

This build adds the multi-user Control Room and the security/CMS improvements discussed during the code review.

## Access model

RI BUROM now supports individual user accounts with three roles:

- **Owner** — full access, including user management, security-sensitive actions, content and enquiries.
- **Content Manager** — tours, media, About Us and team management; no user administration or enquiry deletion.
- **Enquiries / Booking** — view and manage customer enquiries; no website-content management.

Only Owners can create, deactivate, edit roles, or reset passwords for other accounts.

Every user can change their own password from **My Account**. Passwords are stored only as secure hashes. The system prevents the last active Owner from being removed or demoted.

## Security

- CSRF protection on all POST forms.
- Login and public contact rate limiting using Flask-Limiter.
- Production fails closed unless `SECRET_KEY` and `ADMIN_PASSWORD_HASH` are configured.
- Production is the default. Set `APP_ENV=development` explicitly for local development.
- Individual username/password authentication with role-based authorization.
- Password changes and owner password resets use Werkzeug password hashes.
- Safe validation of the login `next` redirect.
- Secure/HttpOnly/SameSite session-cookie settings.
- Basic security response headers.
- Admin logout is a CSRF-protected POST.
- Audit log records logins, logouts, password changes/resets, user changes, and major CMS actions.
- At least one active Owner is always required.

## CMS improvements

- Tour slugs, so public pages use `/tours/<slug>`.
- Tour detail pages with location, duration, price, category, season, difficulty, itinerary, included/excluded fields and a booking CTA.
- `published`, `featured`, and `sort_order` controls from the admin panel.
- Team members can be edited as well as added/deleted.
- Media can be replaced or removed from package/team/hero records.
- Old media is cleaned up when replaced or deleted. Local uploads are kept under `static/uploads/`, separate from system assets.
- Uploaded image validation opens/verifies the file, applies EXIF orientation, resizes and compresses it.
- PDF uploads are checked for the `%PDF-` file signature.

## Contact / leads

- Contact form captures phone, travel dates, traveller count and tour interest.
- Server-side validation and field-length limits.
- Leads appear in the Enquiries / Booking inbox.

## PWA / caching

- Service worker does not cache `/admin` or authenticated pages.
- Cache version is bumped so old unsafe cache entries are cleared.

## Database / deployment

- Flask-Migrate is included for future schema migrations.
- A boot-time bridge migrates the existing SQLite/Postgres schema and creates the new user/audit tables.
- If the database has no users, the first Owner is created from `ADMIN_PASSWORD_HASH` and the `INITIAL_OWNER_*` values.
- `migrate_to_postgres.py` reads legacy SQLite databases directly and maps old rows into the expanded schema.

## Local setup

```bash
python -m venv venv
# Windows
venv\\Scripts\\activate
# macOS/Linux
source venv/bin/activate

pip install -r requirements.txt
```

Create a `.env` from `.env.example` and set:

```text
APP_ENV=development
SECRET_KEY=your-local-secret
ADMIN_PASSWORD_HASH=your-generated-password-hash
INITIAL_OWNER_USERNAME=owner
INITIAL_OWNER_NAME=RI BUROM Owner
```

Generate a hash:

```bash
python generate_password_hash.py
```

Then run:

```bash
python app.py
```

Open `http://127.0.0.1:5000/admin/login`.

The initial Owner account will be created automatically if the database has no users.

## Production

Before deployment, set:

```text
APP_ENV=production
SECRET_KEY=...
ADMIN_PASSWORD_HASH=...
INITIAL_OWNER_USERNAME=...
INITIAL_OWNER_NAME=...
DATABASE_URL=postgresql://...
CLOUDINARY_CLOUD_NAME=...
CLOUDINARY_API_KEY=...
CLOUDINARY_API_SECRET=...
```

Do not use the development fallback `ADMIN_PASSWORD` in production.

For more than one Gunicorn worker/instance, use Redis (or another shared backend) for `RATELIMIT_STORAGE_URI`; `memory://` is per-process. The `redis` Python package is included in `requirements.txt`.

## Database migration

For a one-time data copy from the included SQLite database to PostgreSQL:

```bash
DATABASE_URL="postgresql://..." python migrate_to_postgres.py
```

For future schema changes, use Flask-Migrate/Alembic:

```bash
flask db init        # once, if migrations/ does not exist
flask db migrate -m "describe the schema change"
flask db upgrade
```

## Important deployment note

The ZIP intentionally does not contain the real logo/photos referenced by the sample database. Restore those assets into the project or upload them through the admin control room after configuring persistent storage.

The public site still uses the Tailwind CDN for the existing visual layer. Moving to a compiled local stylesheet is a separate frontend build step.

## Branding / About / Blog / Instagram CMS

The Control Room now provides a dedicated content-management area for the public-facing brand:

- **Header branding:** upload two separate images: a left-side RI BUROM wordmark and a separate logo mark.
- **Hero logo:** upload a separate image for the homepage hero.
- **Logo resizing:** change the display width of the wordmark, logo mark, header gap, and hero logo using admin sliders. This changes display size without altering the original uploaded image.
- **About pillars:** fully edit the Nature, Culture and Community headings/text.
- **Two additional About sections:** create/edit two extra heading + body sections and choose whether each is shown publicly.
- **Logo meaning section:** edit the public explanation, upload the complete logo concept PDF, add the designer/creator name and credit, and choose whether the section is visible.
- **External blog:** paste a blog URL, title, excerpt, button label and optional image. The featured story can be enabled and optionally displayed on the homepage. The link opens the external blog in a new tab.
- **Footer:** edit business name, tagline, phone, email, address and copyright line.
- **Instagram:** paste the Instagram URL. The site provides a direct clickable Instagram button and can automatically generate/display a QR code in the footer.

All of these controls are available to users with the existing `manage_about`/`manage_media` permissions, which means Owner and Content Manager can manage the public website without giving them user-administration privileges.

## v5.2 additions
This build adds Owner-controlled About Us section ordering/visibility, structured profile roles and ordering, removes the hardcoded header wordmark fallback, and makes local storage the default during development while allowing Cloudinary in production.

### Local media behavior
Set `APP_ENV=development` and leave `USE_CLOUDINARY=false` (or unset). Uploaded images/PDFs are saved under `static/uploads/`. Configure valid Cloudinary credentials for production deployment.
