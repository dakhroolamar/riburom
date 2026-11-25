# Cloudflare Workers staging for RI BUROM

This deployment packages the existing Flask site and serves its tracked static assets on Cloudflare Workers Free. A Python Durable Object runs Flask and stores rate-limit counters. A Worker Cron Trigger calls the Durable Object's outbox job through an internal binding.

## Build and deploy staging

Use Python 3.13 or later, uv and Node.js. Run the commands from a fresh checkout at the repository root.

```shell
python deploy/cloudflare/build.py
cd deploy/cloudflare/build
uv run pywrangler deploy
```

The checked-in configuration deploys `riburom-free-compatibility-probe` with disposable SQLite data and a simulated mail transport. It forwards a small list of read-only routes to Flask. The staging outbox endpoint reports the status of a single synthetic job. The first scheduled attempt fails deliberately and the next eligible invocation retries it. The job never calls the Brevo API or sends mail.

For the database connection check, set `RIBUROM_STAGING_HYPERDRIVE_ID` to the isolated staging Hyperdrive configuration ID before building. The schedule runs a read-only PostgreSQL query and records successful connectivity in the Durable Object. The status endpoint exposes the result as `postgres_verified`.

The [GitHub Actions workflow](../../.github/workflows/cloudflare-staging.yml) builds and deploys changes from `codex/cloudflare-free-hosting`. Configure the `cloudflare-staging` GitHub environment to allow only that branch. Set environment variables `CLOUDFLARE_ACCOUNT_ID` and `RIBUROM_STAGING_HYPERDRIVE_ID`, and save an Individual Workers Editor token for `riburom-free-compatibility-probe` as the environment secret `CLOUDFLARE_WORKER_DEPLOY_TOKEN`. The workflow checks the HTTPS health endpoint and the recorded result of the synthetic outbox and PostgreSQL test. It uses a standard Linux runner with an eight-minute timeout. [Cloudflare Worker permissions](https://developers.cloudflare.com/workers/authorization/workers/)

## Prepare a deployment with real services

Set `RIBUROM_STAGING_HYPERDRIVE_ID` and run `python deploy/cloudflare/build.py --application-staging` to assemble `riburom-application-staging`. The profile starts with no public URL or scheduler. Set a staging-only `RIBUROM_STAGING_ACCESS_TOKEN` as a Worker secret, then build with both `--application-staging` and `--enable-staging-url` for the protected rehearsal. HTTP Basic authentication uses username `rehearsal` and that secret as the password. Check that anonymous Flask routes and static assets return 401 and that authenticated `/readyz` returns 200 before enabling the scheduler.

Store secrets in Cloudflare and set `SECRET_KEY`, `ADMIN_PASSWORD_HASH` and the staging Cloudinary settings. The staging profile uploads into `riburom-cloudflare-staging`, disables overwrites and skips deletions outside that prefix. Set `BREVO_CLIENT_ID`, `BREVO_CLIENT_SECRET`, a verified `BREVO_SENDER_EMAIL` and the owner-approved `NOTIFICATION_EMAIL` for the end-to-end staging test. The private OAuth app needs only `transactional.email:write`. Verify that the account accepts its OAuth tokens from Cloudflare while the existing API and SMTP IP controls stay active. Keep `OUTBOX_SCHEDULED=false` until the staging recipients are verified. [Brevo machine-to-machine authentication](https://developers.brevo.com/docs/oauth-m2m-authentication)

The application deployment workflow uses the separate `cloudflare-application-staging` GitHub environment. Restrict it to the staging branch and add its own Individual Workers Editor token for `riburom-application-staging`. After the staging access secret and environment are verified, set the repository variable `CLOUDFLARE_APPLICATION_STAGING_ENABLED=true` and push a candidate. The workflow checks that anonymous requests to both the Flask app and static assets are denied. Use the [transfer runbook](../../docs/render-to-cloudflare.md) for cutover and rollback.
<!-- Trigger read-only comparison deployment -->

## Recheck signed Cloudinary uploads after folder authorization

The application staging Worker is scoped to the Cloudinary root folder
`riburom-cloudflare-staging`. After the dedicated Media Library User API key
has **Folder Editor** access to that folder, rerun the opt-in hosted staging
business workflow by committing a change with `[staging acceptance]` in the
message. The workflow verifies that a small synthetic image can be uploaded
and delivered from the staging folder and exercises other business workflows.
A folder-permission change alone is not proof of a successful signed upload.

Never paste API keys or secrets into the repository, and do not modify the
production Render Cloudinary credential for this staging acceptance test.

## One-off controlled Brevo M2M acceptance

Cloudflare application staging uses the isolated staging Neon database and
has `OUTBOX_SCHEDULED=false`. Dashboard-managed `BREVO_SENDER_EMAIL` is
preserved by `keep_vars=true` on new staging deployments; encrypted Brevo
Client ID and Secret remain Cloudflare secrets. Store the intended private
test inbox as the `NOTIFICATION_EMAIL` secret. Check that `BREVO_CLIENT_ID`
and `BREVO_CLIENT_SECRET` belong to **the same** M2M app with
`transactional.email:write`.

Only a commit explicitly marked `[staging brevo send]` runs the hosted
Brevo acceptance job. It authenticates against Brevo first and, only if
OAuth works, attempts **one synthetic outbox email** to the configured
staging inbox using the existing Brevo transport and outbox pipeline. A
fixed synthetic source ID prevents duplicate sends on repeated runs. The
route is restricted to the isolated application Worker, HTTP Basic and the
staging-only database demo records. It does not process other outbox rows,
enable a Cron schedule or touch Render. No API tokens, secret values,
recipient address or message body is logged in CI. Brevo API acceptance is
not proof of mailbox delivery: verify the approved inbox separately.
