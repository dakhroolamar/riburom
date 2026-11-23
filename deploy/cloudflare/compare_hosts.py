"""Small, read-only HTTP response-time comparison; not a user-device benchmark.

Measures both targets from the same GitHub Actions runner (normally US-based).
The staging database contains synthetic records, so results are not like-for-like
production load tests. No production data is read beyond public HTML requests.
"""
import json
import os
from pathlib import Path
import statistics
import subprocess


PATHS = ("/", "/all_tours", "/about", "/marketplace")
TARGETS = (
    ("Render public website", "https://riburomtours.com", False),
    ("Cloudflare staging", "https://riburom-application-staging.dakhroo.workers.dev", True),
)
REPETITIONS = 5


def request(base, path, protected=False):
    args = [
        "curl", "--silent", "--show-error", "--location",
        "--max-time", "16", "--output", os.devnull,
        "--write-out", "%{http_code} %{time_starttransfer} %{time_total}",
    ]
    if protected:
        args.extend(["--user", "rehearsal:" + os.environ["STAGING_ACCESS_PASSWORD"]])
    args.append(base + path)
    try:
        outcome = subprocess.run(args, text=True, capture_output=True, timeout=20, check=False)
        if outcome.returncode:
            return {"status": "network_error", "code": outcome.returncode}
        code, ttfb, total = outcome.stdout.strip().split()
        return {"status": int(code), "ttfb_s": float(ttfb), "total_s": float(total)}
    except (ValueError, subprocess.TimeoutExpired):
        return {"status": "invalid_response"}


def summarize(records):
    successful = [r for r in records if r.get("status") == 200]
    if not successful:
        return {"successful": 0, "samples": len(records), "statuses": [r["status"] for r in records]}
    totals = sorted(r["total_s"] for r in successful)
    ttfbs = sorted(r["ttfb_s"] for r in successful)
    return {
        "successful": len(successful),
        "samples": len(records),
        "statuses": [r["status"] for r in records],
        "median_total_ms": round(statistics.median(totals) * 1000),
        "max_total_ms": round(totals[-1] * 1000),
        "median_ttfb_ms": round(statistics.median(ttfbs) * 1000),
        "max_ttfb_ms": round(ttfbs[-1] * 1000),
    }


def main():
    report = {
        "method": "Five sequential HTTP GETs per public route from a GitHub-hosted runner; not a browser UX test",
        "limitations": [
            "Runner geography may differ from actual visitors",
            "Staging uses isolated synthetic data; Render uses live production content",
            "Small sample, no load testing, no browser rendering or cold-start isolation",
        ],
        "targets": {},
    }
    for label, base, protected in TARGETS:
        report["targets"][label] = {}
        for path in PATHS:
            request(base, path, protected)  # warm-up, excluded
            records = [request(base, path, protected) for _ in range(REPETITIONS)]
            summary = summarize(records)
            report["targets"][label][path] = summary
            print(
                f"{label} {path}: {summary['successful']}/{REPETITIONS} HTTP 200; "
                f"median total {summary.get('median_total_ms', 'N/A')} ms; "
                f"median TTFB {summary.get('median_ttfb_ms', 'N/A')} ms"
            )
    output = Path(os.environ.get("RUNNER_TEMP", "/tmp")) / "riburom-host-comparison.json"
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Machine-readable comparison saved to {output}")


if __name__ == "__main__":
    main()
