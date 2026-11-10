#!/usr/bin/env python3
"""Static build for The Quillmark (news.samcbarth.com).

  python build.py           production build into the repo root.
                            Pulls every network feed live; if a feed fails, the last
                            good copy in data/feed-cache.json is used.
  python build.py --test    test build into _preview/ (gitignored, never published).
                            Uses C:\\SamSites\\<site>\\news\\feed.json when it exists,
                            otherwise the sample feeds in _testdata/.

Sources of truth: site.json (masthead, sections, feed URLs) and stories/*.json
(one file per hub-only story). Re-run after any change.
"""
import argparse, datetime as dt, html, json, os, pathlib, re, shutil, sys, urllib.request
from email.utils import format_datetime

ROOT = pathlib.Path(__file__).resolve().parent
SITE = json.loads((ROOT / "site.json").read_text(encoding="utf-8"))
BASE = SITE["base"].rstrip("/")
NAME = SITE["name"]
SECTIONS = SITE["sections"]
SEC = {s["key"]: s for s in SECTIONS}
SAMSITES = pathlib.Path(os.environ.get("SAMSITES_DIR") or ROOT.parent)  # where sibling site folders live
CACHE = ROOT / "data" / "feed-cache.json"
TEST_MARK = "[TEST]"

GTM = '''<script async src="https://www.googletagmanager.com/gtm.js?id=GTM-KMS4X55L"></script>
<script>
  window.dataLayer = window.dataLayer || [];
  function gtag(){dataLayer.push(arguments);}
  gtag('js', new Date());
</script>'''

e = lambda s: html.escape(str(s or ""), quote=True)


# ---------------------------------------------------------------- dates
def parse_date(s):
    if not s:
        return None
    try:
        d = dt.datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except ValueError:
        return None
    if d.tzinfo is None:
        d = d.replace(tzinfo=dt.timezone.utc)
    return d


def nice_date(d):
    return f"{d.strftime('%b')} {d.day}, {d.year}"


def long_date(d):
    return f"{d.strftime('%A, %B')} {d.day}, {d.year}"


