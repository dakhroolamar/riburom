# RI BUROM Cloudflare production cutover gates

**As of 25 November 2026 — NO-GO for DNS cutover or production write-role switch.**
The production website remains on Render at [riburomtours.com](https://riburomtours.com).
This document records public, nonsecret technical evidence; it does not
authorize changing the live website.

## Verified acceptance evidence

| Gate | Evidence | Current result |
| --- | --- | --- |
| Full Cloudflare application staging | [Hosted acceptance #45570954629](https://github.com/dakhroolamar/riburom/actions/runs/45570954629) | Seven synthetic business workflows passed, including tour create/edit/delete, CMS draft/preview, invoice/Word export, review moderation, contact persistence, marketplace enquiry privacy and **Cloudinary upload/delivery** |
| Read-only production-data mirror | [Deployment #45558034514](https://github.com/dakhroolamar/riburom/actions/runs/45558034514) | Separate Worker, distinct SELECT-only production Neon reader through isolated Hyperdrive. Basic auth enforced, app writes and admin routes blocked |
| SEO parity | [Protected mirror tests #45561738910](https://github.com/dakhroolamar/riburom/actions/runs/45561738910) | All ten sitemap URLs checked; no metadata/structured-data discrepancies |
| Public response speed | [Production-data benchmark #45561738910](https://github.com/dakhroolamar/riburom/actions/runs/45561738910) | Cloudflare faster on all seven tested routes in small-sample paired GitHub-runner tests; not a field measurement in India |
| Compatibility + staging deployments | [Application staging #45570954629](https://github.com/dakhroolamar/riburom/actions/runs/45570954629) | Build/deploy/readiness/login checks passed |
| Email scheduling isolation | [Notification guard implementation](../deploy/cloudflare/outbox_handoff.py) and [tests](../tests/test_cloudflare_outbox_handoff.py) | Staging and read-only mirror must never schedule mail. Production requires an explicit future owner-approved handoff flag, production host, and enabled cron |
| Notification delivery retry safety | [Outbox integration tests](../tests/test_notification_outbox.py) | Simulated transport tests only; do **not** count as real Brevo delivery |

## Outstanding GO/NO-GO conditions

1. **Controlled Brevo acceptance still pending.** Obtain the owner's explicit
   approved **staging-only** recipient address and verified sender identity,
   retained only in protected settings. Configure Cloudflare application staging
   to use Brevo's least-privileged machine-to-machine OAuth credentials where
   appropriate. Verify a synthetic contact enquiry creates a notification
   outbox record, an approved test message is accepted by Brevo, the recipient
   actually receives it, and a failure can retry. Never send production customer
   records or unsolicited messages during tests. **Leave production Render's
   consumer active and all Cloudflare staging/parallel production mail
   schedules OFF.**
2. **Account resource usage missing.** From Cloudflare dashboard gather Workers
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

## Owner sign-off

**Owner authorization for live domain cutover:** Not received.

**Owner authorization for live outbox handoff:** Not received.

**Owner authorization to retire Render:** Not received.
