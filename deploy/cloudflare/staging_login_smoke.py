"""CSRF- and cookie-aware Control Room login check via the verified curl client.

Uses the existing staging HTTP Basic secret and writes no production data.
"""
import os
from pathlib import Path
import re
import subprocess
import tempfile


def fetch(url, *, secret, jar, output, fields=None, follow_redirects=True):
    args = [
        "curl", "--silent", "--show-error", "--max-time", "30",
        "--user", "rehearsal:" + secret, "--user-agent", "curl/8.0",
        "--cookie", str(jar), "--cookie-jar", str(jar),
        "--output", str(output), "--dump-header", str(output.with_suffix(".headers")),
        "--write-out", "%{http_code} %{redirect_url}",
    ]
    if follow_redirects:
        args.append("--location")
    if fields:
        # Flask-WTF checks the same-origin Referer for secure form POSTs.
        # Real browsers send this header; curl does not unless instructed.
        args.extend(["--referer", url, "--header", "Origin: " + os.environ["STAGING_URL"].rstrip("/")])
    for key, value in (fields or {}).items():
        args.extend(["--data-urlencode", key + "=" + value])
    result = subprocess.run(args + [url], capture_output=True, text=True, timeout=35)
    if result.returncode != 0:
        raise AssertionError("Control Room HTTP client failed with curl code " + str(result.returncode))
    # Preserve an empty redirect URL for normal 200 responses.
    code, _, location = result.stdout.partition(" ")
    code, location = code.strip(), location.strip()
    body = output.read_text(encoding="utf-8", errors="replace")
    if code not in (("200",) if follow_redirects else ("302", "303")):
        title = re.search(r"<title>(.*?)</title>", body, re.IGNORECASE | re.DOTALL)
        header_text = output.with_suffix(".headers").read_text(errors="replace")
        error_class = [
            line.partition(":")[2].strip()
            for line in header_text.splitlines()
            if line.lower().startswith("x-riburom-staging-error-class:")
        ]
        raise AssertionError(
            f"Control Room request failed: HTTP {code}; "
            f"page title: {(title.group(1).strip() if title else 'unknown')[:100]}; "
            f"staging exception class: {(error_class[-1] if error_class else 'not available')}"
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
            follow_redirects=False,
        )
        from urllib.parse import urlsplit
        if not urlsplit(location).path.startswith("/workspace"):
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
                "Staging sign-in did not redirect toward workspace; "
                + "redirect path=" + urlsplit(location).path
                + "; known message=" + (", ".join(hints) if hints else "none")
            )
        _, content = fetch(base + "/workspace", secret=secret, jar=jar, output=output)
        if "control room" not in content.lower():
            raise AssertionError("Authenticated workspace did not render Control Room")
    print("Staging Owner login, CSRF and authenticated workspace: PASS")


if __name__ == "__main__":
    main()
