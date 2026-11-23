"""Assemble the Worker and tracked Flask sources into an isolated Wrangler project."""

import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess


BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[1]


def copy(source, destination):
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=BASE / "build")
    args = parser.parse_args()
    build = args.output.resolve()
    hyperdrive_id = os.environ.get("RIBUROM_STAGING_HYPERDRIVE_ID")
    if hyperdrive_id and not re.fullmatch(r"[0-9a-f]{32}", hyperdrive_id):
        raise SystemExit("Expected a Cloudflare staging Hyperdrive configuration ID.")
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
    for name in ("worker.py", "worker_runtime.py", "worker_fixture.py", "durable_rate_limits.py"):
        copy(BASE / name, build / "src" / name)
    for name in ("pyproject.toml", "wrangler.jsonc"):
        copy(BASE / name, build / name)
    if hyperdrive_id:
        config_path = build / "wrangler.jsonc"
        config = json.loads(config_path.read_text(encoding="utf-8"))
        config["hyperdrive"] = [{"binding": "HYPERDRIVE", "id": hyperdrive_id}]
        config_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    print(f"Assembled synthetic Worker project at {build}")


if __name__ == "__main__":
    main()