# ---------------------------------------------------------------- feeds
def fetch_json(url, timeout):
    req = urllib.request.Request(url, headers={"User-Agent": "QuillmarkHubBuilder/1.0 (+https://news.samcbarth.com/about/)"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def is_test(feed, item):
    return bool(feed.get("_test") or item.get("_test") or str(item.get("title", "")).startswith(TEST_MARK))


def normalize(feed, sec, allow_test):
    out = []
    for it in feed.get("items", [])[:40]:
        if is_test(feed, it) and not allow_test:
            continue
        url, title = it.get("url") or it.get("external_url"), it.get("title")
        d = parse_date(it.get("date_published") or it.get("date_modified"))
        if not (url and title and d):
            continue
        if url.startswith("/"):
            url = sec["site"] + url
        if not url.startswith("https://"):
            continue
        image = it.get("image") or it.get("banner_image") or ""
        if image.startswith("/"):
            image = sec["site"] + image
        out.append({
            "id": it.get("id") or url, "title": title, "url": url,
            "summary": it.get("summary") or "", "image": image if image.startswith("https://") else "",
            "date": d.isoformat(), "tags": it.get("tags") or [], "section": sec["key"],
            "external": True, "site_label": sec["site_label"], "test": is_test(feed, it),
        })
    return out


def load_feeds(test):
    """Returns ({section_key: [items]}, {section_key: status string}, {section_key: raw feed for client copy})."""
    items, status, raw = {}, {}, {}
    cache = json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else {}
    timeout = SITE.get("feed_timeout_seconds", 8)
    for s in SECTIONS:
        k = s["key"]
        feed, how = None, "none"
        if test:
            local = SAMSITES / k / "news" / "feed.json"
            sample = ROOT / "_testdata" / f"{k}.json"
            if local.exists():
                try:
                    feed, how = json.loads(local.read_text(encoding="utf-8-sig")), f"local sibling {local}"
                except (ValueError, OSError) as ex:
                    print(f"  WARNING: {local} is not valid JSON ({ex}); using sample instead")
            if feed is None and sample.exists():
                feed, how = json.loads(sample.read_text(encoding="utf-8")), f"sample {sample.relative_to(ROOT)}"
        else:
            try:
                feed, how = fetch_json(s["feed"], timeout), f"live {s['feed']}"
                good = normalize(feed, s, False)
                if good:
                    cache[k] = feed
            except Exception as ex:  # offline, 404 before the site exists, bad JSON
                if k in cache:
                    feed, how = cache[k], f"cache (live failed: {type(ex).__name__})"
                else:
                    how = f"unavailable ({type(ex).__name__})"
        items[k] = normalize(feed, s, test) if feed else []
        raw[k] = feed
        status[k] = f"{how}: {len(items[k])} items"
    if not test:
        CACHE.parent.mkdir(exist_ok=True)
        CACHE.write_text(json.dumps(cache, indent=1, ensure_ascii=False), encoding="utf-8")
    return items, status, raw


def load_stories():
    stories = []
    for f in sorted((ROOT / "stories").glob("*.json")):
        st = json.loads(f.read_text(encoding="utf-8"))
        assert st["slug"] == f.stem, f"slug must match filename: {f.name}"
        assert st["section"] in SEC, f"unknown section in {f.name}"
        assert st.get("sources"), f"{f.name} needs at least one source"
        st["d"] = parse_date(st["date_published"])
        st["dm"] = parse_date(st.get("date_modified")) or st["d"]
        stories.append(st)
    return stories


# ---------------------------------------------------------------- page shell
class Ctx:
    prefix = ""      # "" in production, "/_preview" in test builds
    test = False
    build_date = None
    feeds_js = "[]"


def link(path):
    return Ctx.prefix + path


def section_url(s):
    return f"/section/{s['slug']}/"


def nav_html(active=None):
    li = [f'<a href="{link("/")}"{" aria-current=page" if active == "home" else ""}>Front page</a>']
    for s in SECTIONS:
        cur = ' aria-current="page"' if active == s["key"] else ""
        li.append(f'<a href="{link(section_url(s))}"{cur}>{e(s["name"])}</a>')
    return "\n".join(li)


def network_bar():
    out = []
    for n in SITE["network"]:
        if n.get("current"):
            out.append(f'<li><span aria-current="page">{e(n["label"])}</span></li>')
        else:
            out.append(f'<li><a href="{e(n["url"])}">{e(n["label"])}</a></li>')
    return "\n".join(out)


def jsonld(obj):
    return f'<script type="application/ld+json">{json.dumps(obj, ensure_ascii=False)}</script>'


def breadcrumbs(trail):
    return {
        "@context": "https://schema.org", "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": i + 1, "name": n, **({"item": BASE + u} if u else {})}
            for i, (n, u) in enumerate(trail)
        ],
    }


PUBLISHER = {
    "@type": "NewsMediaOrganization", "name": NAME, "url": BASE + "/",
    "logo": {"@type": "ImageObject", "url": BASE + "/assets/logo.png", "width": 512, "height": 512},
    "publishingPrinciples": BASE + "/about/#standards",
}


