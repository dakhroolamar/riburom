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

To build from GitHub, connect this Worker in **Settings → Builds**, select the staging branch and set the root directory to `deploy/cloudflare`. Set the build command to `python build.py` and the deploy command to `cd build && uv run pywrangler deploy`. Set `RIBUROM_STAGING_HYPERDRIVE_ID` in the build environment to include the isolated database check. A push to the selected branch updates the synthetic staging Worker. [Workers Builds configuration](https://developers.cloudflare.com/workers/ci-cd/builds/configuration/)

## Prepare a deployment with real services

Save the application configuration under a separate Worker name. Register the SQLite-backed Durable Object for that name, set `RIBUROM_MODE` to `application` and set `RIBUROM_HOST` to the exact hostname that should serve Flask. Bind `HYPERDRIVE` to a cache-disabled configuration with a direct PostgreSQL origin. Test on an isolated, empty Neon database with the current Alembic schema before using the existing production database. Test database access and `/readyz` before enabling the scheduler.

Store secrets in Cloudflare and set `SECRET_KEY`, `ADMIN_PASSWORD_HASH`, `PUBLIC_BASE_URL` and the existing Cloudinary settings for the environment. Set the Brevo API key, verified sender and a controlled recipient for the end-to-end staging test. Use the [transfer runbook](../../docs/render-to-cloudflare.md) for the remaining configuration and cutover. Set `OUTBOX_SCHEDULED=false` until ready to run the outbox in that environment. Verify email delivery and retries after web inactivity before handing production delivery over from Render.
