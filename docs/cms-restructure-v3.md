# CMS restructure v3 — review notes

Branch: `feat/cms-restructure-v3`, based on production commit `a938b60c096241e0b2ebdba9bbca60a36d223b42`.
This branch is for review; it does not merge or deploy production.

## What changed

- Shared Jinja shell for Pages and Library with Site, Media, Business, Design and Settings navigation. Mobile uses a collapsible workspace menu.
- Compact page sections and Content / Media / Design panels replace the numbered workflow and repeated links to advanced screens.
- Gallery media uses one large preview, a thumbnail strip, accessible reorder buttons, a library picker and a selected-image inspector. Alt text, caption, credit, focal points, replacement, uploads and partner fields remain supported.
- Unsaved edits are tracked; section changes ask before discarding them. Save/upload operations lock the editing surface. Late section requests cannot overwrite the currently selected section or panel.
- Inline section colors reuse existing theme fields. Gallery Design adds autoplay, 5/6/7-second timing and desktop proportions. Settings use existing site configuration storage, permission checks, CSRF and concurrency tokens. No migration or dependency was added.
- Business and advanced workflows retain their existing routes. Global typography, navigation labels and backgrounds are discoverable in the sidebar; legacy CMS remains available under Settings.

## Production gallery root cause

Production displayed the dynamically hydrated `home_gallery` river gallery. The old autoplay controller only scanned server-rendered `[data-cms-gallery]` elements; the optional Hero gallery was absent on production. The river instead used manual rail controls. Previous browser QA seeded the optional Hero gallery, masking the production failure.

`cms-public-media.js` now exposes one idempotent controller. The river initializes it after creating slides, and server-rendered Hero/tour galleries use the same controller. The obsolete river rail binding and exit-zoom listener were removed; experience rails and the About flip retain their own distinct interactions.

The controller uses measured slide offsets, a single timer and a visibility threshold. Hover does not pause it. Navigation, horizontal wheel and pointer interaction pause it for 12 seconds; it then resumes. Explicit pause remains paused until resumed. Offscreen/hidden documents, reduced motion and data saving prevent automatic movement. Lazy server images load on entry and before navigation.

The river is centered at a maximum 1000px, with one complete image per slide, default 16:9 desktop / 4:3 mobile, crop focus, understated controls and a position indicator. The transition into About has less empty space. Existing paper, river animation, opening film, permanent logo, About flip, experience rail and torn-paper sections remain.

Changed static URLs and the service-worker cache version prevent old gallery/editor scripts from being served with the new markup.

## Changed files

- Backend: `cms_pages.py`.
- Editor templates: `templates/_cms_shell.html`, `templates/cms_pages.html`, `templates/cms_library.html`, `templates/_cms_media_editor.html`, `templates/cms.html`.
- Public templates: `templates/_cms_gallery.html`, `templates/_public_theme.html`, `templates/index.html`, `templates/tour_detail.html`.
- Styles: `static/css/cms-pages.css`, `static/css/cms-public-media.css`, `static/css/ri-burom-home-fixes.css`.
- Scripts/cache: `static/js/cms-pages.js`, `static/js/cms-public-media.js`, `static/js/ri-burom-home-fixes.js`, `static/sw.js`.
- Tests/CI: `tests/cms_browser_qa.cjs`, `tests/cms_preview.py`, `tests/test_cms_pages.py`, `tests/test_paper_ui.py`, `.github/workflows/cms-workspace-validation.yml`.
- Review notes: this file.

## Verification

- Full Python suite: **162 tests, OK; 9 PostgreSQL cases skipped** in the default run.
- Separate CMS/marketplace/package migration suite on disposable **PostgreSQL 18.6**: **10 tests passed**, including those 9 PostgreSQL cases plus the CMS SQLite migration case.
- Final focused CMS/template checks: **19 passed** after the last layout/formatting edits.
- Python compilation and Node syntax checks passed for changed Python and JavaScript files. `git diff --check` passed.
- `tests/cms_browser_qa.cjs`: passed at **1440×1000** and **390×844**, with no console/page errors. Covers editor rendering, ordering and metadata persistence, picker, section design, gallery settings, library, image loading, page overflow, gallery proportions, actual slide movement, hover, previous/next, manual pause/resume, explicit pause/resume, offscreen pause, reduced motion, keyboard and horizontal scrolling at mobile width.
- The fixture deliberately has **no optional Hero gallery** and uses visibly different numbered/color images. Before/after screenshots demonstrate visible movement rather than merely asserting a timer exists.
- Additional visual pass used the four existing production photo URLs in an isolated local in-memory fixture. No production content was edited. Both desktop and 390px screenshots were inspected; no page errors occurred.
- Browser/IAB was used first for production diagnosis and manual preview inspection. Installed Playwright ran the requested repeatable regression suite and exact-size screenshots; the IAB viewport override did not consistently produce the requested dimensions in background tabs.

## Design comparison

Two Image Gen concepts guided the work: `exec-397c712f-0907-41bb-a238-ffca39cca2f3.png` (CMS) and `exec-a28cc28f-ca46-4c27-8532-6e0386c5d22f.png` (public gallery). Both concepts and final rendered captures were opened with `view_image`.

| Comparison | Final implementation / intentional difference |
| --- | --- |
| Hierarchy | Grouped left navigation, horizontal sections and local editing tabs match the concept. Redundant step headings and explanatory cards were removed. |
| Layout | Large preview on the left and one inspector on the right; stacked on mobile. Preview was tightened to the public 16:9 crop. |
| Palette | Warm neutral canvas, white editor, forest-green controls, sage selection and amber save action. |
| Typography | One native system sans family for editor chrome. Existing public typography stays intact rather than adopting the generated concept's replacement brand typography. |
| Image treatment | Real existing photography, focal crop, thumbnail selection and restrained rounded corners. Generated concept photos are not shipped. |
| Spacing | Reduced editor heading space and shortened the gallery-to-About transition after screenshot review. Save controls remain visible near the viewport bottom. |
| Copy | Retained established page names and business routes. Gallery is shortened from “Hero / River Gallery.” Generated decorative tagline/icons were omitted; form guidance describes real behavior. No public marketing copy was changed. |
| Responsive | Collapsed navigation, horizontally scrollable section selector, single-column inspector, 4:3 gallery and no horizontal page overflow at 390px. |

The final UI was visually verified against these concepts with the intentional compatibility differences above. The generated concepts serve as direction; the existing brand assets, content and working backend remain authoritative.

## Evidence and reproduction

Run `python -m tests.cms_preview`, then `node tests/cms_browser_qa.cjs` with Playwright installed. The fixture binds only localhost and uses an isolated database. `CMS_QA_OUTPUT` overrides the screenshot directory; CI defaults to `/tmp/riburom-cms-qa` and uploads the results as an artifact. The workflow now runs on this feature branch.

Screenshots include CMS main/section/design/library/picker, 390px CMS, desktop/mobile public gallery, and before/after autoplay. The local final-photo evidence uses the `final-*.png` filenames in the delivered `cms-v3` screenshot folder. The deterministic regression fixtures remain self-contained and do not depend on production images.

## Remaining review

Review the feature branch and screenshots before merging to `main`. Production behavior after deployment and physical iOS/Safari touch behavior have not been verified on this undeployed branch. Gallery metadata still uses the existing shared-asset API: edits affect all uses, and gallery ordering plus metadata are saved as separate requests. A failed metadata request leaves the remaining edits available to retry.