def page(path, title, desc, body, ld=(), og_type="website", active=None, extra_head=""):
    canonical = BASE + path
    robots = '<meta name="robots" content="noindex, nofollow">' if Ctx.test else '<meta name="robots" content="index, follow, max-image-preview:large">'
    banner = ('<div class="test-banner" role="note">TEST BUILD: sample or local feed data. Not for publishing.</div>'
              if Ctx.test else "")
    full_title = title if title.startswith(NAME) else f"{title} | {NAME}"
    return f"""<!doctype html>
<html lang="en">
<head>
{GTM}
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(full_title)}</title>
<meta name="description" content="{e(desc)}">
<link rel="canonical" href="{e(canonical)}">
{robots}
<meta property="og:site_name" content="{e(NAME)}">
<meta property="og:type" content="{og_type}">
<meta property="og:title" content="{e(title)}">
<meta property="og:description" content="{e(desc)}">
<meta property="og:url" content="{e(canonical)}">
<meta property="og:image" content="{BASE}/assets/og.png">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:locale" content="{SITE['locale']}">
<meta name="twitter:card" content="summary_large_image">
<meta name="theme-color" content="#000000">
<meta name="color-scheme" content="dark">
<link rel="icon" href="{link('/assets/favicon.svg')}" type="image/svg+xml">
<link rel="alternate" type="application/rss+xml" title="{e(NAME)}" href="{link('/feed.xml')}">
<link rel="alternate" type="application/feed+json" title="{e(NAME)}" href="{link('/feed.json')}">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@700&family=Barlow:wght@900&family=Inter:wght@400;500;700&display=swap">
<link rel="stylesheet" href="{link('/assets/style.css')}">
{extra_head}
{''.join(jsonld(x) for x in ld)}
</head>
<body>
{banner}
<a class="skip" href="#main">Skip to content</a>
<header class="site-head">
  <div class="topbar">
    <div class="topbar-in wrap">
      <a class="logo" href="{link('/')}">{e(NAME)}</a>
      <nav class="sections" aria-label="Sections">
{nav_html(active)}
      </nav>
      <span class="topbar-links"><a href="{link('/about/')}">About</a><a href="{link('/feed.xml')}">RSS</a></span>
    </div>
  </div>
  <div class="masthead">
    <span class="dateline">{long_date(Ctx.build_date)}</span>
    <a class="wordmark" href="{link('/')}" tabindex="-1" aria-hidden="true">{e(NAME)}</a>
    <p class="tagline">{e(SITE['tagline'])}</p>
  </div>
  <div class="band" role="presentation"></div>
</header>
<main id="main" class="wrap">
{body}
</main>
<footer class="site-foot">
  <div class="wrap">
    <nav class="network" aria-label="samcbarth.com network">
      <span class="network-label">The network</span>
      <ul>
{network_bar()}
      </ul>
    </nav>
    <div class="foot-cols">
      <div><a class="wordmark small" href="{link('/')}">{e(NAME)}</a>
      <p>Every story links to its source. Section stories link back to the network site that published them.</p></div>
      <ul class="foot-links">
        <li><a href="{link('/about/')}">About</a></li>
        <li><a href="{link('/about/#standards')}">Editorial standards</a></li>
        <li><a href="{link('/contact/')}">Contact</a></li>
        <li><a href="{link('/privacy/')}">Privacy Policy</a></li>
        <li><a href="{link('/terms/')}">Terms</a></li>
        <li><a href="{link('/feed.xml')}">RSS</a></li>
      </ul>
    </div>
    <p class="fine">&copy; {Ctx.build_date.year} {e(NAME)}, part of the samcbarth.com network.</p>
  </div>
</footer>
<script src="{link('/assets/config.js')}"></script>
<script>window.QM_FEEDS={Ctx.feeds_js};window.QM_PREFIX="{Ctx.prefix}";</script>
<script src="{link('/assets/app.js')}" defer></script>
</body>
</html>
"""


# ---------------------------------------------------------------- pieces
def ad(slot):
    """Empty until ADSENSE_CLIENT is set in assets/config.js; app.js fills or removes it."""
    return f'<div class="ad-slot" data-ad-slot-name="{slot}" aria-hidden="true"></div>'


def item_href(it):
    return it["url"] if it["external"] else link(it["url"])


def thumb(it, size="md"):
    s = SEC[it["section"]]
    if it.get("image"):
        return (f'<div class="thumb s-{s["key"]}"><img src="{e(it["image"])}" alt="" loading="lazy" decoding="async" '
                f'width="640" height="360" onerror="this.remove()"></div>')
    return f'<div class="thumb s-{s["key"]} art" aria-hidden="true"><span>{e(s["name"][0])}</span></div>'


def meta_line(it):
    d = parse_date(it["date"])
    src = f'<span class="src">{e(it["site_label"])}</span>' if it["external"] else f'<span class="src own">{e(NAME)}</span>'
    return f'<span class="meta"><time datetime="{e(it["date"])}">{nice_date(d)}</time> {src}</span>'


def card(it, variant="card", show_summary=True, show_thumb=True):
    s = SEC[it["section"]]
    rel = ' rel="noopener"' if it["external"] else ""
    test = ' data-test="1"' if it.get("test") else ""
    summ = f'<p class="summary">{e(it["summary"])}</p>' if show_summary and it["summary"] else ""
    return f"""<article class="{variant}"{test}>
  <a href="{e(item_href(it))}"{rel}>
    {thumb(it) if show_thumb else ''}
    <div class="card-body">
      <span class="kicker k-{s['key']}">{e(s['name'])}</span>
      <h3>{e(it['title'])}</h3>
      {summ}
      {meta_line(it)}
    </div>
  </a>
</article>"""


def latest_list(items, n=10):
    lis = []
    for it in items[:n]:
        rel = ' rel="noopener"' if it["external"] else ""
        s = SEC[it["section"]]
        lis.append(f'<li><span class="kicker k-{s["key"]}">{e(s["name"])}</span>'
                   f'<a href="{e(item_href(it))}"{rel}>{e(it["title"])}</a>{meta_line(it)}</li>')
    return "\n".join(lis)


