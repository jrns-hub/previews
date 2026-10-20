"""Build preview sites from _gen/data/<slug>.json into <slug>/index.html.

Runs on GitHub Actions (free for this public repo) or locally:
    python _gen/generate.py                 # every data file without a page yet
    python _gen/generate.py slug1 slug2     # just these (rebuilds them)
If GROQ_API_KEY is set, Groq's free tier writes the headline and short copy from the facts in the data file.
Without it, plain fact-based copy is used. Pages that were built by hand have no data file and are never touched.
Stdlib only.
"""
import html, json, os, re, sys, time, urllib.error, urllib.request
from pathlib import Path
from string import Template

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "_gen" / "data"
TPL = Template((ROOT / "_gen" / "template.html").read_text(encoding="utf-8"))

F = "https://fonts.googleapis.com/css2?family="
# Five looks, picked by kind of business. Contrast of ink and accent text on bg checked at 4.5:1 or better.
WORLDS = {
    "counter": dict(note="a busy counter: kraft paper, chalkboard green, tomato red.",
                    fonts=F + "Bagel+Fat+One&family=Figtree:wght@400;600;800&display=swap",
                    v="--bg:#fbf3e6;--card:#fffaf2;--ink:#2a1a10;--soft:#5e4a3b;--line:#ead8bf;--acc:#c2410c;--acc-text:#b23a0a;--on-acc:#fff;--link:#9a3412;--band:#1f3a2e;--on-band:#f4efe4;--frame:#1f3a2e;--frame-pad:14px;--r-frame:22px;--r-img:16px;--r-btn:999px;--display:'Bagel Fat One',system-ui,sans-serif;--body:'Figtree',system-ui,sans-serif;--dw:400;--dt:0;--dcase:none"),
    "studio": dict(note="a calm studio: linen, clay, and a deep plum.",
                   fonts=F + "Young+Serif&family=Albert+Sans:wght@400;600;700&display=swap",
                   v="--bg:#f6f1ec;--card:#fffdfa;--ink:#24171f;--soft:#5d4c55;--line:#e4d8d0;--acc:#6b2d5c;--acc-text:#6b2d5c;--on-acc:#fff;--link:#6b2d5c;--band:#3a2234;--on-band:#f6eef2;--frame:#e9ddd3;--frame-pad:12px;--r-frame:200px 200px 18px 18px;--r-img:14px;--r-btn:999px;--display:'Young Serif',Georgia,serif;--body:'Albert Sans',system-ui,sans-serif;--dw:400;--dt:-.01em;--dcase:none"),
    "cabinet": dict(note="a downtown shop window: cream card stock, slate, brass.",
                    fonts=F + "Gloock&family=Instrument+Sans:wght@400;600;700&display=swap",
                    v="--bg:#f4f0e8;--card:#fffdf8;--ink:#1d1c1a;--soft:#55524c;--line:#ddd6c9;--acc:#1d6e63;--acc-text:#1d6e63;--on-acc:#fff;--link:#1d6e63;--band:#22262a;--on-band:#eef0f1;--frame:#22262a;--frame-pad:14px;--r-frame:6px;--r-img:6px;--r-btn:999px;--display:'Gloock',Georgia,serif;--body:'Instrument Sans',system-ui,sans-serif;--dw:400;--dt:-.01em;--dcase:none"),
    "workshop": dict(note="a working garage: concrete, safety yellow, black.",
                     fonts=F + "Archivo:wdth,wght@75..125,700..900&family=Hanken+Grotesk:wght@400;600;700&display=swap",
                     v="--bg:#f3f3f1;--card:#ffffff;--ink:#141618;--soft:#4f555c;--line:#dcdedf;--acc:#f2c200;--acc-text:#141618;--on-acc:#141618;--link:#1f4fa8;--band:#141618;--on-band:#f3f3f1;--frame:#141618;--frame-pad:10px;--r-frame:4px;--r-img:4px;--r-btn:4px;--display:'Archivo',system-ui,sans-serif;--body:'Hanken Grotesk',system-ui,sans-serif;--dw:900;--dt:-.01em;--dcase:uppercase"),
    "commons": dict(note="a community hall: whitewashed wood, forest green, warm light.",
                    fonts=F + "Newsreader:opsz,wght@6..72,600&family=Atkinson+Hyperlegible:wght@400;700&display=swap",
                    v="--bg:#f5f4ee;--card:#ffffff;--ink:#1b2620;--soft:#4c5a52;--line:#dde2da;--acc:#2f6b4f;--acc-text:#2f6b4f;--on-acc:#fff;--link:#2f6b4f;--band:#20372b;--on-band:#eef3ee;--frame:#dfe7dc;--frame-pad:12px;--r-frame:14px;--r-img:12px;--r-btn:10px;--display:'Newsreader',Georgia,serif;--body:'Atkinson Hyperlegible',system-ui,sans-serif;--dw:600;--dt:-.01em;--dcase:none"),
}
WORLD_FOR = {"food": "counter", "beauty": "studio", "wellness": "studio", "pets": "studio", "retail": "cabinet", "art": "cabinet",
             "auto": "workshop", "trades": "workshop", "church": "commons", "nonprofit": "commons", "other": "cabinet"}
