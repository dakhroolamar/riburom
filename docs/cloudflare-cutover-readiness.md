# RI BUROM Cloudflare production cutover gates

**As of 26 November 2026 — NO-GO for DNS cutover and notification handoff.**
The production website remains on Render at [riburomtours.com](https://riburomtours.com).
This document records public, nonsecret technical evidence; it does not
authorize changing the live website.

## DNS preparation and inbound mail gate

- Cloudflare Free has a pending, DNS-only mirror with assigned nameservers
  `hattie.ns.cloudflare.com` and `leland.ns.cloudflare.com`. Direct queries to
  each matched all 13 observed Namecheap A, CNAME, MX and TXT records,
  including Brevo verification, both DKIM selectors, DMARC, SPF and Google
  verification. Authoritative delegation still names
  `dns1.registrar-servers.com` and `dns2.registrar-servers.com`. The registry
  returned no DS record. [Namecheap record inventory](riburomtours-namecheap-2026-11-26.zone)
- The Namecheap dashboard shows Email Forwarding selected. Namecheap documents
  this service for domains delegated to its own DNS. The registrar's Redirect
  Email page currently shows no forwarding aliases or catch-all. Confirm
  whether replies to the verified Brevo sender `info@riburomtours.com` should
  reach an existing mailbox. If they should, prepare and verify inbound
  forwarding before delegation. If that address is send-only, record the
  owner's decision. Keep Google verification and all Brevo records intact
  when applying any approved replacement MX and SPF configuration.
  [Namecheap Email Forwarding](https://www.namecheap.com/support/knowledgebase/article.aspx/308/2214/how-to-set-up-free-email-forwarding/)
- If DNS delegation must be rolled back, restore Namecheap BasicDNS at the
  registrar and confirm both original nameservers appear at the registry.
  Restore the saved records and Namecheap forwarding configuration if any
  changed. Verify incoming business mail and the Render HTTPS redirect and
  readiness while recursive DNS caches converge. For a web-only rollback,
  restore the Render records in the authoritative zone and keep the active
  inbound mail service in place.

## Additional production acceptance

- All four Brevo bindings are installed. A one-message protected probe verified
  that the runtime reaches Brevo's OAuth endpoint. Brevo returned HTTP 401
  `invalid_client` during the token exchange. The probe stopped before reserving
  or submitting a message and did not touch the production outbox. The candidate
  passed authenticated readiness and all ten sitemap checks on `5befa19a`
  (`11ba722`). Replace only the two OAuth credential bindings with the valid
  pair from the existing approved app, then repeat the gated probe. Keep the
  live-outbox flags false and the production Cron Trigger absent.
  [Hosted OAuth diagnostic](https://github.com/dakhroolamar/riburom/actions/runs/45793098375)
- The protected candidate returned HTTP 200 before and after six minutes
  without rehearsal traffic. Readiness TTFB was 1.42 s before the wait,
  7.42 s immediately after, and 1.13 s on the warm follow-up. An earlier
  rollout attempt hit a transient database connection timeout. Extending the
  Hyperdrive handshake allowance from five to ten seconds cleared readiness
  on version `77f6fd8a`. Its follow-up idle check returned HTTP 200 before and
  after the wait and on a warm follow-up, with 1.20 s, 6.99 s and 0.49 s TTFB.
  The shared production database also serves Render, so these checks do not
  isolate a Neon compute cold start. [First idle test](https://github.com/dakhroolamar/riburom/actions/runs/45765540928) · [Post-fix idle test](https://github.com/dakhroolamar/riburom/actions/runs/45767104854)
- Two signed-in passes through all eight Control Room sections completed.
  Median browser click-to-expected-heading time was 2.81 s across 16 navigations.
  The first Trips navigation took 14.41 s and its second took 3.73 s.
  The Trips summary now issues one aggregate query in place of four count
  statements. The old and new predicates matched in one read-only Neon check.
  Three signed-in Trips visits after deployment completed in 2.75 s, 5.32 s
  and 5.09 s. These samples confirm the new path works and are insufficient
  to attribute a page-latency change to the SQL reduction. Settings reported
  both email notifications and Cloudinary media storage as configured.
- Fifty-four isolated application tests passed, covering Control Room handling,
  notification outbox persistence and retries, multiple services in an enquiry,
  and session revocation. Eight Worker boundary and scheduler-policy tests passed.
- The Hyperdrive dashboard showed 23,485 of 100,000 statements used so far
  that UTC day. The rolling 24-hour view showed 6,410 candidate, 23,290
  staging and 46,490 comparison statements. The daily snapshot had room for
  about 7,651 additional requests at 10 statements per request, 3,825 at 20,
  or 1,912 at 40, assuming no other use. These are capacity scenarios for
  uncached requests. The test-heavy mix and unknown production traffic mean
  they are unsuitable as a customer traffic forecast. Exceeded free quotas
  reject further operations until reset. The dashboard confirmed Workers
  Free and showed 1,665 out of 100,000 account requests for the UTC day.
  Standard GitHub-hosted runners in this public repository are free.
  [Worker limits](https://developers.cloudflare.com/workers/platform/limits/) · [Hyperdrive quotas](https://developers.cloudflare.com/hyperdrive/platform/pricing/) · [GitHub Actions billing](https://docs.github.com/en/actions/concepts/billing-and-usage)
- The database reports six hours of point-in-time history and zero stored
  snapshots. Neon successfully read the schema at the 11:34 IST recovery
  timestamp and found no difference from the current schema. The production
  outbox showed zero pending rows and zero active claims at that checkpoint.
  The recovery window rolls forward. This check did not restore application
  data or rehearse a full database restore.

## 26 November candidate deployment

| Check | Result |
| --- | --- |
| Cloudinary and runtime startup | The owner installed `RIBUROM_PRODUCTION_CLOUDINARY_URL`. The next run uploaded it as a separate Worker update and still returned startup HTTP 503. Deploying the code and all four required bindings in one Worker version cleared startup. The precise cause of the separate-update failure was unconfirmed. [Separate-update run](https://github.com/dakhroolamar/riburom/actions/runs/45757603249) · [Successful atomic deploy](https://github.com/dakhroolamar/riburom/actions/runs/45758065320) |
| Protected Worker | Commit `bb9f6d0`, Worker version `5a352b48-cf1c-4be2-8522-e2a4f7937847`. Linux packaging passed. Anonymous health, readiness and static-asset requests were denied with 401. Authenticated `/healthz` and `/readyz` passed, and readiness passed again after the SEO sweep. |
| Database and SEO | Startup passed the Hyperdrive role, database, schema, revision and restricted-grant checks against the existing production database. A separate catalog query confirmed SELECT on all public tables and INSERT/UPDATE privileges on the eight core enquiry, outbox, invoice, staff, media, marketplace and settings tables checked. Ten same-origin sitemap pages matched Render with zero SEO discrepancies. No business data was changed. |
| Control Room | The owner signed in to the protected candidate. Read-only navigation reached all eight sections with the expected page titles and routes. The session survived reloading the Overview. Logout, role-specific behavior, and business mutations remain separate acceptance checks. |
| Brevo bindings | The dashboard shows `BREVO_CLIENT_ID` and `BREVO_CLIENT_SECRET` as encrypted secrets and `BREVO_SENDER_EMAIL` and `NOTIFICATION_EMAIL` as variables on `riburom-application-staging`. All four are absent from `riburom-production`. The existing M2M app passed staging delivery with `transactional.email:write`. Reuse its approved credentials for the same Brevo account, with the verified production sender and intended production recipient. The candidate has no Cron Trigger and both live-outbox guards are false. [Staging acceptance](https://github.com/dakhroolamar/riburom/actions/runs/45576771477) · [Brevo M2M](https://developers.brevo.com/docs/oauth-m2m-authentication) |
| Resource snapshot | The candidate dashboard showed 115 Worker invocations and one error across all versions in 24 hours. The active version showed 8.18 ms median Worker CPU and zero errors in that snapshot. The candidate Durable Object showed 37 requests, one error and 15.23 GB-seconds across all versions. Hyperdrive showed 396 candidate statements over 24 hours and 4,515 across the account so far that UTC day, against the 100,000 daily allowance. This snapshot includes rehearsal traffic and does not establish customer capacity. |
| Remaining gates | Verify the remaining staff workflows, production Cloudinary and Brevo permissions, controlled idle behavior and free-tier headroom, current Render rollback release, and the authoritative DNS and recovery evidence. Production routing and notification handoff both require owner approval. |

### Public performance against the production candidate

GitHub-hosted Chromium recorded five homepage navigations per host and device.
The candidate was `5a352b48`, with the same live database as Render. All sampled
browser and paired HTTP requests succeeded. Mobile used simulated network and
device settings. The browser measured blocking from FCP through the sample
window, with a median of 0 ms on both hosts and devices.

| Homepage median | Desktop Render | Desktop candidate | Mobile Render | Mobile candidate |
| --- | ---: | ---: | ---: | ---: |
| TTFB | 3,775 ms | 1,169 ms | 3,477 ms | 1,138 ms |
| FCP | 6,340 ms | 2,400 ms | 4,712 ms | 1,936 ms |
| LCP | 6,384 ms | 2,448 ms | 13,316 ms | 2,196 ms |
| Load event | 6,352 ms | 2,409 ms | 13,300 ms | 5,311 ms |
| CLS | 0 | 0.0251 | 0 | 0 |

The HTTP homepage median TTFB was 3,442 ms on Render and 1,105 ms on
Cloudflare over ten paired requests. At three concurrent cache-bypassed
requests, it was 5,016 ms and 1,140 ms, respectively. Tours, About,
Marketplace and Stories all recorded ten Cloudflare cache hits in ten warm
samples per route, with median TTFB ranging from 67 to 103 ms. With the cache
bypassed, those routes ranged from 838 to 1,130 ms on Cloudflare. The samples
are too small for a stable p95. Controlled cold/idle, authenticated Control
Room and field performance in India remain open. [Hosted benchmark](https://github.com/dakhroolamar/riburom/actions/runs/45758525076) · [Timing and screenshot artifact](https://github.com/dakhroolamar/riburom/actions/runs/45758525076/artifacts/15088744721)

## 26 November pre-deployment checkpoint

| Check | Result |
| --- | --- |
| Live Render and public DNS | HTTPS `/readyz` returned 200 on both the apex and `riburom.onrender.com`. HTTP apex and HTTPS `www` each redirected with 301 to HTTPS apex. `robots.txt` and `sitemap.xml` returned 200. Public DNS still points to the Render targets recorded below. The five MX records and SPF were visible. DMARC was unverified, and the authoritative export, DKIM selectors and DNSSEC state are still required before changing delegation. |
| Candidate source and deployment | Remote branch head `7899e0d` passed packaging, and its deploy job was skipped. The Cloudflare dashboard showed version `9e6f9947` at 100% on the protected candidate hostname. The deployed code came from `48d04c4`; the secret uploads in that run created further Worker versions. [Packaging run](https://github.com/dakhroolamar/riburom/actions/runs/45608669810) · [Last hosted deploy](https://github.com/dakhroolamar/riburom/actions/runs/45607959234) |
| Preview and mail isolation | Anonymous `/healthz`, `/readyz` and the protected static logo each returned 401. The Worker settings show both live-outbox flags `false` and no Cron Trigger. Production Brevo settings were absent from the candidate. The earlier staging Brevo delivery remains the only hosted delivery evidence for Cloudflare. |
| Startup blocker | The last authenticated `/readyz` returned 503 with a startup trace ending at Flask's `storage` import. Production storage requires Cloudinary. Both the GitHub candidate environment and active Worker lacked its credential. The existing workflow fix checks and installs `CLOUDINARY_URL` from the encrypted `RIBUROM_PRODUCTION_CLOUDINARY_URL` environment secret. Hosted startup, database guard and SEO still need to pass after it is set. |
| Deployment token and Hyperdrive | The deploy token is present in the intended GitHub environment. The last run deployed the Worker and installed its three preview secrets with that token. The dedicated binding points to the production Neon endpoint, database `neondb`, and role `riburom_worker_app`; Cloudflare shows query caching disabled. The latest candidate startup stopped before verifying the role, schema and grants through Hyperdrive. |
| Direct Neon check | One read-only query as `riburom_worker_app` confirmed `neondb`, schema `public`, Alembic revision `ea4cd9f32108`, enquiry INSERT and tour UPDATE privileges, and denial of schema CREATE. Production has six hours of retained history. A recent recoverable timestamp and recovery rehearsal remain cutover gates. No customer rows were read or changed during this check. |
| Performance and quotas | The earlier read-only mirror recorded median homepage TTFB of 3,878 ms on Render and 534 ms on Cloudflare. A fully functional browser and admin comparison is pending. Cloudflare showed about 19,700 staging statements, 34,330 comparison statements and zero production-candidate statements over the preceding 24 hours. This mixed testing window is unsuitable for estimating customer capacity. Workers and Durable Objects each have a 100,000-request free daily limit. Hyperdrive has a 100,000-statement free daily limit. Check shared production headroom and each provider plan after authenticated readiness. [Workers limits](https://developers.cloudflare.com/workers/platform/limits/) · [Durable Object quotas](https://developers.cloudflare.com/durable-objects/platform/pricing/) · [Hyperdrive quotas](https://developers.cloudflare.com/hyperdrive/platform/pricing/) |

The Cloudinary secret is installed in the
[candidate GitHub environment](https://github.com/dakhroolamar/riburom/settings/environments/28508548003/edit).
Future protected deployments use the migration branch marker
`[production candidate]` and verify both authenticated probes.

## Verified acceptance evidence

### Production candidate, 25 November 2026

The candidate profile builds a separate Worker named `riburom-production` at
`riburom-production.dakhroo.workers.dev`. Its public canonical origin is
`https://riburomtours.com`. The preview requires HTTP Basic authentication
on application pages and assets. Only staff login and logout accept POST.
Render handles business submissions during rehearsal. The candidate has its
own Durable Object, no custom domain, no Cron Trigger and disabled mail processing.

| Item | Verified evidence |
| --- | --- |
| Render rollback service | `https://riburom.onrender.com`, deployment `dep-dbunif8u01pc73f7gp5g`, live commit `f9bebee9feddbdc05959d3bc8d351abbed935b92`. Direct and apex HTTPS `/readyz` returned 200. HTTP apex and HTTPS www redirected to HTTPS apex with 301. |
| Observed public DNS | Apex A `216.24.57.1`, www CNAME `riburom.onrender.com`, authoritative NS `dns1.registrar-servers.com` and `dns2.registrar-servers.com`. MX priorities 10 for eforward1/2/3, 15 for eforward4, 20 for eforward5 under `registrar-servers.com`. SPF `v=spf1 include:spf.efwd.registrar-servers.com ~all`. Export the authoritative zone including DKIM selectors, DMARC, verification records, TTLs and DNSSEC/DS before any nameserver or record change. |
| Database and recovery | RI BUROM production, PostgreSQL 18, database `neondb`, migration head `ea4cd9f32108` matches the candidate. The migration version files and ORM model files match Render. The project reports 21,600 seconds of history and zero snapshots. Observed WAL `0/152E3BB0` at 10:44:10 UTC. This point expires. Verify a fresh recoverable point and rehearse restoration into a separate recovery environment before cutover. |
| Application role | Provisioned `riburom_worker_app` using [production-role.sql](../deploy/cloudflare/production-role.sql). Verified zero owned relations, database or schema ownership, role memberships, schema CREATE, replication, bypass-RLS or administrative privileges. A transaction assumed the role, inserted, updated and read one synthetic enquiry, rolled back to a savepoint and verified zero remaining rows. No outbox enqueue or sequence advancement. Password authentication through Hyperdrive requires a separate hosted check. |
| Live SEO | Ten production sitemap URLs passed the canonical, metadata, robots and verification checks. Repeat against the deployed candidate using `python tests/cloudflare_seo_acceptance.py --candidate production`. |

### Deploy and verify the candidate

1. Neon generated the dedicated role's initial password inside PostgreSQL.
   A fresh connection authenticated as `riburom_worker_app` and repeated
   the insert, update, read and rollback check successfully. Use Neon's
   **Connect** dialog for this existing role. Use a dedicated Hyperdrive with the direct
   production Neon endpoint, database `neondb`, this role, required TLS and
   query caching disabled for fresh authentication, moderation and outbox reads.
2. Set `RIBUROM_PRODUCTION_HYPERDRIVE_ID` to that configuration ID. Use the
   existing staging and comparison IDs as cross-checks. Assemble with
   `python deploy/cloudflare/build.py --production-candidate`. The first
   application request validates the actual server-side role, schema revision
   and application privileges. Never run the staging bootstrap on this Worker.
3. Store a fresh preview password as `RIBUROM_STAGING_ACCESS_TOKEN` on this
   Worker, a production session `SECRET_KEY`, and a valid `ADMIN_PASSWORD_HASH`.
   Existing staff authenticate against Neon. Supply production Cloudinary
   credentials scoped to the required media folder and production verification
   settings. Configure the intended Brevo sender, recipient and M2M credentials
   in encrypted Worker settings. Leave the live-outbox flag false.
4. The candidate workflow packages on Linux with a synthetic binding. Hosted
   deployment uses the `cloudflare-production-candidate` GitHub environment,
   its Worker-scoped deployment token, account and three Hyperdrive IDs, and a
   masked copy of the preview password as `RIBUROM_CANDIDATE_ACCESS_TOKEN`.
   Set repository variable `CLOUDFLARE_PRODUCTION_CANDIDATE_ENABLED=true` and
   use a migration-branch commit containing `[production candidate]` when ready.
   Database and application-provider passwords stay in their provider stores.
5. Verify protected readiness, SEO, staff login, session revocation and role
   restrictions. Exercise writes on isolated staging. Use a transaction with
   a savepoint for candidate DB write verification. Keep synthetic enquiries
   and invoice requests off the two public business endpoints during rehearsal.
   Compare matched Render/candidate reads, mobile layout and observed quotas.
6. If candidate checks fail, keep Render serving and disable the candidate
   endpoint or restore its last known Worker version. At cutover, record a
   fresh DNS export, deploy version, queue counts and recoverable timestamp.
   Route rollback sends apex and www back to their recorded targets. Retain
   business writes in the shared database. Use database recovery only for a
   separately assessed data incident.

| Gate | Evidence | Current result |
| --- | --- | --- |
| Full Cloudflare application staging | [Hosted acceptance #45570954629](https://github.com/dakhroolamar/riburom/actions/runs/45570954629) | Seven synthetic business workflows passed, including tour create/edit/delete, CMS draft/preview, invoice/Word export, review moderation, contact persistence, marketplace enquiry privacy and **Cloudinary upload/delivery** |
| Read-only production-data mirror | [Deployment #45558034514](https://github.com/dakhroolamar/riburom/actions/runs/45558034514) | Separate Worker, distinct SELECT-only production Neon reader through isolated Hyperdrive. Basic auth enforced, app writes and admin routes blocked |
| SEO parity | [Protected mirror tests #45561738910](https://github.com/dakhroolamar/riburom/actions/runs/45561738910) | All ten sitemap URLs checked; no metadata/structured-data discrepancies |
| Public response speed | [Production-data benchmark #45561738910](https://github.com/dakhroolamar/riburom/actions/runs/45561738910) | Cloudflare faster on all seven tested routes in small-sample paired GitHub-runner tests; not a field measurement in India |
| Compatibility + staging deployments | [Application staging #45570954629](https://github.com/dakhroolamar/riburom/actions/runs/45570954629) | Build/deploy/readiness/login checks passed |
| Email scheduling isolation | [Notification guard implementation](../deploy/cloudflare/outbox_handoff.py) and [tests](../tests/test_cloudflare_outbox_handoff.py) | Staging and read-only mirror must never schedule mail. Production requires an explicit future owner-approved handoff flag, production host, and enabled cron |
| Notification delivery retry safety | [Outbox integration tests](../tests/test_notification_outbox.py) | Simulated transport tests only; do **not** count as real Brevo delivery |
| Staging Brevo M2M live acceptance | [Hosted OAuth + one-email test #45576771477](https://github.com/dakhroolamar/riburom/actions/runs/45576771477) | **PASS:** OAuth token accepted with `transactional.email:write`; one synthetic mail accepted; staging Neon outbox `SENT` in one attempt; matching message found in the explicitly selected Gmail inbox; no production data |

## Outstanding GO/NO-GO conditions

1. **Controlled staging Brevo acceptance completed.** One artificial message
   was sent only to the owner-configured staging inbox after successful
   scoped OAuth authorization and a synthetic-record Neon database check.
   Confirmed it arrived in Gmail, not merely that Brevo returned HTTP 201.
   This verifies **one** controlled delivery; failure recovery is covered by
   mocked transport tests, not a live induced Brevo outage. Keep both
   staging and read-only production mirror Cron schedules disabled; the
   live Render notification consumer remains authoritative.
2. **Account resource usage baseline.** The handoff recorded 786 staging
   Worker invocations, zero execution errors, 6.31 ms median active-version CPU,
   and about 24,860 staging Hyperdrive queries in 24 hours, including CI bursts.
   Measure representative customer traffic and shared-account headroom. From Cloudflare dashboard gather Workers
   requests, CPU and error outcomes; Durable Object requests/duration and errors;
   Hyperdrive statements, connection errors and free-plan headroom. GitHub's
   worker-scoped deployment token cannot read all analytics. Do not broaden
   deployment-token permissions just to fetch metrics; use owner dashboard
   screenshots. Refer to the [Workers](https://developers.cloudflare.com/workers/platform/limits/),
   [Durable Objects](https://developers.cloudflare.com/durable-objects/platform/pricing/)
   and [Hyperdrive](https://developers.cloudflare.com/hyperdrive/platform/pricing/)
   official limits.
3. **Real mobile check in India remains limited to manual observation.** A GitHub
   runner benchmark is not Core Web Vitals from a real device. Confirm pages,
   Control Room performance, upload/download reliability after idle, and error
   messages on typical Indian networks.
4. **Credential hygiene:** An apparent Cloudinary Root API secret was shared in
   earlier discussion. Audit exposure and rotate any genuinely exposed Root
   credential using a coordinated replacement across services that depend
   on it. Never paste credentials into GitHub issues, commits or diagnostic logs.
   Keep staging's folder-restricted credential separate.
5. **Production-only deployment and migration gate:** After explicit sign-off,
   provision a separate production Worker and writable Neon production
   identity as needed. Confirm the production schema version, verified recovery
   point, intended Cloudinary/Brevo settings, domain TLS, canonical URLs,
   redirects, and existing Google Search Console verification.
6. **Rollback rehearsal:** Record current production Render deploy SHA, exact
   Render URL, DNS apex/www targets, mail DNS records (MX/SPF/DKIM/DMARC),
   and how to restore traffic. Verify Render remains fully usable and its
   notification consumer is active **before** any change. After a confirmed
   change window, hand over at most one consumer at a time (see below).


## Brevo and dashboard-variable retention

- Added `keep_vars=true` to the application staging Wrangler profile,
  so a CI deployment does not remove the operator-configured plaintext
  `BREVO_SENDER_EMAIL` setting from the Cloudflare dashboard. Brevo M2M
  Client ID, Client Secret and the recipient remain encrypted Worker secrets.
- The explicit opt-in `[staging brevo send]` acceptance ran once with the
  existing Basic-protected Worker, staging demo database guard and a fixed
  synthetic source ID. It never activates background delivery or touches the
  production Neon database. Further reruns return `already_sent` without
  duplicate email, when the same staging database is retained.
- The recipient's Gmail inbox contained the matching message with an
  Inbox label. Do not include personal email addresses or credentials in
  public CI logs or issue comments.

## Notification handoff (requires owner approval; do not execute yet)

- Staging and parallel comparison Workers must have no Cron Trigger and
  `OUTBOX_SCHEDULED=false`. Runtime `OUTBOX_WORKER_ENABLED=false`.
- In the future **production-only** Worker, keep `OUTBOX_SCHEDULED=false`
  and `RIBUROM_LIVE_OUTBOX_APPROVED` unset until DNS/functional tests
  pass and the owner specifically approves mail handoff.
- Disable Render's outbox consumer, allow any in-flight lease to settle, and
  inspect the database queue without exposing recipient details.
- Only then set `RIBUROM_LIVE_OUTBOX_APPROVED=true` and
  `OUTBOX_SCHEDULED=true` on the verified production Worker with
  `RIBUROM_HOST=riburomtours.com`. Enable its Cron Trigger, submit one
  approved synthetic enquiry and verify delivery and retries.
- On rollback, immediately disable Cloudflare's production mail consumer
  **before** re-enabling Render's, then restore the saved routing state.
  Do not enable two consumers deliberately even with DB leases.
- Keep Render provisioned for a rollback comparison; retirement is a
  separate owner decision, not an automatic post-cutover action.

## Emergency rollback after cutover

1. On the live Cloudflare Worker, remove the production Cron Trigger and
   deploy `OUTBOX_SCHEDULED=false` and `RIBUROM_LIVE_OUTBOX_APPROVED=false`.
   Confirm the new version is active and new scheduled processing has stopped.
2. Restore web traffic to the saved Render origin. If cutover used a Workers
   Route over a working Render origin, remove that route. If it used a Worker
   Custom Domain, detach it and restore the saved apex A `216.24.57.1` and
   `www` CNAME `riburom.onrender.com` in the authoritative zone. Use the signed-off
   cutover DNS export if records changed before handover. Preserve the mail
   records, verification records and DNSSEC configuration. Verify HTTPS apex
   readiness and the canonical `www` redirect from outside the account.
3. Wait for any in-flight Cloudflare notification claims to finish or expire.
   In the shared Neon outbox, check the count of `PROCESSING` rows where
   `next_attempt_at > now()` without reading recipients or payloads. When no
   active claims remain and Cloudflare scheduling is off, set
   `OUTBOX_WORKER_ENABLED=true` on the retained Render web service and apply
   the environment change with a deploy. Confirm the Render app is live and
   its consumer is processing the queue. Reconcile ambiguous deliveries with
   Brevo before replaying any job manually.
4. Confirm staff login, recent accepted enquiries, and normal queue progress.
   Keep the shared Neon database in place. Database restoration requires a
   separate data-recovery decision.

## Owner sign-off

**Owner authorization for live domain cutover:** Not received.

**Owner authorization for live outbox handoff:** Not received.

**Owner authorization to retire Render:** Not received.
