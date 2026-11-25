"""Opt-in hosted Brevo OAuth and one-recipient email test (no secrets printed)."""
import os

import requests

STAGING = "https://riburom-application-staging.dakhroo.workers.dev"


def call(path):
    access = os.environ["STAGING_ACCESS_PASSWORD"]
    if not access or len(access) < 16:
        raise RuntimeError("Staging access password is missing")
    response = requests.post(
        STAGING + path, auth=("rehearsal", access), timeout=45,
        headers={"Cache-Control": "no-store", "Accept": "application/json"},
    )
    try:
        data = response.json()
    except ValueError:
        data = {"status": "non_json_response"}
    # Server responses contain only sanitized status/attempt counts.
    print(f"{path}: HTTP {response.status_code}, status={data.get('status')}")
    if data.get("provider_http_status"):
        print("Brevo OAuth HTTP status:", data["provider_http_status"])
    if data.get("names"):
        print("Missing configuration names:", ", ".join(data["names"]))
    if data.get("failure_category"):
        print("Delivery category:", data["failure_category"])
    return response.status_code, data


def main():
    status, info = call("/__staging/brevo-check")
    if status != 200 or info.get("status") != "oauth_authorized":
        raise SystemExit("Brevo OAuth check not accepted; no email sent.")

    status, info = call("/__staging/brevo-send")
    if status != 200 or info.get("status") not in ("sent", "already_sent"):
        raise SystemExit("Brevo staging email was not accepted; inspect the safe statuses.")

    print("Staging notification accepted by Brevo. Verify actual inbox delivery.")


if __name__ == "__main__":
    main()
