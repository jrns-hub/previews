# Previews

Draft websites Wolfgang Joerns builds for local businesses in Black Mountain, NC, to show the owner before anything goes live. Not indexed by search engines.

## Auto-built previews
`_gen/data/<slug>.json` holds facts from the business's Google listing (photos, reviews, hours). `_gen/generate.py` turns it into `<slug>/index.html`, on GitHub Actions when a data file is pushed, or locally. Hand-built pages have no data file and are never overwritten.
