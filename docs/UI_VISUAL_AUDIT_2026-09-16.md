# RI BUROM UI Visual Audit — 16 September 2026

## Scope

This audit covers the current public homepage, marketplace, provider page, tours/experience pages, and staff workspace. It combines:

- inspection of the live public site at desktop (1440 × 900 CSS px) and mobile (390 × 844 CSS px),
- computed live layout measurements,
- inspection of the Jinja templates and compiled utility stylesheet,
- review of the responsive and interaction patterns already present.

No production UI behavior is changed by this audit.

## Executive diagnosis

The public site has a recognizable visual identity and a usable green/amber foundation, but it currently feels like several individually-built interfaces rather than one product system.

The most important issue is not typography or color. It is **stylesheet drift**: newer marketplace/provider templates use Tailwind-style utility classes that are missing from `static/css/ri-burom-compiled.css`. As a result, a meaningful portion of the intended responsive layout and polish is not actually applied in production.

The second major issue is **shell fragmentation**. Public pages share navigation/footer/theme primitives, but staff interfaces use several different shells and component definitions. Operations, CMS, Marketplace, Marketplace Enquiries and Customer Analytics look like related internal tools rather than one coherent workspace.

The redesign should therefore start with the design system and shared shells before page-level decoration.

---

## 1. Cross-cutting visual infrastructure

### 1.1 Compiled utility CSS is out of sync with templates — highest priority

Approximate utility coverage from the current templates:

| Surface | Missing compiled utilities observed |
|---|---:|
| Homepage | 1 |
| Marketplace | 36 |
| Provider page | 22 |
| Tour detail | 2 |
| Tours listing | 0 |

Examples missing from the marketplace include `grid-cols-2`, `rounded-2xl`, `border-gray-200`, `sm:text-5xl`, `sm:px-6`, `aspect-[16/9]`, `overflow-y-auto`, and several focus utilities.

Examples missing from the provider page include `xl:grid-cols-12`, `xl:col-span-8`, `xl:col-span-4`, `xl:sticky`, `xl:top-28`, `rounded-2xl`, `shadow-xl`, `bg-green-50` and responsive typography/padding classes.

This is already visible in the live marketplace: the intended two-column “Browse by” toggle computes as a **single-column grid** on desktop and mobile.

**Design implication:** do not start a detailed visual redesign on top of the current generated stylesheet. First create a reliable UI build/source-of-truth so every class used by the templates is actually shipped.

### 1.2 Too many independent style definitions

Public theme variables, the compiled utility file, motion CSS embedded in the navigation partial, page-specific inline CSS, and standalone workspace page styles all overlap.

The design refresh should consolidate these into:

1. global tokens,
2. public-site components,
3. workspace components,
4. page-specific styles only when genuinely unique.

### 1.3 Brand palette is recognizable but inconsistently applied

The established green/amber language works for RI BUROM, but current pages also use blue, teal, indigo, purple and red as structural accents. Some are functional status colors; others are decorative leftovers.

The refresh should keep:
- deep forest green as the primary brand anchor,
- warm earth/amber as the secondary accent,
- neutral stone/slate surfaces,
- blue/red/amber/green reserved mainly for functional states in the workspace.

### 1.4 Radius/shadow hierarchy is inconsistent

The site mixes `rounded`, `rounded-xl`, intended-but-uncompiled `rounded-2xl`, several custom 14/20/22 px radii, and multiple shadow systems.

Define a small scale instead of allowing each template to invent its own.

---

## 2. Homepage

### Current strengths

- Clear first-message hierarchy: logo/brand, “Meghalaya, beyond the ordinary.”, supporting line, two primary actions.
- Strong full-width destination imagery and overlay concept.
- The green/amber palette fits the Meghalaya/nature positioning.
- Good content sequence: Hero → About → Experiences → Why RI BUROM → Story/Blog → Contact.
- Public CMS already gives the content enough flexibility for a redesign without changing the data model.
- Motion generally respects reduced-motion preferences.

### Live measurements

Desktop:
- navigation: ~76 px high,
- hero: ~912 px high,
- H1: 60 px,
- total page height: ~3417 px.

Mobile:
- navigation: ~76 px,
- hero: ~952 px high on an 844 px viewport,
- H1: 36 px and approximately 120 px tall,
- total page height: ~5176 px,
- footer alone: ~937 px.

### Problems

**Hero is too dominant on mobile.** The hero is taller than the initial viewport. A traveller must move beyond more than one screen before seeing the next content block.

**The homepage is long when content is sparse.** Production currently has no public tour cards visible. This makes the Experiences area depend heavily on an empty state while the rest of the page remains very long.

**The footer becomes disproportionately large on mobile.** The four-column desktop structure stacks into almost a full viewport of footer content.

**The cards are visually generic.** White card + shadow + colored top border is functional, but does not feel like a high-end travel discovery product.

**CTA hierarchy is crowded.** Hero primary action, secondary action, navigation login, contact form and floating WhatsApp all compete for attention.

### Redesign direction

