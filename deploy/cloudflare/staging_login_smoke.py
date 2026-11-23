"""CSRF- and cookie-aware Control Room login check via the verified curl client.

Uses the existing staging HTTP Basic secret and writes no production data.
"""
import os
from pathlib import Path
import re
import subprocess
import tempfile


def fetch(url, *, secret, jar, output, fields=None):
    args = [
        "curl", "--silent", "--show-error", "--location", "--max-time", "30",
        "--user", "rehearsal:" + secret, "--user-agent", "curl/8.0",
        "--cookie", str(jar), "--cookie-jar", str(jar),
        "--output", str(output), "--write-out", "%{http_code} %{url_effective}",
    ]
    for key, value in (fields or {}).items():
        args.extend(["--data-urlencode", key + "=" + value])
    result = subprocess.run(args + [url], capture_output=True, text=True, timeout=35)
    if result.returncode != 0:
        raise AssertionError("Control Room HTTP client failed with curl code " + str(result.returncode))
    code, location = result.stdout.strip().split(" ", 1)
    body = output.read_text(encoding="utf-8", errors="replace")
    if code != "200":
        title = re.search(r"<title>(.*?)</title>", body, re.IGNORECASE | re.DOTALL)
        raise AssertionError(
            f"Control Room request failed: HTTP {code}; "
            f"page title: {(title.group(1).strip() if title else 'unknown')[:100]}"
        )
    return location, body


def main():
    base = os.environ["STAGING_URL"].rstrip("/")
    secret = os.environ["STAGING_ACCESS_PASSWORD"]
    with tempfile.TemporaryDirectory(prefix="riburom-staging-signin-") as tmp:
        jar = Path(tmp) / "cookies.txt"
        output = Path(tmp) / "response.html"
        _, page = fetch(base + "/admin/login", secret=secret, jar=jar, output=output)
        token = re.search(
            r'<input[^>]+name=["\']csrf_token["\'][^>]+value=["\']([^"\']+)',
            page,
        )
        if not token:
            raise AssertionError("Control Room login form has no CSRF token")
        location, login_body = fetch(
            base + "/admin/login", secret=secret, jar=jar, output=output,
            fields={"username": "staging-owner", "password": secret, "csrf_token": token.group(1)},
        )
        if not location.startswith(base + "/workspace"):
            from urllib.parse import urlsplit
            hints = []
            for marker in (
                "Incorrect username or password.",
                "The form expired or was submitted from an invalid session.",
                "Please log in to access the control room.",
                "Too Many Requests",
            ):
                if marker.lower() in login_body.lower():
                    hints.append(marker)
            raise AssertionError(
                "Staging sign-in did not reach workspace; "
                + "final path=" + urlsplit(location).path
                + "; known message=" + (", ".join(hints) if hints else "none")
            )
        _, content = fetch(base + "/workspace", secret=secret, jar=jar, output=output)
        if "control room" not in content.lower():
            raise AssertionError("Authenticated workspace did not render Control Room")
    print("Staging Owner login, CSRF and authenticated workspace: PASS")


if __name__ == "__main__":
    main()