def story_item(st):
    return {
        "id": BASE + f"/story/{st['slug']}/", "title": st["title"], "url": f"/story/{st['slug']}/",
        "summary": st["dek"], "image": st.get("image", ""), "date": st["d"].isoformat(),
        "tags": st.get("tags", []), "section": st["section"], "external": False,
        "site_label": NAME, "test": False,
    }


def items_json(items):
    slim = [{k: it[k] for k in ("title", "url", "summary", "image", "date", "section", "external", "site_label")}
            for it in items[:80]]
    return json.dumps(slim, ensure_ascii=False).replace("</", "<\\/")


# ---------------------------------------------------------------- pages
def build_home(all_items, by_sec, stories):
    hub_sorted = sorted(stories, key=lambda s: s["d"], reverse=True)
    lead = story_item(hub_sorted[0]) if hub_sorted else all_items[0]
    rest = [i for i in all_items if i["url"] != lead["url"]]
    top = rest[:4]
    rails = []
    for n, s in enumerate(SECTIONS):
        its = by_sec[s["key"]][:4]
        if its:
            inner = "\n".join(card(i, "card", show_summary=False) for i in its)
        else:
            inner = (f'<p class="empty">The {e(s["name"])} desk at <a href="{e(s["site"])}/">{e(s["site_label"])}</a> '
                     f'has not published yet. {e(s["blurb"])}</p>')
        rails.append(f"""<section class="rail" aria-labelledby="rail-{s['key']}">
  <header class="rail-head"><h2 id="rail-{s['key']}"><a href="{link(section_url(s))}">{e(s['name'])}</a></h2>
  <a class="more" href="{link(section_url(s))}">More {e(s['name'])}</a></header>
  <div class="rail-grid" data-rail="{s['key']}">
{inner}
  </div>
</section>""")
        if n in (1, 3):
            rails.append(ad(f"between-rails-{(n + 1) // 2}"))
    body = f"""
<h1 class="visually-hidden">{e(NAME)}: housing, tools, gaming, streaming, home and deals news</h1>
<div class="front">
  <div class="front-main">
    <div class="lead-block">
      {card(lead, "lead")}
      <div class="top-stack">
{''.join(card(i, "compact", show_thumb=False) for i in top)}
      </div>
    </div>
    {ad("after-lead")}
{''.join(rails)}
  </div>
  <aside class="front-side" aria-label="Latest">
    <section class="latest">
      <h2>Latest</h2>
      <ol id="latest-list">
{latest_list(all_items)}
      </ol>
      <p class="updated" id="feed-updated" hidden></p>
    </section>
    {ad("sidebar")}
  </aside>
</div>
<script type="application/json" id="qm-items">{items_json(all_items)}</script>
"""
    ld = [
        {"@context": "https://schema.org", "@type": "WebSite", "name": NAME, "url": BASE + "/",
         "description": SITE["description"], "publisher": PUBLISHER},
        {"@context": "https://schema.org", **PUBLISHER},
        breadcrumbs([("Front page", "/")]),
    ]
    return page("/", f"{NAME}: news from housing, tech, gaming, streaming, home and deals",
                SITE["description"], body, ld, active="home")


def build_section(s, items, all_items):
    blocks = []
    for n, it in enumerate(items):
        blocks.append(card(it, "row"))
        if n == 5:
            blocks.append(ad("section-mid"))
    if not items:
        blocks.append(f'<p class="empty">No stories yet. The {e(s["name"])} desk publishes at '
                      f'<a href="{e(s["site"])}/news/">{e(s["site_label"])}/news</a>.</p>')
    ever = "".join(f'<li><a href="{e(x["url"])}">{e(x["label"])}</a></li>' for x in s["evergreen"])
    body = f"""
<nav class="crumbs" aria-label="Breadcrumb"><a href="{link('/')}">Front page</a> <span>/</span> {e(s['name'])}</nav>
<div class="section-head s-line-{s['key']}">
  <h1>{e(s['name'])} news</h1>
  <p class="answer">{e(s['blurb'])} Stories marked {e(s['site_label'])} open on that site; stories marked {e(NAME)} are written here.</p>
</div>
<div class="front">
  <div class="front-main">
    <div class="list" data-rail="{s['key']}" data-variant="row">
{''.join(blocks)}
    </div>
    {ad("section-end")}
  </div>
  <aside class="front-side">
    <section class="side-box"><h2>From {e(s['site_label'])}</h2><ul>{ever}</ul></section>
    <section class="latest"><h2>Latest across the network</h2><ol id="latest-list">{latest_list(all_items, 6)}</ol></section>
    {ad("sidebar")}
  </aside>
</div>
<script type="application/json" id="qm-items">{items_json(all_items)}</script>
"""
    path = section_url(s)
    ld = [
        {"@context": "https://schema.org", "@type": "CollectionPage", "name": f"{s['name']} news", "url": BASE + path,
         "description": s["blurb"], "isPartOf": {"@type": "WebSite", "name": NAME, "url": BASE + "/"},
         "mainEntity": {"@type": "ItemList", "itemListElement": [
             {"@type": "ListItem", "position": i + 1, "url": it["url"] if it["external"] else BASE + it["url"]}
             for i, it in enumerate(items[:20])]}},
        breadcrumbs([("Front page", "/"), (s["name"] + " news", path)]),
    ]
    return page(path, f"{s['name']} news", f"{s['name']} news from {NAME}: {s['blurb']}", body, ld, active=s["key"])


