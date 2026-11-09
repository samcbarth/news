"""Writes sample JSON Feed 1.1 files for local testing of the hub.

TEST DATA ONLY. Every feed carries "_test": true and every title starts with "[TEST]".
build.py drops these in production builds and aborts if any reach the published output.
This folder starts with "_" so GitHub Pages (Jekyll) does not serve it.

  python _testdata/make_samples.py
"""
import json, pathlib, datetime as dt

HERE = pathlib.Path(__file__).parent
SITES = {
    "realestate": ("Real Estate", ["Sample: rent survey for a mid-size Texas metro", "Sample: property tax protest deadline reminder",
                                   "Sample: what a rate change does to a duplex's cash flow", "Sample: Oklahoma County listing counts"]),
    "tools": ("Tools", ["Sample: a browser release changes a developer API", "Sample: a free image compressor update",
                        "Sample: a CRM adds a new free tier limit", "Sample: a password manager feature note"]),
    "games": ("Games", ["Sample: a new original browser game ships", "Sample: a console update note",
                        "Sample: a release date moves", "Sample: a free weekend on a PC storefront"]),
    "streaming": ("Streaming", ["Sample: a service changes its ad tier", "Sample: a device firmware update",
                                "Sample: a bundle adds a partner app", "Sample: what leaves a catalog next month"]),
    "homerepair": ("Home Repair", ["Sample: a tool recall notice", "Sample: a local permit fee change",
                                   "Sample: winter pipe freeze tips from a utility", "Sample: a building code update"]),
    "deals": ("Deals", ["Sample: a retailer moves its sale weekend", "Sample: price-match policy changes",
                        "Sample: a return window extends for the holidays", "Sample: a gift card fee rule"]),
}

now = dt.datetime(2026, 11, 9, 7, 0, tzinfo=dt.timezone(dt.timedelta(hours=-6)))
for n, (key, (label, titles)) in enumerate(SITES.items()):
    base = f"https://{key}.samcbarth.com"
    items = []
    for i, t in enumerate(titles):
        d = now - dt.timedelta(hours=n * 3 + i * 17)
        items.append({
            "id": f"{base}/news/test-sample-{i + 1}/",
            "url": f"{base}/news/test-sample-{i + 1}/",
            "title": f"[TEST] {t}",
            "summary": "Placeholder item for local testing of the news hub. Not a real story.",
            "image": "",
            "date_published": d.isoformat(),
            "tags": [label, "test"],
            "_test": True,
        })
    feed = {
        "version": "https://jsonfeed.org/version/1.1",
        "title": f"[TEST] {label} news (sample feed)",
        "home_page_url": f"{base}/news/",
        "feed_url": f"{base}/news/feed.json",
        "_test": True,
        "items": items,
    }
    (HERE / f"{key}.json").write_text(json.dumps(feed, indent=2), encoding="utf-8")
print("wrote", len(SITES), "sample feeds")
