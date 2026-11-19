#!/usr/bin/env python3
"""Add the claim bar to every preview site.

The bar lives in claim/claim.css and claim/claim.js. This script only adds the
two tags to each <slug>/index.html, so changing the offer later is one edit, not
123.

Safe to run any time. Skips files that already have it, so it never doubles up.
Run again after _gen/generate.py rebuilds previews (the template includes it, but
older files will not).

    python claim/install.py
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SNIPPET = (
    '<link rel="stylesheet" href="../claim/claim.css">\n'
    '<script src="../claim/claim.js" defer></script>\n'
)
MARK = "claim/claim.js"


def main() -> None:
    added, done, skipped = 0, 0, []
    for page in sorted(ROOT.glob("*/index.html")):
        if page.parent.name == "claim":
            continue
        html = page.read_text(encoding="utf-8")
        if MARK in html:
            done += 1
            continue
        if "</body>" not in html:
            skipped.append(page.parent.name)
            continue
        page.write_text(html.replace("</body>", SNIPPET + "</body>", 1), encoding="utf-8")
        added += 1

    print(f"added {added}, already had it {done}, skipped {len(skipped)}")
    if skipped:
        print("no </body> tag in: " + ", ".join(skipped[:10]))


if __name__ == "__main__":
    main()