def build_story(st, all_items):
    s = SEC[st["section"]]
    path = f"/story/{st['slug']}/"
    parts, pcount, ad_done = [], 0, False
    for b in st["body"]:
        if "h" in b:
            parts.append(f"<h2>{e(b['h'])}</h2>")
        else:
            parts.append(f"<p>{e(b['p'])}</p>")
            pcount += 1
            if pcount == 3 and not ad_done:
                parts.append(ad("in-article"))
                ad_done = True
    sources = "".join(f'<li><a href="{e(x["url"])}" rel="noopener">{e(x["label"])}</a></li>' for x in st["sources"])
    ever = "".join(f'<li><a href="{e(x["url"])}">{e(x["label"])}</a></li>' for x in s["evergreen"])
    more = [i for i in all_items if i["section"] == s["key"] and i["url"] != path][:4]
    more_html = "".join(card(i, "compact", show_thumb=False) for i in more) or "<p>More stories coming soon.</p>"
    d = st["d"]
    body = f"""
<nav class="crumbs" aria-label="Breadcrumb"><a href="{link('/')}">Front page</a> <span>/</span>
<a href="{link(section_url(s))}">{e(s['name'])}</a></nav>
<div class="front">
  <article class="story front-main">
    <header class="story-head">
      <span class="kicker k-{s['key']}">{e(s['name'])}</span>
      <h1>{e(st['title'])}</h1>
      <p class="dek">{e(st['dek'])}</p>
      <p class="byline">By {e(NAME)} staff &middot; <time datetime="{d.isoformat()}">{nice_date(d)}</time></p>
    </header>
    <div class="story-body">
{''.join(parts)}
    </div>
    <section class="sources"><h2>Sources</h2><ul>{sources}</ul>
    <p class="note">{e(NAME)} writes short summaries and links to the original source for full detail. Spot an error? <a href="{link('/contact/')}">Tell us</a>.</p></section>
    {ad("end-of-article")}
    <section class="related"><h2>More {e(s['name'])}</h2><div class="related-grid">{more_html}</div></section>
  </article>
  <aside class="front-side">
    <section class="side-box"><h2>From {e(s['site_label'])}</h2><ul>{ever}</ul></section>
    <section class="latest"><h2>Latest</h2><ol>{latest_list(all_items, 6)}</ol></section>
    {ad("sidebar")}
  </aside>
</div>
"""
    ld = [
        {"@context": "https://schema.org", "@type": "NewsArticle", "headline": st["title"],
         "description": st["dek"], "datePublished": d.isoformat(), "dateModified": st["dm"].isoformat(),
         "articleSection": s["name"], "keywords": st.get("tags", []),
         "image": [BASE + "/assets/og.png"], "mainEntityOfPage": BASE + path, "url": BASE + path,
         "author": {"@type": "Organization", "name": f"{NAME} desk", "url": BASE + "/about/"},
         "publisher": PUBLISHER, "isAccessibleForFree": True,
         "citation": [x["url"] for x in st["sources"]]},
        breadcrumbs([("Front page", "/"), (s["name"] + " news", section_url(s)), (st["title"], path)]),
    ]
    extra = (f'<meta property="article:published_time" content="{d.isoformat()}">'
             f'<meta property="article:section" content="{e(s["name"])}">')
    return page(path, st["title"], st["dek"], body, ld, og_type="article", active=s["key"], extra_head=extra)


