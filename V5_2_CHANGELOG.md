# RI BUROM v5.2 — About Structure & Brand Header

## What changed

### About Us page structure (Owner only)
- Added `AboutSection` CMS records with independent `enabled` and `sort_order` values.
- Owner can reorder About Us sections with drag-and-drop or Up / Down controls.
- Owner can show/hide sections without deleting their content.
- Default section order:
  1. What We Believe
  2. Nature | Culture | Community
  3. Additional Section 1
  4. Additional Section 2
  5. Our People
  6. The Meaning Behind Our Logo
  7. Stories from the Journey

### People/profile management
- Added structured profile role types: Founder, Co-Founder, Designer, Team Member, Custom.
- Added profile `sort_order`.
- Existing profiles are migrated to the intended default order: Founder → Co-Founder → Designer → Team Members.
- Owner can independently reorder profiles with drag-and-drop or Up / Down controls.
- Content Managers can still add/edit/delete profiles but cannot change the overall ordering.

### Header branding
- Removed the visible hardcoded `RI BUROM` text fallback from the top-left header.
- The header now uses the uploaded wordmark image as the text/brand name representation.
- The uploaded logo mark remains a separate image beside the wordmark.
- If neither image is uploaded, the header is intentionally blank rather than inserting a generic text logo.

### Local vs Cloudinary storage
- Local development now uses `static/uploads/` automatically.
- Cloudinary is used when valid production credentials are present.
- Development only uses Cloudinary when `USE_CLOUDINARY=true` is explicitly set.
- Placeholder Cloudinary values in `.env.example` no longer trigger Cloudinary uploads.
- This fixes local PDF/image uploads when Cloudinary is not configured.

### Migration / compatibility
- Existing SQLite databases receive the new team columns automatically.
- New `about_sections` records are seeded automatically.
- PostgreSQL migration now carries the new team ordering/role fields and About section records when present.

## Validation performed in this environment
- Python source compilation: passed for `app.py`, `models.py`, `storage.py`, `migrate_to_postgres.py`, and `generate_password_hash.py`.
- Jinja parsing: passed for `_nav.html`, `about.html`, `admin.html`, and `edit_team_member.html`.
- Full Flask runtime was not executed here because the environment does not have the Flask dependencies installed. Run the included requirements on your Windows machine before runtime testing.