- Reduce mobile hero to approximately 72–82 svh while retaining cinematic imagery.
- Use stronger editorial spacing rather than repeated generic card blocks.
- Convert experience cards into image-led travel cards with clearer location, duration and starting-price metadata.
- Replace the four “Why” cards with a more distinctive story/value treatment.
- Compress mobile footer and separate business information from secondary links.
- Keep WhatsApp available but visually secondary to the principal discovery/enquiry journey.
- Preserve CMS-controlled copy and ordering.

---

## 3. Public Marketplace

### Current strengths

- Clear concept: search, category filter, then switch between Providers and Services.
- Client-side filtering is immediate.
- Service detail modal supports galleries and has keyboard focus handling.
- Empty-result feedback exists.
- Public marketplace is separate from staff/admin workflows.

### Live state

Production currently exposes no public provider/service records, so the live page is effectively an empty marketplace shell.

Desktop:
- page height: ~1401 px,
- H1 renders at **30 px**, despite the template intending a larger responsive size,
- search field: ~862 × 60 px,
- “Browse by” toggle computes as **one column**, not two.

Mobile:
- page height: ~2135 px,
- H1 remains 30 px,
- search field: ~324 × 60 px,
- footer: ~937 px,
- “Browse by” toggle is also one column.

### Problems

**The marketplace is where stylesheet drift is most visible.** The intended visual design and the shipped design differ.

**The empty marketplace currently shows search/filter controls before there is anything to search.** This makes the product feel unfinished when inventory is empty.

**Provider rows are too text-led.** They lack strong imagery, location/service metadata and visual differentiation.

**Services open in a modal while providers open on a new page.** That behavior is valid, but the two browsing modes do not yet feel like parts of one unified discovery system.

**Filter architecture is too thin for the long-term marketplace model.** Category + free text is adequate now, but the visual system should reserve room for geography, service type and future availability without becoming a filter wall.

### Redesign direction

- Fix utility coverage first.
- Create a marketplace hero/search band that immediately explains what can be discovered.
- Use visually rich provider cards/list tiles with provider type, location/area served, service count and image.
- Use a compact filter bar on desktop and filter drawer/sheet on mobile.
- Treat Providers / Services as a proper segmented control.
- Build a designed empty state that explains how RI BUROM works instead of presenting inactive search infrastructure.
- Keep the current underlying provider/service routing and enquiry architecture.

---

## 4. Provider Page

### Current strengths

This is currently the strongest conceptual public marketplace page.

- Large image-led provider hero.
- Strong provider identity and service-type chips.
- Service list is easy to understand.
- Dedicated marketplace enquiry CTA.
- Multi-service enquiry is correctly represented in the UI.
- Enquiry dialog has focus management and progressive service-family fields.

### Structural visual defect

The template intends:

- 12-column desktop grid,
- 8-column service area,
- 4-column sticky enquiry/contact sidebar.

Those `xl:*` utilities are **not present in the compiled stylesheet**. Therefore the intended desktop split/sticky presentation is not reliably applied. The provider page can remain stacked even on large screens.

### Problems

**Contact information is repeated.** Phone/email can appear in the hero stats and again in the Contact details card.

**The hero is powerful but dense.** Provider types, title, description, service count, phone and email all compete in the first viewport.

**Service rows need more travel-commerce information.** They show category, name, description and image but little decision support.

**The enquiry dialog can become very long.** Dynamic fields help, but a traveller can still face a large form with many possible trip/stay/transport fields.

**The intended sticky conversion panel is currently undermined by missing CSS.**

### Redesign direction

- Restore the intended desktop 8/4 split.
- Keep the hero focused on identity, trust and short description; move detailed contact data to the sidebar.
- Give each service a consistent image, category, concise summary and “Add to enquiry” interaction.
- Make the enquiry panel feel like a request builder rather than a generic form.
- Consider a 2-step enquiry interaction in the UI later: service selection → trip/contact details. Backend can remain unchanged initially.

---

## 5. Tours / Experience Pages

### Tours listing

Current strengths:
- simple 3-column desktop card grid,
- image, category, duration, title, description, location, price and clear view action.

Problems:
- production currently has no published experiences visible,
- empty listing occupies only the viewport and has **no shared footer**,
- card styling uses a blue top border that conflicts with the otherwise green/earth brand language,
- no browsing/filter affordance,
- empty state does not carry enough brand/product explanation.

The missing footer is a direct consistency defect in `templates/tours.html`.

### Tour detail

Current strengths:
- image-led 55vh hero,
- strong title scale,
- overview / itinerary / included / excluded information structure,
- desktop CTA sidebar concept,
- WhatsApp and enquiry actions are prominent.

Visual defects from missing compiled utilities:
- `h-full` is absent, so the hero content container may not fill the hero and the intended bottom alignment is weakened,
- `h-fit` is absent on the desktop sidebar, which can interfere with the intended sticky CTA behavior.

Product/design weaknesses:
- itinerary is plain long-form text rather than day-by-day visual structure,
- no image gallery,
- no clear provider/trust block,
- no map/location context,
- no compact “trip facts” band,
- price/season/CTA sidebar is functional but visually generic.

