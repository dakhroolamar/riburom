"""Matched public GET measurements against Render and a protected Worker."""
import base64
from concurrent.futures import ThreadPoolExecutor
import json
from math import ceil
import os
from pathlib import Path
from statistics import median
from time import perf_counter
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


HOSTS = {
    "render": "https://riburomtours.com",
    "cloudflare": {
        "staging": "https://riburom-application-staging.dakhroo.workers.dev",
        "production-candidate": "https://riburom-production.dakhroo.workers.dev",
    }[os.environ.get("RIBUROM_BENCHMARK_PROFILE", "staging")],
}
ROUTES = ("/", "/all_tours", "/about", "/marketplace", "/stories")
SAMPLES = 10


def visit(host, route, bypass=False):
    headers = {"User-Agent": "RI-BUROM-read-only-benchmark/1", "Accept-Encoding": "gzip"}
    if host == "cloudflare":
        auth = "rehearsal:" + os.environ["STAGING_ACCESS_PASSWORD"]
        headers["Authorization"] = "Basic " + base64.b64encode(auth.encode()).decode()
    if bypass:
        headers["Cookie"] = "ri_benchmark=1"
    request = Request(HOSTS[host] + route, headers=headers)
    opener = build_opener(NoRedirect)
    started = perf_counter()
    try:
        with opener.open(request, timeout=25) as response:
            headers_ms = round((perf_counter() - started) * 1000)
            size = len(response.read())
            hit = response.headers.get("X-Riburom-Cache") == "HIT"
            count = response.headers.get("X-Riburom-Staging-SQL-Count")
            return dict(status=response.status, headers_ms=headers_ms,
                        total_ms=round((perf_counter() - started) * 1000), body_bytes=size,
                        cache_hit=hit, sql_count=0 if hit else int(count) if count else None)
    except HTTPError as exc:
        return {"status": exc.code}
    except (URLError, OSError) as exc:
        return {"status": type(exc).__name__}


def summarize(rows):
    ok = [row for row in rows if row["status"] == 200]
    result = dict(samples=len(rows), errors=len(rows)-len(ok), hits=sum(r["cache_hit"] for r in ok))
    for key in ("headers_ms", "total_ms", "body_bytes", "sql_count"):
        values = sorted(r[key] for r in ok if r[key] is not None)
        if values:
            result[key] = dict(median=median(values), p95=values[ceil(.95 * len(values))-1])
    return result


def main():
    output = []
    def record(host, route, kind, rows):
        group = dict(host=host, route=route, kind=kind, summary=summarize(rows))
        print(json.dumps(group), flush=True)
        output.append(dict(**group, rows=rows))

    for route in ROUTES:
        for host in HOSTS:
            record(host, route, "first_observed", [visit(host, route)])
        batches = {host: [] for host in HOSTS}
        for sample in range(SAMPLES):
            for host in (HOSTS if sample % 2 == 0 else reversed(HOSTS)):
                batches[host].append(visit(host, route))
        for host, rows in batches.items():
            record(host, route, "anonymous", rows)
            with ThreadPoolExecutor(max_workers=3) as pool:
                burst = list(pool.map(lambda _: visit(host, route, True), range(3)))
            record(host, route, "three_concurrent_cookie_bypass", burst)
    dest = Path(os.environ["RUNNER_TEMP"]) / "riburom-browser-qa"
    dest.mkdir(exist_ok=True)
    (dest / "http.json").write_text(json.dumps(output, indent=2))
    if any(group["summary"]["errors"] for group in output):
        raise SystemExit("HTTP benchmark recorded errors")


if __name__ == "__main__":
    main()