BANNED = re.compile(r"nestled|elevate|unleash|discover the|look no further|your one-stop|in the heart of|hidden gem|"
                    r"since \d{4}|family[- ]owned|award|best in|#1|guarantee", re.I)

e = lambda s: html.escape(str(s or ""), quote=True)


def clean(s):
    s = re.sub(r"\s*[—–]\s*", ", ", str(s or "")).replace(" ,", ",")
    return re.sub(r"\s+", " ", s).strip()


def short_review(t, limit=230):
    sents = re.split(r"(?<=[.!?])\s+", t.strip())
    out = ""
    for s in sents:
        if len(out) + len(s) > limit:
            break
        out = (out + " " + s).strip()
    return out or t[:limit].rsplit(" ", 1)[0] + "…"


def groq_copy(d):
    key = os.environ.get("GROQ_API_KEY")
    if not key:
        return None
    facts = {k: d.get(k) for k in ("name", "cat", "street", "town", "hours", "rating", "desc", "kind")}
    facts["reviews"] = [r["t"][:400] for r in d.get("reviews", [])[:8]]
    prompt = ("You are a sharp local copywriter writing the homepage for a real small business. Use ONLY the facts below. Never invent services, "
              "products, prices, years, awards or claims. Owner or staff first names may be used only if a review names them.\n"
              "Return JSON with keys:\n"
              "headline: 3 to 9 words, sentence case, built on one specific thing customers love in the reviews. Do not include the business name or the town. "
              "Good: 'Pick a stone. Leave wearing it today.' 'Coffee by day. Cocktails by night.' 'Hot, fresh, 100% vegan donuts.' "
              "Bad: 'Your local salon in Black Mountain', 'Welcome to ...', 'Quality service you can trust'.\n"
              "accent: one word or short phrase copied exactly from the headline to color.\n"
              "sub: 1 or 2 short sentences: what the place is and the reason people keep coming back, drawn from the reviews. No street address.\n"
              "offer_h: 2 to 5 word section title, sentence case.\n"
              "items: 2 to 5 objects {name, line, evidence}. Each is something customers get here. evidence must be a short phrase copied word for word "
              "from a review or the description that proves it. Skip anything you cannot prove.\n"
              "visit_h: 2 to 5 words, sentence case.\n"
              "No em dashes, no exclamation marks, no words like nestled, elevate, hidden gem, one-stop.\n\nFACTS:\n"
              + json.dumps(facts, ensure_ascii=False))
    for model in os.environ.get("GEN_MODELS", "openai/gpt-oss-120b,openai/gpt-oss-120b,openai/gpt-oss-20b,openai/gpt-oss-120b").split(","):
        body = json.dumps({"model": model, "messages": [{"role": "user", "content": prompt}],
                           "response_format": {"type": "json_object"}, "temperature": 0.6}).encode()
        req = urllib.request.Request("https://api.groq.com/openai/v1/chat/completions", body,
                                     {"Authorization": f"Bearer {key}", "Content-Type": "application/json", "User-Agent": "previews-gen/1.0"})
        try:
            out = json.loads(json.loads(urllib.request.urlopen(req, timeout=60).read())["choices"][0]["message"]["content"])
        except urllib.error.HTTPError as ex:
            if ex.code in (401, 403):
                sys.exit("Groq rejected the key. Fix the GROQ_API_KEY secret; nothing was built with plain copy.")
            wait = float(ex.headers.get("retry-after") or 20) if ex.code == 429 else 3
            print(f"  groq {model} {ex.code}, waiting {wait:.0f}s")
            time.sleep(min(wait, 90))
            continue
        except Exception as ex:
            if "401" in str(ex) or "403" in str(ex):
                sys.exit("Groq rejected the key (401). Fix the GROQ_API_KEY secret; nothing was built with plain copy.")
            print("  groq", model, "failed:", str(ex)[:120])
            continue
        text = json.dumps(out)
        if out.get("headline") and out.get("sub") and not BANNED.search(text) and d["name"].lower() not in out["headline"].lower():
            src = " ".join([d.get("desc", ""), d.get("cat", "")] + [r["t"] for r in d.get("reviews", [])]).lower()
            out["items"] = [i for i in out.get("items") or [] if i.get("evidence") and str(i["evidence"]).lower().strip(" .") in src]
            return out
        print("  groq", model, "copy rejected, trying next")
    return None