### Redesign direction

- Unify Tours listing and Marketplace visually so they feel like two discovery modes within RI BUROM.
- Add shared footer to listing.
- Build an experience-card component reused on homepage + tours listing.
- On detail pages, introduce trip facts near the hero, richer itinerary treatment and stronger CTA card.
- Preserve existing URLs/slugs and existing form/WhatsApp actions.

---

## 6. Workspace / CMS / Marketplace Admin

### Current strengths

- Internal tools are functional and information-dense.
- Operations has useful stats, tables and permission-aware actions.
- Marketplace enquiries have status counts and filters.
- CMS exposes a powerful level of public-site control.
- Most destructive actions are clearly red.
- Responsive rules exist for the major form grids.

### Main visual problem: there is no single workspace shell

Current internal pages use several independent layouts:

- `workspace.html`: dark sticky left sidebar,
- `cms.html`: dark horizontal CMS header,
- `marketplace.html`: standalone wide content shell with no persistent sidebar,
- `marketplace_inquiries.html`: another standalone shell,
- `customer_analytics.html`: utility-only layout with a “Back to Control Room” link.

This makes navigation feel like moving between separate admin products.

### Density problems

**CMS is extremely long.** Public copy, typography and section appearance are presented as large uninterrupted forms. The functionality is strong, but the interface has little progressive disclosure.

**Create forms dominate before management tables.** In Marketplace and Operations, large creation forms occupy substantial vertical space even when the common task may be reviewing/editing existing records.

**Tables rely on horizontal scrolling on narrow screens.** There is no mobile-specific record/card representation.

**Status and action colors are locally defined.** The same semantic intent can appear with different styling across internal screens.

**Mobile workspace navigation is weak.** The sidebar switches to a normal full-width block, putting all workspace/account links above content instead of becoming a compact drawer/top bar.

### Redesign direction

Build one shared workspace shell with:

- persistent desktop sidebar,
- compact mobile header + drawer,
- breadcrumbs/page title,
- consistent top-right actions,
- reusable stat cards,
- reusable data table,
- reusable status badges,
- reusable form fields,
- reusable confirmation/destructive-action treatment.

Then reorganize CMS into tabs/sections:
- Content,
- Brand,
- Page Structure,
- Media,
- Marketplace Appearance.

Marketplace admin should similarly separate:
- Providers,
- Services,
- Taxonomy,
- Enquiries,
- Appearance.

This is a presentation reorganization; permissions/routes/data can initially remain unchanged.

---

## 7. Mobile-specific audit

Highest-impact mobile issues:

1. Homepage hero exceeds the first viewport.
2. Homepage and marketplace footers are ~937 px tall.
3. Marketplace responsive utility classes are missing, so intended mobile refinements do not apply.
4. Workspace sidebar becomes a large content block instead of a mobile navigation pattern.
5. Dense admin tables fall back to horizontal scrolling rather than responsive record cards.
6. Long enquiry/CMS forms need grouping and progressive disclosure.

Touch targets are generally reasonable, and modal keyboard handling is already better than many early-stage marketplace implementations.

---

## 8. Recommended implementation order

### Phase UI-0 — visual infrastructure

1. Replace/fix the current compiled utility pipeline so every used utility is generated.
2. Establish design tokens: colors, type scale, spacing, radius, shadows, containers, motion.
3. Create shared public components: nav, footer, buttons, cards, chips, form controls, empty states.
4. Create shared workspace shell/components.

### Phase UI-1 — public discovery

1. Navigation + footer.
2. Homepage.
3. Marketplace.
4. Provider page.
5. Tours listing + tour detail.

### Phase UI-2 — conversion

1. Provider/service enquiry builder.
2. Homepage contact treatment.
3. Empty/loading/success/error states.

### Phase UI-3 — staff product

1. Workspace shell.
2. Operations.
3. Marketplace admin + enquiries.
4. CMS.
5. Analytics.

---

## 9. Guardrails for the refresh

The UI work should not silently change the hardened architecture.

Preserve:

- existing public URLs and slugs,
- CSRF handling,
- permission checks,
- marketplace enquiry persistence,
- notification outbox behavior,
- Cloudinary/media lifecycle,
- SEO metadata behavior,
- reduced-motion support,
- keyboard/focus behavior already added,
- CMS-backed copy and theme controls unless a deliberate migration is designed.

The visual branch should remain independent from production until the redesigned surfaces have responsive and regression checks.

---

## Audit conclusion

The UI does **not** need a cosmetic reskin first.

It needs a short infrastructure correction, followed by a deliberate visual system.

The core visual strategy should be:

> **Editorial Meghalaya travel brand on the public side; calm operations product on the staff side.**

The public interface should feel image-led, local, premium and exploratory. The workspace should feel compact, predictable and operational rather than inheriting the same decorative language.

The first implementation task should be **UI-0: repair the stylesheet/design-token layer and create the shared public/workspace primitives** before redesigning individual pages.
