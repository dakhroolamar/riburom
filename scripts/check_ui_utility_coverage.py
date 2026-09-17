"""Fail CI when Tailwind-style utilities used by public templates are not shipped.

RI BUROM intentionally keeps a small hand-compiled utility stylesheet rather than a
runtime CSS framework. This guard prevents template/CSS drift from silently breaking
responsive layouts.
"""

from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
CSS_PATH = ROOT / "static" / "css" / "ri-burom-compiled.css"

PUBLIC_TEMPLATES = (
    "templates/_nav.html",
    "templates/_footer.html",
    "templates/index.html",
    "templates/about.html",
    "templates/tours.html",
    "templates/tour_detail.html",
    "templates/marketplace_public.html",
    "templates/marketplace_provider.html",
    "templates/marketplace_inquiry_success.html",
    "templates/errors/403.html",
    "templates/errors/404.html",
    "templates/errors/500.html",
)

CLASS_RE = re.compile(r'class\s*=\s*["\']([^"\']+)["\']')
UTILITY_RE = re.compile(
    r"^(?:"
    r"sm:|md:|lg:|xl:|2xl:|hover:|focus:|focus-visible:|"
    r"bg-|text-|border|rounded|shadow|p-|px-|py-|pt-|pb-|pl-|pr-|"
    r"m-|mx-|my-|mt-|mb-|ml-|mr-|gap-|space-|w-|h-|min-|max-|"
    r"items-|justify-|content-|self-|col-|grid-|overflow-|object-|"
    r"tracking-|leading-|font-|whitespace-|z-|inset-|top-|right-|"
    r"bottom-|left-|aspect-|cursor-|break-|ring-|outline-|opacity-|"
    r"line-clamp|-translate-|translate-|brightness-|invert$|"
    r"block$|inline-block$|inline-flex$|flex$|hidden$|sticky$|"
    r"relative$|absolute$|fixed$|uppercase$|italic$|transition$"
    r")"
)


def utility_tokens(source: str) -> set[str]:
    result: set[str] = set()
    for match in CLASS_RE.finditer(source):
        for token in match.group(1).split():
            if "{{" in token or "{%" in token:
                continue
            if token.startswith(("rb-", "marketplace-")):
                continue
            if UTILITY_RE.match(token):
                result.add(token)
    return result


def main() -> int:
    css = CSS_PATH.read_text(encoding="utf-8").replace("\\", "")
    missing: dict[str, list[str]] = {}

    for relative in PUBLIC_TEMPLATES:
        source = (ROOT / relative).read_text(encoding="utf-8")
        absent = sorted(
            token
            for token in utility_tokens(source)
            if (
                f".{token}{{" not in css
                and f".{token}:" not in css
                and f".{token} " not in css
            )
        )
        if absent:
            missing[relative] = absent

    if missing:
        print("Public UI utility coverage is incomplete:")
        for path, tokens in missing.items():
            print(f"- {path}: {', '.join(tokens)}")
        return 1

    print("Public UI utility coverage: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
