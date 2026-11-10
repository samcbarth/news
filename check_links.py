"""Link check for The Quillmark.

  python check_links.py            internal links, scripts, styles and images in the production build
  python check_links.py --preview  same for the _preview/ test build
  python check_links.py --external also requests every story source URL (needs network)

Exits non-zero on any broken internal link.
"""
import json, pathlib, re, sys, urllib.request
from html.parser import HTMLParser

ROOT = pathlib.Path(__file__).resolve().parent
PREVIEW = "--preview" in sys.argv
OUT = ROOT / "_preview" if PREVIEW else ROOT
PREFIX = "/_preview" if PREVIEW else ""


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.found = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        for key in ("href", "src"):
            if a.get(key):
                self.found.append(a[key])


def resolve(url, page):
    url = url.split("#")[0].split("?")[0]
    if not url or url.startswith(("http://", "https://", "mailto:", "data:", "//")):
        return None
    if url.startswith("/"):
        if PREVIEW and not url.startswith(PREFIX):
            return "OUTSIDE_PREVIEW"
        rel = url[len(PREFIX):].lstrip("/")
        target = OUT / rel
    else:
        target = (page.parent / url)
    if target.is_dir() or url.endswith("/"):
        target = target / "index.html"
    return target


pages = [p for p in OUT.rglob("*.html") if PREVIEW or not ({"_preview", "_testdata", ".git"} & set(p.relative_to(OUT).parts))]
broken, count = [], 0
for page in pages:
    parser = Links()
    parser.feed(page.read_text(encoding="utf-8"))
    for url in parser.found:
        t = resolve(url, page)
        if t is None:
            continue
        count += 1
        if t == "OUTSIDE_PREVIEW" or not pathlib.Path(t).exists():
            broken.append(f"{page.relative_to(OUT)} -> {url}")
print(f"{len(pages)} pages, {count} internal links checked, {len(broken)} broken")
for b in broken:
    print("  BROKEN", b)

if "--external" in sys.argv:
    bad = 0
    for f in sorted((ROOT / "stories").glob("*.json")):
        for s in json.loads(f.read_text(encoding="utf-8"))["sources"]:
            req = urllib.request.Request(s["url"], headers={"User-Agent": "Mozilla/5.0 (QuillmarkLinkCheck)"})
            try:
                code = urllib.request.urlopen(req, timeout=15).status
            except urllib.error.HTTPError as ex:
                code = ex.code
            except Exception as ex:
                code = type(ex).__name__
            flag = "ok " if code == 200 else "CHECK"
            if code != 200:
                bad += 1
            print(f"  {flag} {code} {s['url']}")
    print(f"external sources: {bad} not 200 (403/429 often means the site blocks scripts; open those in a browser)")

sys.exit(1 if broken else 0)
