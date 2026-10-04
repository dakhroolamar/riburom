# CMS foundation and media collections

Base: origin/main `4299cf1`. Feature branch: `feat/cms-page-editor`.

## Editing

Open `/workspace/pages` for the page list, section text, galleries and Hero logo preview. Home sections follow the configured public order. `/workspace/library` provides reusable images, metadata, search, usage filtering and removal of unused library entries. Existing CMS screens remain available for controls not yet moved into the page editor.

Gallery editing supports sequential multiple uploads, upload progress, library selection, replacement, drag sorting and keyboard ordering. First image is the default / tour cover. Metadata is shared by all uses of an asset; focal points and partner details belong to collection items. Save gallery applies the selection. Logo placement has desktop, tablet and mobile settings with bounded percentage sliders and reset.

Uploads are limited to 12 MB per file, 40 megapixels and 10 files / 120 MB per client batch. Each file is a separate request within the existing 16 MB request ceiling. The backend checks file bytes and format before storage. Cloudinary failures leave existing selections untouched. `CMS_COLLECTION_LIMIT` configures the collection size (default 10).

## Architecture and compatibility

- `MediaAsset` owns the reusable storage reference and common metadata.
- `MediaCollection` owns the ordered list and an optimistic-concurrency version.
- `MediaCollectionItem` holds image membership, focus and partner presentation.
- `PageSection` holds responsive logo settings with its own concurrency version.
- Existing SiteSettings content and appearance remain authoritative; section text updates retain the existing public-configuration concurrency token.

Migration `e6f7a8b9c012` adds four tables and registers existing image references without copying or downloading images. Existing image dimensions, bytes and historical upload dates cannot be recovered from legacy fields: imported records have unknown dimensions/bytes and a registration timestamp. New uploads record their original dimensions and bytes.

Public galleries use new records when present, otherwise keep legacy CMS media and built-in fallbacks. Empty collections revert to the legacy fallback. Hidden partner entries stay hidden. Legacy media deletion now protects references registered in the library. Removing an unused library record retains the underlying file conservatively; this release does not purge Cloudinary blobs.

The migration downgrade drops the new records but retains legacy content and media files. New collection edits should be exported before a database downgrade. For an application rollback, keep the additive tables and deploy the previous application commit instead.

## Public behavior

Hero photographs support manual navigation, touch/trackpad scrolling and controlled autoplay. Autoplay pauses for hover, focus, user interaction, hidden tabs, offscreen galleries, reduced motion and data saving. Tour pages have progressive-loading galleries; selected tour covers also appear in existing cards. The river gallery and About flip interaction are reused with editable metadata and focal points. Footer partner logos render only when configured.

Cloudinary images use automatic format/quality and bounded delivery width. Subsequent Hero/tour images acquire their source as they approach the gallery viewport. The existing river and About layout, opening film and protected parchment styling remain in place.

## Validation

- Full Python suite: 159 tests, 9 skipped (includes opt-in database tests).
- Separate SQLite and PostgreSQL 18 migration upgrade/downgrade tests: 2 passed.
- JavaScript syntax checks and `git diff --check`: passed.
- Disposable local browser: gallery reorder/save, two-file upload/save, responsive logo save, desktop homepage and exact 390 CSS-pixel homepage/CMS review.
- Browser QA generates screenshots from local synthetic media, not production content. CI retains them as workflow artifacts rather than committing them to the repository.

## Subsequent phases

The full controlled appearance editor, global design-token consolidation, full-page draft preview, revision history/rollback, and the Signature Experiences autoplay setting remain subsequent phases. Saves in this release still apply immediately. The existing marketplace and provider editing workflows remain linked from the page navigation.
