"""Read-only baseline and Cloudflare staging SQL-time profiling.

Compares identical public routes, after one warm-up, from the same Actions
runner. Never sends customer data or any mutating request. Protected staging
statistics are numeric only; they never include SQL text or credentials.
"""
import json
import os
from pathlib import Path
import re
import statistics
import subprocess
import tempfile

TARGETS = (
    ("render", "https://riburomtours.com", False),
    ("cloudflare_staging", "https://riburom-application-staging.dakhroo.workers.dev", True),
)
PATHS = ("/", "/all_tours", "/about")
SAMPLES = 3


def one(url, protected, path, headers):
    args = [
        "curl", "--silent", "--show-error", "--location", "--max-time", "20",
        "--output", os.devnull, "--dump-header", str(headers),
        "--write-out", "%{http_code} %{time_starttransfer} %{time_total}",
    ]
    if protected:
        args.extend(["--user", "rehearsal:" + os.environ["STAGING_ACCESS_PASSWORD"]])
    try:
        result = subprocess.run(args + [url + path], text=True, capture_output=True, timeout=25)
    except subprocess.TimeoutExpired:
        return {"status": "timeout"}
    if result.returncode:
        return {"status": "curl_error", "exit_code": result.returncode}
    try:
        status, ttfb, total = result.stdout.strip().split()
        row = {"status": int(status), "ttfb_ms": round(float(ttfb)*1000),
               "total_ms": round(float(total)*1000)}
    except ValueError:
        return {"status": "invalid_response"}
    raw = headers.read_text(errors="replace")
    timing = re.findall(r"^server-timing:\\s*(.+)$", raw, re.I | re.M)
    if timing:
        for label, value in re.findall(r"(flask|sql);dur=([0-9.]+)", timing[-1]):
            row[label + "_ms"] = round(float(value))
    sql_count = re.findall(r"^x-riburom-staging-sql-count:\\s*([0-9]+)", raw, re.I | re.M)
    if sql_count:
        row["sql_count"] = int(sql_count[-1])
    return row


def summary(rows):
    ok = [r for r in rows if r.get("status") == 200]
    out = {"statuses": [r["status"] for r in rows], "successes": len(ok)}
    for metric in ("ttfb_ms", "total_ms", "flask_ms", "sql_ms", "sql_count"):
        numbers = [r[metric] for r in ok if metric in r]
        if numbers:
            out["median_" + metric] = round(statistics.median(numbers))
    return out


def main():
    results = {}
    with tempfile.TemporaryDirectory(prefix="riburom-profile-") as tmp:
        headers = Path(tmp) / "headers.txt"
        for label, url, protected in TARGETS:
            results[label] = {}
            for path in PATHS:
                one(url, protected, path, headers)  # warm-up excluded
                observations = [one(url, protected, path, headers) for _ in range(SAMPLES)]
                report = summary(observations)
                results[label][path] = report
                print(f"{label} {path}: {report}")
    payload = {
        "method": "Three sequential HTTP GETs after warm-up per page and host, same GitHub runner",
        "caveats": ["Different app platform and region", "Protected staging adds Basic authentication",
                    "No browser rendering or concurrency/load measurement",
                    "SQL duration excludes connection acquisition and Python template rendering",
                    "Public staging has test content and may differ from live content"],
        "results": results,
    }
    destination = Path(os.environ.get("RUNNER_TEMP", "/tmp")) / "riburom-profile.json"
    destination.write_text(json.dumps(payload, indent=2))
    print(f"Profile saved: {destination}")


if __name__ == "__main__":
    main()
