"""Compare public Render pages with the protected, read-only Cloudflare production mirror.

The two hosts use the same production data. No forms, database writes, customer
records or privileged pages are requested. Only response statuses, sizes and
timing numbers are logged or written to the GitHub Actions artifact.
"""
from collections import Counter
from math import ceil
import json
import os
from pathlib import Path
import statistics
from time import perf_counter
from urllib.parse import urlsplit
from xml.etree import ElementTree

import requests


LIVE = "https://riburomtours.com"
PARALLEL = "https://riburom-parallel-comparison.dakhroo.workers.dev"
STATIC_ROUTES = ("/", "/all_tours", "/about", "/marketplace", "/stories")
REPEATS = 7
HEADERS = {"User-Agent": "RI-BUROM-ReadOnly-Host-Acceptance/1.0"}


def routes_from_sitemap():
    response = requests.get(LIVE + "/sitemap.xml", headers=HEADERS,
                            timeout=25, allow_redirects=False)
    response.raise_for_status()
    urls = [loc.text for loc in ElementTree.fromstring(response.content).findall("{*}url/{*}loc")]
    tour_routes = sorted({
        urlsplit(url).path for url in urls if url
        and urlsplit(url).scheme == "https"
        and urlsplit(url).netloc == urlsplit(LIVE).netloc
        and urlsplit(url).path.startswith("/tours/")
    })
    if len(tour_routes) < 2:
        raise RuntimeError("At least two live tour detail URLs must be listed in the sitemap")
    return (*STATIC_ROUTES, *tour_routes[:2])


def request(session, base, path, password=None):
    started = perf_counter()
    try:
        with session.get(
            base + path,
            auth=("rehearsal", password) if password else None,
            headers=HEADERS, stream=True, allow_redirects=False, timeout=25,
        ) as response:
            ttfb_ms = round(response.elapsed.total_seconds() * 1000)
            size = sum(len(chunk) for chunk in response.iter_content(chunk_size=65536))
            return {
                "status": response.status_code,
                "ttfb_ms": ttfb_ms,
                "total_ms": round((perf_counter() - started) * 1000),
                "bytes": size,
            }
    except requests.RequestException as exc:
        return {"status": "network_error", "error_class": type(exc).__name__}
    finally:
        # Read-only comparison is anonymous except for the Worker Basic gate;
        # do not allow Flask cookies to change samples or cache eligibility.
        session.cookies.clear()


def summarize(rows):
    ok = [row for row in rows if row["status"] == 200]
    result = {
        "samples": len(rows),
        "successes": len(ok),
        "statuses": dict(Counter(str(row["status"]) for row in rows)),
    }
    for metric in ("ttfb_ms", "total_ms", "bytes"):
        values = sorted(row[metric] for row in ok)
        if values:
            result["median_" + metric] = round(statistics.median(values))
            result["p95_" + metric] = values[ceil(0.95 * len(values)) - 1]
    return result


def main():
    password = os.environ.get("PARALLEL_ACCESS_TOKEN", "")
    if len(password) < 16:
        raise RuntimeError("Read-only comparison password is missing or too short")

    routes = routes_from_sitemap()
    targets = (
        ("render", LIVE, None),
        ("cloudflare_production_readonly", PARALLEL, password),
    )
    sessions = {name: requests.Session() for name, _, _ in targets}
    results = {name: {} for name, _, _ in targets}
    try:
        for path in routes:
            for name, origin, auth in targets:
                request(sessions[name], origin, path, auth)  # warm-up, excluded
            observations = {name: [] for name, _, _ in targets}
            for sample in range(REPEATS):
                pair = targets if sample % 2 == 0 else tuple(reversed(targets))
                for name, origin, auth in pair:
                    observations[name].append(request(sessions[name], origin, path, auth))
            for name, _, _ in targets:
                results[name][path] = summarize(observations[name])
                report = results[name][path]
                print(f"{name} {path}: {report['successes']}/{REPEATS} HTTP 200; "
                      f"median TTFB {report.get('median_ttfb_ms', 'N/A')} ms; "
                      f"median total {report.get('median_total_ms', 'N/A')} ms; "
                      f"p95 total {report.get('p95_total_ms', 'N/A')} ms", flush=True)
    finally:
        for session in sessions.values():
            session.close()

    payload = {
        "method": ("One warm-up and seven matched sequential anonymous GETs per route "
                   "and host, alternating host order, same GitHub Actions runner"),
        "data_basis": "Both Render and protected Cloudflare read filtered production Neon public data",
        "limitations": [
            "GitHub Actions geography may not match visitors in India",
            "HTTP timing is not browser LCP, CLS or INP",
            "Small sample: p95 is close to the slowest observed request",
            "HTTP Basic protection adds some overhead to Cloudflare",
            "Cloudflare comparison is read-only and is not a test of editable production",
        ],
        "paths": list(routes),
        "results": results,
    }
    output = Path(os.environ.get("RUNNER_TEMP", "/tmp")) / "riburom-parallel-host-benchmark.json"
    output.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print("Paired performance report saved as a GitHub Actions artifact", flush=True)
    if any(results[name][path]["successes"] < REPEATS for name, _, _ in targets for path in routes):
        print("::warning::Some anonymous comparison requests were unsuccessful; check status counts")


if __name__ == "__main__":
    main()
