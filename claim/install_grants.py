#!/usr/bin/env python3
"""Put a claim bar on every grant readiness report.

Different offer from the business previews: the report is free and already
written, so the ask is a 20 minute walkthrough, not $150. The bar is configured
per file with window.BT_CLAIM so the org name and the text message are correct.

    python claim/install_grants.py
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GRANTS = ROOT / "grants"
MARK = "window.BT_CLAIM"
H1 = re.compile(r"<h1>(.*?)</h1>", re.S)
TAGS = re.compile(r"<[^>]+>")


def org_name(html: str, fallback: str) -> str:
    m = H1.search(html)
    if not m:
        return fallback
    return TAGS.sub("", m.group(1)).strip() or fallback


def main() -> None:
    added = done = 0
    for page in sorted(GRANTS.glob("*.html")):
        html = page.read_text(encoding="utf-8")
        if MARK in html or "claim/claim.js" in html:
            done += 1
            continue
        if "</body>" not in html:
            continue

        name = org_name(html, page.stem.replace("-", " ").title())
        cfg = {
            "name": name,
            "price": 150,
            "label": "Book 20 minutes",
            "headline": "Your free grant report is ready, {name}. Twenty minutes and I will walk you through it.",
            "sub": "Free. Spark Good closes Nov 30. Never a percentage of a grant.",
            "message": "I would like the 20 minute walkthrough of my grant report. My organization is " + name + ".",
        }
        snippet = (
            '<link rel="stylesheet" href="../claim/claim.css">\n'
            "<script>window.BT_CLAIM=" + json.dumps(cfg) + ";</script>\n"
            '<script src="../claim/claim.js" defer></script>\n'
        )
        page.write_text(html.replace("</body>", snippet + "</body>", 1), encoding="utf-8")
        added += 1

    print(f"grant reports: added {added}, already had it {done}")


if __name__ == "__main__":
    main()
