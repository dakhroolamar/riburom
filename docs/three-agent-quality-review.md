# Three-agent website quality review

Date: 10 October 2026 (Asia/Calcutta). Baseline: a43bd1f. Scope: public website and staff CMS source, operational workflows, authorization boundaries, data consistency, notifications and realistic growth limits.

The Developer assessed feasibility and implemented operational fixes. The Reviewer independently reproduced bugs and wrote regression tests. The Critic challenged the design and assessed residual risks. The coordinating agent integrated and verified their changes. Agreement means the reviewed changes meet the stated operational scope; it is not a claim of unlimited capacity or absence of all vulnerabilities.

## Agreed findings and corrections

| Finding | Correction | Independent evidence |
| --- | --- | --- |
| Older package/trip forms could overwrite another manager's saved work | Existing timestamps become SQLAlchemy version checks; forms require current tokens; conflicting saves roll back with 409 | Separate database sessions read the same version; the losing commit fails and the winning data remains |
| Quotes could reopen terminal enquiries or downgrade confirmed bookings | Closed, declined and spam records require explicit reopening; revised quotes preserve confirmed state; quote/conversion changes use atomic enquiry checks | Terminal-state, stale-token and confirmed-state persistence tests |
| Editing a trip linked to package 201+ could silently clear the association | Current linked package is included even outside the bounded selector, including its template data | Regression creates 205 packages and verifies rendered selected option and persisted link |
| Document review defaults could verify a pending/rejected document or erase its note | Saved status and note are prefilled with escaped content | Rendered form and note/status update persistence tests |
| VERIFIED partners were suggested as approved operational partners | Suggestions use actual public approval states plus Enabled | Source review of state filter and user-facing wording |
| Authenticated traveller pages lacked explicit privacy cache controls | Operational/customer HTML responses use private, no-store; static assets retain caching | Enquiry, quote and private preview response assertions |
| Private package preview had a blank browser title; browser favicon returned 404 | Escaped preview title and existing brand favicon response | Title/noindex/header assertions and public favicon test |

No schema migration is required for these corrections: package and trip timestamps already exist.

## Four-pillar consensus

- **Usability:** agreed corrections make daily work safer and preserve the visible state staff intended to edit. Desktop and mobile interaction verification is required before release.
- **Scalability:** bounded queries and durable transactional queue claims suit the current staff-assisted model. No production load test or throughput promise is made. The template selectors and payloads need a growth plan.
- **Security:** source-specific permissions, CSRF protections, private document access and session controls were inspected. Privacy caching was hardened. No authorization bypass was demonstrated in this scope; this is not a penetration-test certificate.
- **Quality:** meaningful tests cover persistent state, competing database sessions, workflow transitions and form rendering. Final acceptance requires full-suite and browser checks, followed by CI and deployment health verification if released.

## Explicit remaining limits

- Configure shared Redis/Valkey rate-limit storage before adding workers or application instances. The default in-memory store does not aggregate limits across processes.
- Package choices initially include 200 records, and previous-trip choices include 30 recent records. The selected existing package is preserved. Add authorized search and on-demand template loading as the catalogue grows; embedded package content can make pages large.
- External notifications are at least once. If a provider accepts a message immediately before the worker/database fails, a retry can duplicate delivery. A durable queue does not make that external transaction atomic.
- Historical spam and malformed legacy dates remain unchanged. New submission validation and explicit spam operations do not repair old customer records automatically.
- A successful photo upload followed by an invalid PDF can leave an unreferenced upload. This pre-existing storage cleanup issue is low impact and does not overwrite customer or package data.
- Production customer records were not changed to exercise save flows. Database race tests and browser mutation workflows use disposable local/CI fixtures.

## Validation record

The integrated local suite ran 246 tests: 236 passed and 10 PostgreSQL-dependent tests skipped locally. Ten independent consistency regressions passed. The complete tourism operations browser workflow passed on desktop (1440×1000) and mobile (390×844), without console or page errors. Browser validation used installed Playwright because the Browser plugin is unavailable.

An intermittent quote-to-trip browser test failure was investigated on fresh disposable fixtures. The form and dialog were correct, and both the original and instrumented workflows passed. The test now waits for navigation load completion and asserts visible dialog state before interacting, avoiding actions before deferred script initialization. No forced interaction or weakened visibility check was introduced.

All three agents approved the resulting patch for the stated scope. PostgreSQL validation is configured in CI. Deployment and CI results are recorded in the accompanying release response.
