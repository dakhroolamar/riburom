# RI BUROM v5 — Branding & Content Control Upgrade

This build extends the v4 multi-user Control Room without changing the existing three-role access model.

## New public-facing controls

### Header and hero logos
- Header now supports two separate uploaded images:
  1. RI BUROM wordmark/text on the far left.
  2. Separate logo mark immediately after it.
- Homepage hero uses a separately uploaded hero logo.
- If a dedicated hero logo is not uploaded, the header mark/wordmark can act as fallback.
- Admin sliders control wordmark width, mark width, gap and hero-logo width.
- Display resizing is CSS-based; the uploaded originals are not overwritten.

### About Us
- Nature / Culture / Community headings and text are fully editable.
- Two additional custom sections are available, each with:
  - heading
  - body text
  - show/hide toggle
- Logo meaning section supports:
  - custom heading
  - custom explanatory text
  - complete PDF upload
  - designer/creator name
  - designer credit/role
  - public show/hide toggle

### External blog
- Paste an external blog URL.
- Configure featured story title, excerpt, button text and optional image.
- Enable/disable the blog feature.
- Independently choose whether the selected story appears on the homepage.
- External story opens in a new tab.

### Footer and Instagram
- Footer business name, tagline, phone, email, address and copyright line are editable.
- Instagram URL is configurable from the Control Room.
- Site shows a direct clickable Instagram button.
- A QR code is automatically generated from the supplied Instagram URL.
- QR display can be enabled/disabled independently.

## Migration / compatibility
- New `site_settings` singleton table is created automatically on startup.
- Existing v4 SQLite data remains intact.
- PostgreSQL migration script now also copies the `site_settings` record when present.
- Existing user roles and permissions remain unchanged.

## Testing
See `MULTI_USER_TESTING.md` for the new branding, About, blog and Instagram tests.

## v5.1 hotfix — startup audit context

- Fixed initial Owner creation crashing during application startup because audit logging attempted to access Flask's request/session context before any HTTP request existed.
- `add_audit()` now safely records startup/system events without a request context, while continuing to record the authenticated user and IP address for normal HTTP actions.
- Initial Owner creation remains idempotent and does not require a logged-in user.