def static_page(path, title, desc, inner, crumb):
    body = f"""<nav class="crumbs" aria-label="Breadcrumb"><a href="{link('/')}">Front page</a> <span>/</span> {e(crumb)}</nav>
<article class="prose">
{inner}
</article>"""
    ld = [{"@context": "https://schema.org", "@type": "WebPage", "name": title, "url": BASE + path,
           "description": desc, "isPartOf": {"@type": "WebSite", "name": NAME, "url": BASE + "/"}},
          breadcrumbs([("Front page", "/"), (crumb, path)])]
    return page(path, title, desc, body, ld)


def static_pages():
    upd = nice_date(Ctx.build_date)
    sec_list = "".join(f'<li><a href="{e(s["site"])}/">{e(s["site_label"])}</a>: {e(s["blurb"])}</li>' for s in SECTIONS)
    pages = {}
    pages["/about/"] = ("About The Quillmark", f"What {NAME} is, how its stories are chosen and sourced, and how to report an error.", f"""
<h1>About {e(NAME)}</h1>
<h2>What is {e(NAME)}?</h2>
<p>{e(NAME)} is the front page of the samcbarth.com network, a group of independent sites published by Sam Barth. It collects the latest headlines from each network site's news desk and adds a small number of its own short stories about the same beats.</p>
<h2>Which sites feed it?</h2>
<ul>{sec_list}</ul>
<p>When you click a section headline, you go to the story on the site that published it. Stories marked {e(NAME)} are written here.</p>
<h2 id="standards">What are the editorial standards?</h2>
<ul>
<li>Every story links to its primary source, such as a government release, company announcement or the outlet that first reported it.</li>
<li>We write original summaries. We do not copy other outlets' articles, and we quote at most one short line per story, with attribution.</li>
<li>We do not invent facts, numbers, quotes or events. If a detail cannot be verified, it is left out.</li>
<li>Stories explain what happened and why it matters to readers of the network. They are not personal endorsements.</li>
</ul>
<h2>How do corrections work?</h2>
<p>If you find an error, use the <a href="{link('/contact/')}">contact page</a>. Confirmed errors are fixed on the page and the change is noted at the end of the story.</p>
<h2>How is the site paid for?</h2>
<p>{e(NAME)} may show ads from Google AdSense. Some network sites earn affiliate commissions; those sites disclose it on each page. Advertisers do not choose or review stories.</p>
""", "About")
    pages["/contact/"] = ("Contact", f"How to reach {NAME} with corrections, tips or questions.", """
<h1>Contact</h1>
<h2>How do I reach the desk?</h2>
<p>Corrections, story tips and general questions all go to the same place.</p>
<div id="contact-slot" class="contact-slot"><p>The contact form is loading. If it does not appear, check back soon.</p></div>
<h2>What should a correction include?</h2>
<p>The story link, the sentence you think is wrong, and a source that shows the correct information. That lets us check and fix it quickly.</p>
""", "Contact")
    pages["/privacy/"] = ("Privacy Policy", f"How {NAME} uses cookies, analytics and Google ads, and the choices you have.", f"""
<h1>Privacy Policy</h1>
<p class="answer">Last updated {upd}. {e(NAME)} does not ask you to create an account. We use analytics and, when enabled, Google ads, both of which can set cookies.</p>
<h2>What data is collected?</h2>
<p>We use Google Tag Manager and Google Analytics to understand which pages are read. These tools collect information such as pages viewed, approximate location, device and browser type, and referring site. We do not collect names or email addresses unless you send them to us through the contact page.</p>
<h2>How are cookies and Google ads used?</h2>
<p>This site may show ads served by Google AdSense. Third-party vendors, including Google, use cookies to serve ads based on your prior visits to this and other websites. Google's use of advertising cookies enables it and its partners to serve ads based on your visits to this site and other sites on the internet. You can opt out of personalized advertising at <a href="https://adssettings.google.com/" rel="noopener">Google Ads Settings</a>, and learn more at <a href="https://policies.google.com/technologies/ads" rel="noopener">How Google uses information from sites that use its services</a>. You can also opt out of some third-party vendors' cookies at <a href="https://www.aboutads.info/choices/" rel="noopener">aboutads.info</a>.</p>
<h2>What about affiliate links?</h2>
<p>Headlines on this page link to other samcbarth.com network sites. Some of those sites, such as the streaming, home repair and deals sites, contain affiliate links, including Amazon Associates links, that may earn a commission. Those sites disclose this on every page that has such links.</p>
<h2>What about the dark mode setting?</h2>
<p>If you switch between light and dark mode, that choice is saved in your browser's local storage. It never leaves your device.</p>
<h2>Children's privacy</h2>
<p>This site is not directed to children under 13 and does not knowingly collect their information.</p>
<h2>Contact</h2>
<p>Questions about this policy can be sent through the <a href="{link('/contact/')}">contact page</a>.</p>
""", "Privacy Policy")
    pages["/terms/"] = ("Terms of Use", f"Terms for using {NAME}, including how news summaries and outside links work.", f"""
<h1>Terms of Use</h1>
<p class="answer">Last updated {upd}. By using {e(NAME)} you agree to these terms.</p>
<h2>Is the content advice?</h2>
<p>No. Stories are general news summaries for information only. They are not financial, legal, real estate, safety or purchasing advice. Check the linked primary source and a qualified professional before acting.</p>
<h2>Who owns the content?</h2>
<p>Original text on this site belongs to {e(NAME)}. You may quote short passages with a link back. Linked stories, trademarks and source material belong to their owners.</p>
<h2>What about links to other sites?</h2>
<p>We link to network sites and outside sources. We are not responsible for the content or policies of outside sites.</p>
<h2>Is accuracy guaranteed?</h2>
<p>We work to keep stories accurate and fix confirmed errors, but the site is provided as is, without warranties. Figures such as rates and prices change after publication.</p>
<h2>Can these terms change?</h2>
<p>Yes. Changes take effect when posted on this page.</p>
""", "Terms")
    return pages


