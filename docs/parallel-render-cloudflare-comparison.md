# RI BUROM: Parallel Render and Cloudflare acceptance

## Status and safety boundary (23 November 2026)

- **Render is production.** Keep the existing custom domain, Render web process,
  Neon production database, Brevo outbox consumer, and mail DNS unchanged.
- **Cloudflare application staging** is a password-protected Worker backed by its
  **separate Neon staging project**. It has real published website content copied
  for comparison, but no production staff logins, enquiries or invoices. It is
  safe to test writes only with synthetic staging-specific data.
- **Cloudflare parallel comparison** is a *different*, proposed password-protected
  Worker. It will use a separate **SELECT-only** Neon role through a distinct
  Hyperdrive configuration pointing to production. The Worker rejects all HTTP
  writes, admin routes and private API routes. It has **no Cron Trigger**.
  This Worker is NOT deployed until its dedicated credentials are provisioned.
- No DNS cutover, no Render shutdown, and no dual notification consumers.

## Why a read-only production comparison

The production site has real customer information and notifications. Sending
both independently writable web applications against the same database and
turning on two email schedulers would risk duplicate and inconsistent mail.
A production-data mirror can measure page rendering against identical records
without giving the second site permission to mutate invoices, enquiries or
accounts. Continue to exercise the full write workflows on the isolated staging
Neon database.

## Verified production reader (25 November 2026)

Neon's production reader `riburom_comparison_reader` is already initialized.
Its password was successfully configured, and it authenticates with the direct
Neon endpoint. **Do not reset the password again to work around a browser
selector failure.** A live connection as this role showed
`transaction_read_only=on`, search path
`pg_catalog, riburom_public_comparison`, four published tours and two public
providers. Reading `public.messages` failed with SQLSTATE 42501.
This role has no inherited role memberships, database/schema CREATE grants,
or base-table read/write privileges; it can SELECT only from 17 public views.

**Manual secret-safe handoff:** In Neon Console → RI BUROM (production) →
Connect, select the `riburom_comparison_reader` role, `neondb` database,
and **Direct connection** endpoint. Click **Copy snippet**. The password can
remain masked; there is no need to find or click “Show password”.
Do not paste the snippet into chat, a GitHub issue, git history, or a workflow
command that echoes it.

In the Cloudflare dashboard open **Storage & databases → Postgres & MySQL
(Hyperdrive) → Create Configuration**. Create a new configuration named
`riburom-production-readonly` using the copied Neon PostgreSQL connection
string. Keep the database in the production Neon project, not staging, and
**disable Hyperdrive query caching** during page-parity measurements.
Store this credential only in Cloudflare Hyperdrive's protected origin
configuration. Copy *only the generated 32-hex Hyperdrive configuration ID*
into the `RIBUROM_PARALLEL_HYPERDRIVE_ID` environment variable described below.

The connected ChatGPT Neon service can verify/read this login but cannot
write into Cloudflare account settings. Cloudflare's separate account-level
Hyperdrive setup must be completed through its own authorized dashboard/API
before the GitHub workflow can deploy.

## Provision only the following separate Cloudflare comparison resources

1. Create a **new** Cloudflare Hyperdrive configuration targeting the **RI BUROM
   production Neon project**, but authenticate with a dedicated role granted
   SELECT only on the tables required by the site. Confirm its project endpoint
   is NOT the Cloudflare staging Neon project. Keep query caching disabled until
   consistency has been evaluated.
2. Create GitHub Actions environment `cloudflare-parallel-comparison` for branch
   `codex/cloudflare-free-hosting`, with variables:
   `CLOUDFLARE_ACCOUNT_ID`, `RIBUROM_PARALLEL_HYPERDRIVE_ID`, and
   `RIBUROM_STAGING_HYPERDRIVE_ID`. The last two IDs must differ.
3. Set **environment secrets** in GitHub, not in chat:
   `CLOUDFLARE_WORKER_DEPLOY_TOKEN` (scope to the **new**
   `riburom-parallel-comparison` Worker),
   `RIBUROM_PARALLEL_ACCESS_TOKEN` (random >=16 characters),
   `RIBUROM_PARALLEL_SESSION_SECRET` (random >=32 characters), and
   `RIBUROM_PARALLEL_ADMIN_HASH` (a distinct nonproduction valid Werkzeug
   password hash; never reuse the production Owner password).
4. Set `CLOUDFLARE_PARALLEL_ENABLED=true` as a repository variable only after
   both identities and scopes have been independently verified. This enables
   `.github/workflows/cloudflare-parallel-comparison.yml`.
5. The workflow deploys to
   `https://riburom-parallel-comparison.dakhroo.workers.dev`. It fails unless
   unauthenticated requests are blocked, the DB role lacks write privileges,
   public pages load, and administrative and POST routes are blocked.
   The workflow never touches Render or the live domain.

## Comparison measurements

Run identical public routes `/`, `/all_tours`, `/about`,
`/marketplace`, `/stories`, and at least two tour detail pages against
Render and the shadow Worker in the same measurement window. Measure:
- HTTP status and content parity (published tours, reviews, public photos,
  SEO metadata, canonical URLs, correct image and downloadable PDF links)
- Cold and warm TTFB, p50/p95 total response time, bytes, and errors
- Mobile browser LCP, CLS, INP, and request waterfalls from India
- Several concurrent read-only GET requests, then post-idle behavior
- Cloudflare Workers, Durable Object, Hyperdrive, and Neon usage versus
  their free tier quotas and observed Render usage.

A CI runner outside India is useful for comparisons but is **not** a substitute
for testing users in the target geography. Record test region and sample counts.

## Feature sign-off, then optional live-domain cutover

Full staging tests must demonstrate CSRF/session/revocation, staff permissions,
a synthetic website enquiry and marketplace enquiry, the outbox and controlled
Brevo receipt, photo/PDF upload and review moderation, and Word invoice export.
Verify the staging-only folder and staging-only mail recipients.

Only after explicit sign-off may the separate production Cloudflare Worker be
reconfigured to use the live production credentials and appropriate write roles.
At that stage, keep Render running as the rollback web host, but permit only
**one** outbox consumer. A domain switch is a separate, reversible action after
TLS, DNS, mail records, and the direct Render URL are recorded. Do not detach
or delete Render while comparing.

## Rollback criteria

Immediately restore Render traffic (or keep it unchanged) if any public page,
staff function, database write, email handoff, privacy check, or performance
threshold fails. Maintain one known-good production commit and a database
recovery point. Never transfer live production secrets or private records into
the test-only staging Neon project.
