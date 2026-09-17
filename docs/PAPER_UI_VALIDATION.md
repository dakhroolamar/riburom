# Meghalaya paper UI

This refresh builds on `ui/visual-refresh` at `17e5382`. No application routes,
models, migrations, authentication, notification delivery or deployment commands
are changed.

## Presentation

- Shared paper surfaces, original SVG landscapes, reserved stream gutter,
  editorial serif headings, and responsive image frames live in the existing UI
  system. No external font provider or security-header exception was added.
- Tour titles and metadata are separate from artwork. `object-fit: contain`
  preserves poster lettering; titles wrap dynamically without manual breaks.
- Existing CMS copy, visibility, order, per-section colors, media and contact
  fields remain bound. New paper colors are defaults only. The optional hero film
  plays in the landscape area while the title and logo stay visible.
- The about section provides the waterfall story; the values section carries
  root-bridge decoration; the optional CMS blog supplies the community story.
  Dedicated Nohkalikai, craft and guide content fields do not exist. No fictional
  production story, artisan, download or migration has been introduced. Existing
  package PDF links remain conditional on actual media.
- GSAP and ScrollTrigger **3.12.5** are vendored under `static/vendor` with upstream
  copyright/license notices and README. They load only on the homepage. There is
  one scrubbed stream timeline and one small roots parallax trigger. ResizeObserver
  refreshes layout measurements; reduced motion renders the full static stream,
  with no path drawing or parallax. Failed JS leaves the full SVG visible.

## Reproduce local browser QA

Run `python -m tests.ui_preview`, then `node tests/ui_browser_qa.cjs` in a second
terminal with Playwright available. The preview disables dotenv, removes service
credentials from its process environment and uses an in-memory SQLite database.
It does not submit messages. Fixture and synthetic-poster routes exist only in
the preview script, never in the deployed application.

Browser QA covers homepage, two tour title lengths, tours listing, marketplace,
provider, About and empty marketplace at 1440×900, 1280×800, 1024×768, 768×1024,
and 390×844. It checks overflow, heading bounds, navigation separation, stream
clearance, menu Escape handling, enquiry selection, CSRF presence, scroll drawing
and changing reduced-motion preference. Screenshots and results are written to
the OS temporary directory `riburom-paper-qa`.

Run `python scripts/check_ui_utility_coverage.py` and
`python -m unittest discover -s tests -p 'test_*.py'` with a sanitized test
environment. PostgreSQL integration cases require a separately provisioned local
disposable test database; they must never use the production Neon URL.

Production media and saved CMS palettes still require human visual review. Browser
fixtures deliberately use local artwork and block external network requests;
they do not verify Cloudinary, Brevo, Neon or Render configuration.