def plain_copy(d):
    g, n = d["group"], d["name"]
    head = {"food": "Good food, right here in " + d["town"], "beauty": "Look good, feel good, close to home",
            "wellness": "Feel better, close to home", "pets": "Good care for your pets", "retail": "Come see what's on the shelves",
            "art": "Made and found here in " + d["town"], "auto": "Honest work on your car", "trades": "Local work done right",
            "church": "Everyone is welcome here", "nonprofit": "Neighbors helping neighbors", "other": n + " in " + d["town"]}[g]
    return {"headline": head, "accent": "", "sub": f"{d['cat']} at {d['street']}, {d['town']}, NC.", "offer_h": "", "items": [],
            "visit_h": "Come by" if d["kind"] == "business" else "Visit us"}


FORMJS = "<script>document.querySelectorAll('.ask form').forEach(function(f){f.addEventListener('submit',function(e){e.preventDefault();f.classList.add('sent')})})</script>"
ASK_NAV = {"nonprofit": "Volunteer", "church": "Visit us"}


def ask_label(d):
    return ASK_NAV.get(d["kind"]) or {"beauty": "Book", "wellness": "Book", "pets": "Book", "auto": "Quote", "trades": "Quote", "food": "Order"}.get(d["group"], "Updates")


def ask_block(d, items, days):
    """The service being pitched, shown working: volunteer sign-up, visit planning, booking, quote, order. Preview forms send nothing."""
    g, k = d["group"], d["kind"]
    names = [clean(i["name"]) for i in items][:6]
    opts = "".join(f"<option>{e(x)}</option>" for x in names) or "<option>Tell us what you need</option>"
    who = '<div class="row2"><label>Your name<input autocomplete="name" required></label><label>Phone<input type="tel" autocomplete="tel"></label></div>'
    note = ('<p class="note">Preview: when this goes live, every request reaches you as a text and an email.</p>'
            '<p class="done">Thanks! This is a preview, so nothing was sent.</p>')
    extra = ""
    if k == "nonprofit":
        h, sub = "Volunteer with us", "Pick when you can help. We will reach out with a first shift."
        form = (who + '<label>Email<input type="email" autocomplete="email"></label><div class="chips">'
                + "".join(f'<label><input type="checkbox"> {x}</label>' for x in ["Weekday mornings", "Weekday afternoons", "Weekends", "Events", "Behind the scenes"])
                + '</div><button class="btn btn-main" type="submit">Sign me up</button>')
        extra = '<p><a class="btn btn-line" href="#ask">Give online</a></p>'
    elif k == "church":
        h, sub = "Join us this week", "New here? Tell us you are coming and someone will say hello at the door."
        times = "".join(f"<li>{e(x)}</li>" for x in days if "Closed" not in x)
        extra = (f'<ul class="times">{times}</ul>' if times else "") + '<p><a class="btn btn-line" href="#ask">Give online</a></p>'
        form = ('<label>Your name<input autocomplete="name" required></label><label>Email for the weekly note<input type="email" autocomplete="email"></label>'
                '<label>How many are coming<select><option>Just me</option><option>2</option><option>3 to 4</option><option>5 or more</option></select></label>'
                '<button class="btn btn-main" type="submit">Plan my visit</button>')
    elif g in ("beauty", "wellness", "pets"):
        h, sub = "Book a visit", "Pick a service and a time. You get a text to confirm."
        form = ('<label>What would you like done?<input placeholder="Cut, color, trim, a first visit..."></label><div class="row2"><label>Day<input type="date"></label>'
                '<label>Time<select><option>Morning</option><option>Midday</option><option>Afternoon</option></select></label></div>'
                + who + '<button class="btn btn-main" type="submit">Request this time</button>')
    elif g in ("auto", "trades"):
        h, sub = "Get a quote", "Tell us what is going on. Add a photo if you have one, and we will text you a price."
        form = ('<label>What do you need?<textarea rows="3" placeholder="Year, make and model, and what is happening"></textarea></label>'
                '<label>Photo (optional)<input type="file" accept="image/*"></label>' + who
                + '<button class="btn btn-main" type="submit">Send for a quote</button>')
    elif g == "food":
        h, sub = "Order ahead", "Send your order here and it will be ready when you walk in."
        form = ('<label>What would you like?<textarea rows="2" placeholder="Your order"></textarea></label>'
                '<div class="row2"><label>Your name<input autocomplete="name" required></label><label>Pickup time<input type="time"></label></div>'
                '<button class="btn btn-main" type="submit">Send my order</button>')
    else:
        h, sub = "Hear about new arrivals", "Get a text when something new comes in. One message a week at most."
        form = ('<div class="row2"><label>Your name<input autocomplete="name"></label><label>Phone or email<input required></label></div>'
                + '<label>What are you looking for?<input placeholder="Anything in particular"></label>'
                + '<button class="btn btn-main" type="submit">Keep me posted</button>')
    return (f'<section class="ask" id="ask"><div class="wrap"><div><h2>{e(h)}</h2><p>{e(sub)}</p>{extra}</div>'
            f'<form novalidate>{form}{note}</form></div></section>')


