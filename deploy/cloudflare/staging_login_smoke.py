"""Read-only Control Room sign-in smoke test for isolated Cloudflare staging."""
import base64
from http.cookiejar import CookieJar
import os
import re
from urllib.parse import urlencode
from urllib.request import HTTPCookieProcessor, Request, build_opener


def main():
    base = os.environ["STAGING_URL"].rstrip("/")
    secret = os.environ["STAGING_ACCESS_PASSWORD"]
    basic = base64.b64encode(("rehearsal:" + secret).encode()).decode("ascii")
    headers = {"Authorization": "Basic " + basic}
    opener = build_opener(HTTPCookieProcessor(CookieJar()))

    with opener.open(Request(base + "/admin/login", headers=headers), timeout=30) as response:
        page = response.read().decode("utf-8", errors="replace")
        assert response.status == 200, "Login page must return 200"
    match = re.search(
        r'<input[^>]+name=["\']csrf_token["\'][^>]+value=["\']([^"\']+)', page
    )
    if not match:
        raise AssertionError("Staging login page did not contain a CSRF field")

    body = urlencode({
        "username": "staging-owner",
        "password": secret,
        "csrf_token": match.group(1),
    }).encode("utf-8")
    with opener.open(Request(
        base + "/admin/login", data=body,
        headers={**headers, "Content-Type": "application/x-www-form-urlencoded"},
    ), timeout=30) as response:
        final_url = response.geturl()
        response.read()
        if response.status != 200 or not final_url.startswith(base + "/workspace"):
            raise AssertionError("Staging Owner login did not redirect to workspace")

    with opener.open(Request(base + "/workspace", headers=headers), timeout=30) as response:
        body = response.read().decode("utf-8", errors="replace").lower()
        if response.status != 200 or "control room" not in body:
            raise AssertionError("Staging Owner cannot view the Control Room")
    print("Authenticated staging Owner sign-in and Control Room access: PASS")


if __name__ == "__main__":
    main()
