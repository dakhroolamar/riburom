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

The compatibility Worker also records a one-time, unauthenticated SMTP TLS and EHLO check against Brevo. It sends no message.

The [GitHub Actions workflow](../../.github/workflows/cloudflare-staging.yml) builds and deploys changes from `codex/cloudflare-free-hosting`. Configure the `cloudflare-staging` GitHub environment to allow only that branch. Set environment variables `CLOUDFLARE_ACCOUNT_ID` and `RIBUROM_STAGING_HYPERDRIVE_ID`, and save an Individual Workers Editor token for `riburom-free-compatibility-probe` as the environment secret `CLOUDFLARE_WORKER_DEPLOY_TOKEN`. The workflow checks the HTTPS health endpoint and the recorded result of the synthetic outbox and PostgreSQL test. It uses a standard Linux runner with an eight-minute timeout. [Cloudflare Worker permissions](https://developers.cloudflare.com/workers/authorization/workers/)

## Prepare a deployment with real services

Set `RIBUROM_STAGING_HYPERDRIVE_ID` and run `python deploy/cloudflare/build.py --application-staging` to assemble `riburom-application-staging`. The profile starts with no public URL or scheduler. Set a staging-only `RIBUROM_STAGING_ACCESS_TOKEN` as a Worker secret, then build with both `--application-staging` and `--enable-staging-url` for the protected rehearsal. HTTP Basic authentication uses username `rehearsal` and that secret as the password. Check that anonymous Flask routes and static assets return 401 and that authenticated `/readyz` returns 200 before enabling the scheduler.

Store secrets in Cloudflare and set `SECRET_KEY`, `ADMIN_PASSWORD_HASH`, `PUBLIC_BASE_URL` and the existing Cloudinary settings for the environment. Set the Brevo API key, verified sender and a controlled recipient for the end-to-end staging test. Use the [transfer runbook](../../docs/render-to-cloudflare.md) for the remaining configuration and cutover. Set `OUTBOX_SCHEDULED=false` until ready to run the outbox in that environment. Verify email delivery and retries after web inactivity before handing production delivery over from Render.