def build(d):
    world = WORLDS[WORLD_FOR.get(d["group"], "cabinet")]
    c = groq_copy(d)
    if c is None and os.environ.get("GROQ_API_KEY"):
        return None
    c = c or plain_copy(d)
    c = {k: (clean(v) if isinstance(v, str) else v) for k, v in c.items()}
    name, phone = d["name"], d.get("phone", "")
    tel = re.sub(r"[^\d]", "", phone)
    dest = "https://www.google.com/maps/dir/?api=1&destination=" + urllib.request.quote(f"{name}, {d['addr']}")
    photos = d.get("photos", [])
    img = lambda u, w, h, alt, lazy=True: (f'<img src="{e(u)}=w{w}-h{h}-p-k-no" alt="{e(alt)}" width="{w}" height="{h}"'
                                           + (' loading="lazy"' if lazy else "") + ">")

    head = e(c["headline"])
    if c.get("accent") and c["accent"] in c["headline"]:
        head = head.replace(e(c["accent"]), f"<em>{e(c['accent'])}</em>", 1)
    actions = (f'<a class="btn btn-main" href="tel:+1{tel}">Call {e(phone)}</a>' if tel else "") + \
              f'<a class="btn btn-line" href="{e(dest)}">Get directions</a>'
    dock = (f'<a class="btn btn-main" href="tel:+1{tel}">Call</a>' if tel else "") + f'<a class="btn btn-line" href="{e(dest)}">Directions</a>'
    m = re.match(r"\s*(\d\.\d)\s*\(([\d,]+)\)", d.get("rating", ""))
    stars = f'<div class="stars"><b>{m.group(1)} on Google</b> from {m.group(2)} reviews</div>' if m else ""
    badge = (f"{m.group(1)} stars<small>{m.group(2)} Google reviews</small>" if m else f"{e(d['street'])}<small>{e(d['town'])}, NC</small>")

    days = [x.strip() for x in (d.get("hours") or "").split(";") if x.strip()]
    today = ""
    if days:
        today = ('<section class="today" aria-label="Hours"><div class="wrap"><span class="now" id="now">Hours</span><ul class="days">'
                 + "".join(f"<li>{e(x)}</li>" for x in days) + "</ul></div></section>")
    items = [i for i in (c.get("items") or []) if i.get("name")][:5]
    offer = ""
    if items:
        offer = (f'<section class="offer" id="offer"><div class="wrap"><div><h2>{e(c.get("offer_h") or "What you will find")}</h2>'
                 f'<p>{e(c["sub"])}</p></div><ul class="list">'
                 + "".join(f'<li><b>{e(clean(i["name"]))}</b><span>{e(clean(i.get("line", "")))}</span></li>' for i in items) + "</ul></div></section>")
    gallery = ""
    if len(photos) >= 4:
        gallery = ('<section class="gallery" aria-label="Photos"><div class="wrap grid">'
                   + "".join(img(u, 900 if i == 0 else 500, 900 if i == 0 else 500, f"Photo of {name}") for i, u in enumerate(photos[1:6])) + "</div></section>")
    revs = [r for r in d.get("reviews", []) if r.get("s", 5) >= 4][:6]
    reviews = ""
    if revs:
        title = f"{m.group(1)} stars, {m.group(2)} reviews" if m else "What people say"
        reviews = (f'<section class="reviews" id="reviews"><div class="wrap"><h2>{e(title)}</h2><div class="rv">'
                   + "".join(f"<figure><blockquote>“{e(short_review(r['t']))}”</blockquote><figcaption>{e(r['a'])}</figcaption></figure>" for r in revs)
                   + "</div></div></section>")
    dl = f"<dt>Where</dt><dd>{e(d['addr'])}</dd>"
    if days:
        dl += f"<dt>Hours</dt><dd>{'<br>'.join(e(x) for x in days)}</dd>"
    if tel:
        dl += f'<dt>Call</dt><dd><a href="tel:+1{tel}">{e(phone)}</a></dd>'
    for s in d.get("social", []):
        dl += f'<dt>Follow</dt><dd><a href="{e(s)}">{"Instagram" if "instagram" in s else "Facebook"}</a></dd>'
    nav = "".join(f'<a href="#{a}">{t}</a>' for a, t, ok in [("offer", "What we do", items), ("ask", ask_label(d), True), ("reviews", "Reviews", revs), ("visit", "Visit", True)] if ok)
    script = ""
    if days:
        script = ("<script>(function(){var d=new Date().toLocaleDateString('en-US',{weekday:'short',timeZone:'America/New_York'});"
                  "var li=[].slice.call(document.querySelectorAll('.days li')).find(function(x){return x.textContent.indexOf(d)===0});"
                  "if(li){document.getElementById('now').textContent='Today: '+li.textContent.slice(4);li.style.fontWeight='800'}})();</script>")
    return TPL.substitute(
        title=e(f"{name} · {d['cat']} in {d['town']}"), meta=e(c["sub"]), fonts=e(world["fonts"]), world_note=world["note"], vars=world["v"],
        name=e(name), nav=nav, headline=head, sub=e(c["sub"]), actions=actions, stars=stars,
        hero_img=img(photos[0], 900, 1100, f"{name}, {d['street']}", lazy=False) if photos else f'<div class="plate"><b>{e(name)}</b><span>{e(d["street"])}, {e(d["town"])}</span><small>Your own photos go here. We take them on a free photo walk.</small></div>',
        badge=badge, today=today, offer=offer, ask=ask_block(d, items, days), gallery=gallery, reviews=reviews,
        visit_h=e(c.get("visit_h") or "Come by"), visit_dl=dl,
        visit_img=img(photos[-1], 900, 675, f"{name} in {d['town']}") if len(photos) > 1 else "", dock=dock, script=script + FORMJS)


