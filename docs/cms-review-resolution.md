# Resolution of the seven website review findings

All seven findings from the independent review were repaired in the local working tree. These changes have not been deployed.

| Finding | Resolution | Verification |
| --- | --- | --- |
| Q1: shared image metadata overwritten | MediaAsset now has an optimistic version. Central metadata writes, standalone image writes and gallery metadata batches require the version returned by their reads. Location, category and tags participate in the same asset version. Stale writes return 409. | Independent overlapping ORM sessions, stale writes across three endpoints, and a successful versioned gallery batch. |
| Q2: legacy images reappear after clearing | An existing collection remains authoritative when empty. Legacy fallback applies only to absent collections. Empty tour galleries also omit the legacy cover from public cards. | Filled-to-empty gallery with populated legacy settings; empty tour cover checks on home and all tours. |
| Q3: Appearance permission mismatch | Section design visibility and loading use the media permission, matching the API. Content-only accounts retain their content controls. | Delegated permission tests and actual media/content account browser checks. |
| Q4: detail preview opens home | Tour and provider previews require a published record selection and render the corresponding public view with the saved draft. Invalid targets return 404; preview responses remain private/no-store. | Target selection, selected tour/provider output, draft text and invalid-record checks. |
| Q5: input disappears during saving | Metadata inputs and actions lock during the pending request; media selection stays on the saved image. Controls restore on completion or failure. Subsequent edits retain the dirty state. | Delayed network response exercised at desktop and mobile widths. |
| Q6: opening film marked unused | Video responses include live opening-film usage. Server filters and client loading include videos in the Used view. | Used/Unused API checks and rendered Used filter at desktop and mobile widths. |
| Q7: indexing intent lost between commits | CMS saves stage IndexNow records in the content transaction. This includes page content, appearance, galleries, publication and older website/marketplace editors. Network delivery happens in the worker; successful commits wake it. Rollback clears the wake flag. | A content save uses one commit and creates a pending intent without network calls. Injected commit failure rolls back both content and intent. |

Regression checks are in `tests/test_cms_pages.py`, `tests/test_control_room.py`, `tests/test_cms_reliability.py` and `tests/test_control_room_migration.py`. Browser checks are reproducible with `python -m tests.cms_review_preview` and `tests/cms_review_browser_qa.cjs`; the preview uses synthetic in-memory data and binds only to localhost.

The full Python suite completed successfully, with 227 tests and 9 optional checks skipped. Six browser checks passed at widths 1440 and 390, with no JavaScript runtime errors. JavaScript syntax checks and `git diff --check` passed. Local evidence is under `.test-artifacts/seven-fixes/` (ignored by Git).

## Deployment requirement

Upgrade the database through `b7d2e9a4c610` before starting the new application. This migration follows `f9c4d8e1a235` and adds the image version column while preserving existing image metadata. Its upgrade and downgrade were tested on isolated SQLite. The existing deployment migration gate upgrades to the current head.

Existing custom clients of the image metadata API must send the version returned by the relevant image or collection read. The built-in CMS clients have been updated, and their script cache versions were bumped.

Production deployment and production PostgreSQL validation were not performed. IndexNow delivery remains conditional on a configured key and the background worker running; external services were not contacted during validation.
