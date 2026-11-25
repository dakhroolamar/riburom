"""Compare public sitemap URLs against the protected candidate, without following redirects."""
import argparse
import json
import os
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser
from xml.etree import ElementTree

import requests
from bs4 import BeautifulSoup


LIVE = "https://riburomtours.com"
STAGING = "https://riburom-application-staging.dakhroo.workers.dev"
PARALLEL = "https://riburom-parallel-comparison.dakhroo.workers.dev"


def fetch(origin, path, auth=None):
    response = requests.get(origin + path, auth=auth, allow_redirects=False,
                            headers={"User-Agent": "Googlebot"}, timeout=60)
    assert response.status_code == 200, (origin, path, response.status_code)
    return response


def sitemap(origin, canonical_origin, auth):
    xml = ElementTree.fromstring(fetch(origin, "/sitemap.xml", auth).content)
    urls = [loc.text for loc in xml.findall("{*}url/{*}loc")]
    assert urls and len(urls) == len(set(urls)), "Empty sitemap or duplicate URLs"
    paths = set()
    for url in urls:
        parts = urlsplit(url)
        assert parts.scheme == "https" and parts.netloc == urlsplit(canonical_origin).netloc
        assert url == canonical_origin + parts.path and parts.path.startswith("/") and not parts.path.startswith("//")
        paths.add(parts.path)
    return paths


def metadata(origin, path, auth):
    response = fetch(origin, path, auth)
    page = BeautifulSoup(response.content, "html.parser")
    robots = [tag.get("content", "").lower() for tag in page.select('meta[name="robots" i], meta[name="googlebot" i]')]
    header = response.headers.get("X-Robots-Tag", "").lower()
    if origin == LIVE:
        assert all("noindex" not in value and "none" not in value for value in [*robots, header]), path
    else:
        assert "noindex" in header, (path, "missing preview exclusion")
    canonical = page.select_one('link[rel~="canonical"]')["href"]
    expected_origin = STAGING if origin == STAGING else LIVE
    assert canonical == expected_origin + path, (path, "canonical")
    schemas = [json.loads(tag.get_text().replace(expected_origin, LIVE))
               for tag in page.select('script[type="application/ld+json"]')]
    assert schemas and page.title and page.title.get_text(strip=True), path
    verification = {tag["content"] for tag in page.select('meta[name="google-site-verification"][content]')}
    if path == "/":
        assert verification, "Homepage verification tag missing"
    return (page.title.get_text(strip=True), page.select_one('meta[name="description"]')["content"],
            schemas, verification)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate", choices=("staging", "parallel"))
    args = parser.parse_args()
    paths = sitemap(LIVE, LIVE, None)
    robots = RobotFileParser()
    robots.parse(fetch(LIVE, "/robots.txt").text.splitlines())
    assert LIVE + "/sitemap.xml" in (robots.site_maps() or [])
    if args.candidate:
        candidate = STAGING if args.candidate == "staging" else PARALLEL
        auth = ("rehearsal", os.environ["SEO_PREVIEW_PASSWORD"])
        assert paths <= sitemap(candidate, candidate if candidate == STAGING else LIVE, auth)
    errors = []
    for path in sorted(paths):
        try:
            assert robots.can_fetch("Googlebot", LIVE + path)
            live = metadata(LIVE, path, None)
            if args.candidate:
                other = metadata(candidate, path, auth)
                for name, left, right in zip(("title", "description", "structured data", "verification"), live, other):
                    if left != right:
                        errors.append((path, name))
        except (AssertionError, KeyError, TypeError, ValueError, requests.RequestException) as exc:
            errors.append((path, str(exc)))
    print(f"{len(paths)} sitemap URLs checked; discrepancies: {errors}", flush=True)
    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
