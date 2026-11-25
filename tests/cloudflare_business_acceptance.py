"""Exercise browser-facing business workflows on the isolated application Worker only."""
from datetime import date
import io
import os
import re
import traceback
from urllib.parse import urljoin, urlsplit
from zipfile import ZipFile

from bs4 import BeautifulSoup
from PIL import Image
import requests


ORIGIN = "https://riburom-application-staging.dakhroo.workers.dev"


class Visitor:
    def __init__(self):
        self.client = requests.Session()
        self.client.auth = ("rehearsal", os.environ["STAGING_ACCESS_PASSWORD"])
        self.token = None

    def request(self, method, path, expected=200, **kwargs):
        url = urljoin(ORIGIN, path)
        if urlsplit(url).netloc != urlsplit(ORIGIN).netloc or urlsplit(url).scheme != "https":
            raise ValueError("Staging origin required")
        response = self.client.request(method, url, allow_redirects=False, timeout=35, **kwargs)
        if response.status_code != expected:
            # Only numeric status and whitelisted diagnostic exception types;
            # never record response bodies, cookies, or authorization headers.
            error_type = response.headers.get("X-Riburom-Staging-Upload-Error-Class", "unknown")
            cause_type = response.headers.get("X-Riburom-Staging-Upload-Cause-Class", "unknown")
            raise AssertionError(
                f"{method} expected HTTP {expected}, received {response.status_code}; "
                f"upload_error={error_type}; cause={cause_type}"
            )
        return response

    def html(self, path):
        page = BeautifulSoup(self.request("GET", path).content, "html.parser")
        token = page.select_one('input[name="csrf_token"]')
        if token:
            self.token = token.get("value")
        return page

    def post(self, path, fields, expected=302, **kwargs):
        assert self.token, "Expected a browser form CSRF token"
        return self.request("POST", path, expected, data=dict(csrf_token=self.token, **fields),
                            headers={"Referer": ORIGIN + "/", "Origin": ORIGIN}, **kwargs)


