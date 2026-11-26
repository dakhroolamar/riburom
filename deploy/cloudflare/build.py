"""Assemble the Worker and tracked Flask sources into an isolated Wrangler project."""

import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess

from outbox_handoff import PRODUCTION_CANDIDATE_HOST, PRODUCTION_HOST


BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[1]


def copy(source, destination):
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=BASE / "build")
    profiles = parser.add_mutually_exclusive_group()
    profiles.add_argument(
        "--application-staging", action="store_true",
        help="Build the separate application Worker with public routes and email scheduling disabled.",
    )
    parser.add_argument(
        "--enable-staging-url", action="store_true",
        help="Enable the application staging URL behind its required access secret.",
    )
    profiles.add_argument(
        "--parallel-comparison", action="store_true",
        help="Build a separate read-only production-data comparison Worker.",
    )
    profiles.add_argument(
        "--production-candidate", action="store_true",
        help="Build the protected production Worker, without custom domains or scheduled mail.",
    )
    profiles.add_argument(
        "--production-live", action="store_true",
        help="Assemble the public custom-domain deployment, with scheduled mail disabled.",
    )
    parser.add_argument(
        "--enable-live-outbox", action="store_true",
        help="Preserve the approved production notification handoff (live profile only).",
    )
    args = parser.parse_args()
    if args.enable_live_outbox and not args.production_live:
        parser.error("--enable-live-outbox requires --production-live")
    build = args.output.resolve()
    if args.enable_staging_url and not args.application_staging:
        raise SystemExit("Only the application staging profile supports --enable-staging-url.")
    stage_hyperdrive = os.environ.get("RIBUROM_STAGING_HYPERDRIVE_ID")
    prod_hyperdrive = os.environ.get("RIBUROM_PARALLEL_HYPERDRIVE_ID")
    hyperdrive_id = prod_hyperdrive if args.parallel_comparison else stage_hyperdrive
    if args.production_candidate or args.production_live:
        hyperdrive_id = os.environ.get("RIBUROM_PRODUCTION_HYPERDRIVE_ID")
        if not hyperdrive_id or hyperdrive_id in (stage_hyperdrive, prod_hyperdrive):
            raise SystemExit("Production requires its dedicated writable Hyperdrive binding.")
    if hyperdrive_id and not re.fullmatch(r"[0-9a-f]{32}", hyperdrive_id):
        raise SystemExit("Expected a 32-hex Cloudflare Hyperdrive configuration ID.")
    if args.application_staging and not stage_hyperdrive:
        raise SystemExit("Application staging requires the isolated staging Hyperdrive.")
    if args.parallel_comparison and not prod_hyperdrive:
        raise SystemExit("Parallel comparison requires a distinct production-readonly Hyperdrive.")
    if args.parallel_comparison and stage_hyperdrive and stage_hyperdrive == prod_hyperdrive:
        raise SystemExit("Production comparison may not reuse the staging Hyperdrive binding.")
    if build.exists() and any(build.iterdir()):
        raise SystemExit(f"Build directory must be empty: {build}")
    tracked = subprocess.check_output(
        ["git", "ls-files", "-z", "--", "*.py", "templates", "static"], cwd=ROOT
    ).decode().split("\0")
    for name in filter(None, tracked):
        source = ROOT / name
        if name.startswith("static/"):
            copy(source, build / "public" / name)
        elif name.startswith("templates/") or ("/" not in name and name.endswith(".py")):
            copy(source, build / "src" / name)
    for name in ("sw.js", "robots.txt", "control-room/favicon.ico", "control-room/ri-burom-mark.png"):
        copy(ROOT / "static" / name, build / "src" / "static" / name)
    for name in ("worker.py", "worker_runtime.py", "worker_fixture.py", "durable_rate_limits.py", "staging_setup.py", "outbox_handoff.py", "staging_brevo_test.py", "production_brevo_probe.py"):
        copy(BASE / name, build / "src" / name)
    for name in ("pyproject.toml", "wrangler.jsonc"):
        copy(BASE / name, build / name)
    config_path = build / "wrangler.jsonc"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    if hyperdrive_id:
        config["hyperdrive"] = [{"binding": "HYPERDRIVE", "id": hyperdrive_id}]
    if args.application_staging:
        # Keep dashboard-managed staging Brevo sender/recipient vars on CI deploy.
        # Secrets remain encrypted and managed separately in Cloudflare.
        config["keep_vars"] = True
        config.update(
            name="riburom-application-staging",
            workers_dev=args.enable_staging_url,
            assets={"directory": "./public", "binding": "ASSETS", "run_worker_first": True},
            vars={
                "RIBUROM_MODE": "application",
                "RIBUROM_HOST": "riburom-application-staging.dakhroo.workers.dev",
                # New staging-only object: first instantiation hints Singapore
                # proximity, where the separate Neon project is located.
                "RIBUROM_DO_NAME": "web-apac-se-staging-v1",
                "RIBUROM_DO_LOCATION": "apac-se",
                "RIBUROM_PUBLIC_CACHE": "true",
                "RIBUROM_STAGING_ACCESS_REQUIRED": "true",
                "PUBLIC_BASE_URL": "https://riburom-application-staging.dakhroo.workers.dev",
                "CLOUDINARY_STAGING_FOLDER": "riburom-cloudflare-staging",
                "OUTBOX_SCHEDULED": "false",
            },
            triggers={"crons": []},
        )
    if args.parallel_comparison:
        config.update(
            name="riburom-parallel-comparison",
            workers_dev=True,
            assets={"directory": "./public", "binding": "ASSETS", "run_worker_first": True},
            vars={
                "RIBUROM_MODE": "application",
                "RIBUROM_HOST": "riburom-parallel-comparison.dakhroo.workers.dev",
                "PUBLIC_BASE_URL": "https://riburomtours.com",
                "RIBUROM_STAGING_ACCESS_REQUIRED": "true",
                "RIBUROM_READ_ONLY": "true",
                "RIBUROM_DO_NAME": "web-apac-se-parallel-v1",
                "RIBUROM_DO_LOCATION": "apac-se",
                "OUTBOX_SCHEDULED": "false",
            },
            triggers={"crons": []},
        )
    if args.production_candidate or args.production_live:
        config.update(
            name="riburom-production",
            workers_dev=args.production_candidate,
            keep_vars=True,
            assets={"directory": "./public", "binding": "ASSETS", "run_worker_first": True},
            vars={
                "RIBUROM_MODE": "application",
                "RIBUROM_HOST": PRODUCTION_HOST if args.production_live else PRODUCTION_CANDIDATE_HOST,
                "PUBLIC_BASE_URL": f"https://{PRODUCTION_HOST}",
                "RIBUROM_DO_NAME": "web-production-v1",
                "RIBUROM_DO_LOCATION": "apac-se",
                "RIBUROM_PUBLIC_CACHE": "true",
                "RIBUROM_STAGING_ACCESS_REQUIRED": "false" if args.production_live else "true",
                "RIBUROM_LIVE_OUTBOX_APPROVED": "false",
                "OUTBOX_SCHEDULED": "false",
            },
            triggers={"crons": []},
        )
    if args.production_live:
        config["vars"]["RIBUROM_READ_ONLY"] = "false"
        config["observability"] = {"enabled": True, "logs": {"enabled": True, "invocation_logs": True}}
        if args.enable_live_outbox:
            config["vars"]["OUTBOX_SCHEDULED"] = "true"
            config["vars"]["RIBUROM_LIVE_OUTBOX_APPROVED"] = "true"
            config["triggers"] = {"crons": ["*/5 * * * *"]}
        config["routes"] = [
            {"pattern": hostname, "custom_domain": True}
            for hostname in (PRODUCTION_HOST, f"www.{PRODUCTION_HOST}")
        ]
    config_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    print(f"Assembled {config['name']} at {build}")


if __name__ == "__main__":
    main()