def status_page():
    """status.html: one progress bar over every lead, plus where each one stands. Rebuilt on every run."""
    tf = ROOT / "_gen" / "targets.json"
    if not tf.exists():
        return
    ts = sorted(json.loads(tf.read_text(encoding="utf-8")), key=lambda t: -t.get("score", 0))
    rows, n_built = [], 0
    for t in ts:
        slug = t.get("hand") or t["slug"]
        built = (ROOT / slug / "index.html").exists()
        queued = (DATA / f"{t['slug']}.json").exists()
        n_built += built
        state = ("built", "Preview ready") if built else ("queued", "Queued for the next build") if queued else ("missing", "Not on Google Maps yet")
        name = f'<a href="{e(slug)}/">{e(t["name"])}</a>' if built else e(t["name"])
        rows.append(f'<tr class="{state[0]}"><td>{name}</td><td>{e(t["kind"])}</td><td>{"yes" if t.get("walk") else ""}</td><td>{state[1]}</td></tr>')
    pct = round(100 * n_built / max(1, len(ts)))
    page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex,nofollow"><title>Preview progress</title><style>
:root{{--bg:#f5f4ee;--card:#fff;--ink:#1b2620;--soft:#4c5a52;--line:#dde2da;--acc:#2f6b4f;--warn:#9a5b00}}
@media (prefers-color-scheme:dark){{:root{{--bg:#141916;--card:#1d2420;--ink:#e6ebe7;--soft:#9ba69f;--line:#323b36;--acc:#72c39a;--warn:#e2b45b}}}}
body{{margin:0;background:var(--bg);color:var(--ink);font:16px/1.5 system-ui,sans-serif}}main{{max-width:900px;margin:0 auto;padding:20px 16px 60px}}
h1{{margin:.2em 0}}.bar{{height:22px;background:var(--line);border-radius:99px;overflow:hidden;margin:12px 0 6px}}.bar i{{display:block;height:100%;width:{pct}%;background:var(--acc)}}
table{{width:100%;border-collapse:collapse;margin-top:18px;background:var(--card)}}td,th{{text-align:left;padding:8px 10px;border-bottom:1px solid var(--line);font-size:.95rem}}
tr.queued td:last-child{{color:var(--warn)}}tr.missing td:last-child{{color:var(--soft)}}a{{color:var(--acc)}}</style></head><body><main>
<h1>Preview sites: {n_built} of {len(ts)} built</h1><div class="bar" role="progressbar" aria-valuenow="{pct}" aria-valuemin="0" aria-valuemax="100"><i></i></div>
<p>{pct}% done. New ones build every morning at 8. Sorted by call priority.</p>
<table><thead><tr><th>Lead</th><th>Kind</th><th>Walkable</th><th>Status</th></tr></thead><tbody>{"".join(rows)}</tbody></table></main></body></html>"""
    (ROOT / "status.html").write_text(page, encoding="utf-8")
    print(f"status: {n_built}/{len(ts)} built")


def main(args):
    limit = None
    if args[:1] == ["--limit"]:
        limit, args = int(args[1]), args[2:]
    files = [DATA / f"{s}.json" for s in args] if args else sorted(DATA.glob("*.json"), key=lambda f: -json.loads(f.read_text(encoding="utf-8")).get("score", 0))
    built = 0
    for f in files:
        if limit is not None and built >= limit:
            break
        d = json.loads(f.read_text(encoding="utf-8"))
        out = ROOT / f.stem / "index.html"
        if out.exists() and not args and not d.get("rebuild"):
            continue
        if not d.get("photos") and not d.get("reviews") and d.get("kind") == "business":
            print("skip (needs photos and reviews):", f.stem)
            continue
        page = build(d)
        if page is None:
            print("left for next run (Groq busy):", f.stem)
            continue
        out.parent.mkdir(exist_ok=True)
        out.write_text(page, encoding="utf-8")
        built += 1
        print("built", f.stem)
        time.sleep(4)
    # manifest the call list reads, so new previews show up there without a rebuild
    man = {json.loads(f.read_text(encoding="utf-8"))["id"]: f.stem for f in DATA.glob("*.json") if (ROOT / f.stem / "index.html").exists()}
    (ROOT / "manifest.json").write_text(json.dumps(man, indent=1), encoding="utf-8")
    status_page()


if __name__ == "__main__":
    main(sys.argv[1:])