def main():
    # The permanent staging-only demo slug and Owner guard against a misbound DB.
    owner = Visitor()
    visitor = Visitor()
    owner.html("/admin/login")
    login = owner.post("/admin/login", dict(username="staging-owner", password=os.environ["STAGING_ACCESS_PASSWORD"]))
    assert urlsplit(login.headers["Location"]).path.startswith("/workspace")
    trips = owner.html("/workspace/control/marketplace")
    assert "STAGING DEMO" in trips.get_text(), "Isolated demonstration tours are missing"
    marker = "Staging QA " + os.environ["GITHUB_RUN_ID"] + "-" + os.environ["GITHUB_RUN_ATTEMPT"]
    failures = []

    def check(name, action):
        try:
            action()
            print(f"{name}: PASS", flush=True)
        except Exception as exc:
            # Never log server bodies, redirect receipts, form values or credentials.
            failures.append(name)
            line = traceback.extract_tb(exc.__traceback__)[-1].lineno
            detail = str(exc) if isinstance(exc, AssertionError) else type(exc).__name__
            print(f"{name}: FAIL ({detail}, line {line})", flush=True)

    def tour():
        owner.html("/add_package")
        result = owner.post("/add_package", dict(title=marker, description="Synthetic unpublished itinerary"))
        path = urlsplit(result.headers["Location"]).path
        assert re.fullmatch(r"/edit_package/\d+", path)
        package_id = path.rsplit("/", 1)[1]
        editor = owner.html(path)
        assert editor.select_one('input[name="title"]')["value"] == marker
        try:
            version = editor.select_one('input[name="package_token"]')["value"]
            assert marker not in visitor.html("/all_tours").get_text()
            owner.post(path, dict(title=marker, description="Revised synthetic itinerary",
                                  published="on", package_token=version))
            listing = visitor.html("/all_tours?staging_qa=1")
            card = next(card for card in listing.select("article") if marker in card.get_text())
            public_path = card.select_one('a[href^="/tours/"]')["href"]
            assert "Revised synthetic itinerary" in visitor.html(public_path).get_text()
        finally:
            owner.post("/delete_package/" + package_id, {})
        visitor.request("GET", public_path, expected=404)

    def draft():
        path = "/workspace/control/website?page=home"
        token = owner.html(path).select_one('input[name="token"]')["value"]
        owner.post("/workspace/control/website/home/draft", dict(token=token, hero_title=marker))
        preview = owner.html(path).select_one('a[href*="/revisions/"][href$="/preview"]')
        assert preview and marker in owner.html(preview["href"]).get_text()
        assert marker not in visitor.html("/").get_text()

    def invoice():
        path = "/workspace/control/invoices"
        owner.html(path)
        result = owner.post(path, dict(customer=marker, issued=date.today().isoformat(), due_date=date.today().isoformat(),
                                       supplier="Staging office", recipient="QA guest", mode="IGST", reverse="No",
                                       item="QA transport", code="", qty="1", rate="100", gst="0"))
        view = urlsplit(result.headers["Location"]).path
        assert re.fullmatch(path + r"/\d+", view)
        assert marker in owner.html(view).get_text()
        data = owner.request("GET", view + "?format=docx").content
        with ZipFile(io.BytesIO(data)) as document:
            assert marker.encode() in document.read("word/document.xml")
            assert "word/header1.xml" in document.namelist()

    def review():
        visitor.html("/")
        visitor.post("/reviews", dict(name=marker, rating="4", comment="Synthetic staging review"), expected=303)
        admin = owner.html("/workspace/control/reviews?status=pending")
        entry = next(row for row in admin.select("article.review-entry") if row.select_one("h2").get_text() == marker)
        path = "/workspace/control/reviews/" + entry["id"].removeprefix("review-")
        owner.post(path, dict(action="approve", expected="pending"))
        try:
            assert marker in visitor.html("/").get_text()
        finally:
            owner.post(path, dict(action="unpublish", expected="published"))
        assert marker not in visitor.html("/").get_text()

    def contact():
        visitor.html("/")
        visitor.post("/send_message", dict(name=marker, email="synthetic@example.invalid", message=marker))
        assert marker in owner.html("/workspace/control/enquiries?q=" + marker).get_text()

    def marketplace():
        listing = visitor.html("/marketplace")
        profile = listing.select_one('a[href^="/marketplace/providers/"]')
        page = visitor.html(profile["href"])
        provider = page.select_one('input[name="provider_id"]')["value"]
        result = visitor.post("/marketplace/inquiries", dict(provider_id=provider, name=marker,
                              email="synthetic@example.invalid", requirements="Synthetic staging request"), expected=303)
        receipt = urlsplit(result.headers["Location"]).path
        assert receipt.startswith("/marketplace/inquiries/success/")
        visitor.html(receipt)
        Visitor().request("GET", receipt, expected=404)
        assert marker in owner.html("/workspace/marketplace/inquiries?q=" + marker).get_text()

    def media():
        owner.html("/workspace/control/media")
        photo = io.BytesIO()
        Image.new("RGB", (48, 48), (32, 67, 49)).save(photo, "PNG")
        result = owner.post("/workspace/media-api/assets", {}, expected=201,
                            files={"image": (marker + ".png", photo.getvalue(), "image/png")})
        src = result.json()["src"]
        parsed = urlsplit(src)
        assert parsed.scheme == "https" and parsed.hostname == "res.cloudinary.com"
        assert "/riburom-cloudflare-staging/" in parsed.path
        # Public CDN delivery uses a fresh HTTP client with no staging credentials.
        response = requests.get(src, timeout=20, allow_redirects=False)
        assert response.status_code == 200 and Image.open(io.BytesIO(response.content)).size == (48, 48)

    for name, action in [("Tour create, edit, publish and delete", tour), ("Website Manager draft/preview", draft),
                         ("Invoice and Word export", invoice), ("Review moderation", review),
                         ("Contact persistence", contact), ("Marketplace enquiry and private receipt", marketplace),
                         ("Staging Cloudinary upload and delivery", media)]:
        check(name, action)
    if failures:
        raise SystemExit("Incomplete workflows: " + ", ".join(failures))


if __name__ == "__main__":
    main()