def build_404():
    body = f"""<article class="prose"><h1>Page not found</h1>
<p>That page does not exist or has moved. Try the <a href="{link('/')}">front page</a> or a section:</p>
<ul>{''.join(f'<li><a href="{link(section_url(s))}">{e(s["name"])}</a></li>' for s in SECTIONS)}</ul></article>"""
    return page("/404.html", "Page not found", f"Page not found on {NAME}.", body)


# ---------------------------------------------------------------- feeds out
def rss(items):
    out = []
    for it in items[:40]:
        url = it["url"] if it["external"] else BASE + it["url"]
        d = parse_date(it["date"])
        out.append(f"""<item><title>{e(it['title'])}</title><link>{e(url)}</link><guid isPermaLink="true">{e(url)}</guid>
<pubDate>{format_datetime(d)}</pubDate><category>{e(SEC[it['section']]['name'])}</category><description>{e(it['summary'])}</description></item>""")
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom"><channel>
<title>{e(NAME)}</title><link>{BASE}/</link><description>{e(SITE['description'])}</description><language>en-us</language>
<atom:link href="{BASE}/feed.xml" rel="self" type="application/rss+xml"/>
{''.join(out)}
</channel></rss>
"""


def json_feed(stories):
    return json.dumps({
        "version": "https://jsonfeed.org/version/1.1", "title": NAME, "home_page_url": BASE + "/",
        "feed_url": BASE + "/feed.json", "description": "Hub-only stories from " + NAME,
        "language": "en-US",
        "items": [{"id": BASE + f"/story/{s['slug']}/", "url": BASE + f"/story/{s['slug']}/", "title": s["title"],
                   "summary": s["dek"], "image": BASE + "/assets/og.png", "date_published": s["d"].isoformat(),
                   "tags": [SEC[s["section"]]["name"]] + s.get("tags", [])}
                  for s in sorted(stories, key=lambda x: x["d"], reverse=True)],
    }, indent=2, ensure_ascii=False)


def sitemap(paths):
    urls = "".join(f"<url><loc>{BASE}{p}</loc><lastmod>{lm}</lastmod></url>\n" for p, lm in paths)
    return f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{urls}</urlset>\n'


def llms(stories):
    lines = [f"# {NAME}", "", f"> {SITE['description']}", "",
             "Hub of the samcbarth.com network. Section headlines link to the network site that published them; "
             "stories under /story/ are written here and cite primary sources.", "", "## Sections"]
    lines += [f"- [{s['name']}]({BASE}{section_url(s)}): {s['blurb']} Source site: {s['site']}/" for s in SECTIONS]
    lines += ["", "## Hub stories"]
    lines += [f"- [{s['title']}]({BASE}/story/{s['slug']}/): {s['dek']}"
              for s in sorted(stories, key=lambda x: x["d"], reverse=True)]
    lines += ["", "## About", f"- [About and editorial standards]({BASE}/about/)", f"- [RSS]({BASE}/feed.xml)",
              f"- [JSON Feed]({BASE}/feed.json)", ""]
    return "\n".join(lines)


# ---------------------------------------------------------------- main
GENERATED = ["index.html", "404.html", "feed.xml", "feed.json", "sitemap.xml", "robots.txt", "llms.txt",
             "section", "story", "about", "contact", "privacy", "terms"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--test", action="store_true", help="build into _preview/ with sample or local sibling feeds")
    args = ap.parse_args()
    Ctx.test = args.test
    Ctx.prefix = "/_preview" if args.test else ""
    Ctx.build_date = dt.datetime.now(dt.timezone(dt.timedelta(hours=-6)))
    out = ROOT / "_preview" if args.test else ROOT

    stories = load_stories()
    feeds, status, raw = load_feeds(args.test)
    for k, v in status.items():
        print(f"  feed {k:11s} {v}")

    if args.test:
        shutil.rmtree(out, ignore_errors=True)
        out.mkdir()
        shutil.copytree(ROOT / "assets", out / "assets")
        (out / "feeds").mkdir()
        for k, f in raw.items():
            if f:
                (out / "feeds" / f"{k}.json").write_text(json.dumps(f, ensure_ascii=False), encoding="utf-8")
        Ctx.feeds_js = json.dumps([{"section": k, "url": f"/_preview/feeds/{k}.json"} for k, f in raw.items() if f])
    else:
        for g in ("section", "story", "about", "contact", "privacy", "terms"):
            shutil.rmtree(out / g, ignore_errors=True)
        # Only refresh in the browser the feeds that answered at build time (live or cached), so a site
        # whose DNS is not set up yet does not log network errors on every page view.
        Ctx.feeds_js = json.dumps([{"section": s["key"], "url": s["feed"]} for s in SECTIONS if raw.get(s["key"])])

    hub = [story_item(s) for s in stories]
    all_items = sorted(hub + [i for v in feeds.values() for i in v], key=lambda i: i["date"], reverse=True)
    # de-dupe by URL
    seen, uniq = set(), []
    for i in all_items:
        if i["url"] not in seen:
            seen.add(i["url"]); uniq.append(i)
    all_items = uniq
    by_sec = {s["key"]: [i for i in all_items if i["section"] == s["key"]] for s in SECTIONS}

    def write(rel, text):
        p = out / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")

    today = Ctx.build_date.date().isoformat()
    paths = [("/", today)]
    write("index.html", build_home(all_items, by_sec, stories))
    for s in SECTIONS:
        write(f"section/{s['slug']}/index.html", build_section(s, by_sec[s["key"]], all_items))
        paths.append((section_url(s), today))
    for st in stories:
        write(f"story/{st['slug']}/index.html", build_story(st, all_items))
        paths.append((f"/story/{st['slug']}/", st["dm"].date().isoformat()))
    for p, (title, desc, inner, crumb) in static_pages().items():
        write(p.strip("/") + "/index.html", static_page(p, title, desc, inner, crumb))
        paths.append((p, today))
    write("404.html", build_404())
    write("feed.xml", rss(all_items))
    write("feed.json", json_feed(stories))
    write("sitemap.xml", sitemap(paths))
    write("llms.txt", llms(stories))
    write("robots.txt", "User-agent: *\nDisallow: /\n" if args.test else
          f"User-agent: *\nAllow: /\nDisallow: /_testdata/\n\nSitemap: {BASE}/sitemap.xml\n")

    if not args.test:
        # Guard: test data must never reach the published build.
        bad = []
        for f in list(out.glob("*.html")) + list(out.glob("*/**/*.html")) + [out / "feed.xml"]:
            if f.is_file() and "_preview" not in f.parts and "_testdata" not in f.parts:
                t = f.read_text(encoding="utf-8")
                if TEST_MARK in t or 'data-test="1"' in t or "TEST BUILD" in t:
                    bad.append(str(f.relative_to(out)))
        if bad:
            sys.exit(f"ABORT: test data found in production output: {bad}")

    print(f"built {'TEST preview in _preview/' if args.test else 'production site'}: "
          f"{len(stories)} hub stories, {sum(len(v) for v in feeds.values())} feed items, {len(paths)} pages")


if __name__ == "__main__":
    main()
