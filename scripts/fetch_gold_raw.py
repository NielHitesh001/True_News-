"""One-off M0 helper: fetch candidate articles for the gold set from public RSS feeds.

Not the M2 collector. This exists only to assemble a real, recent sample for labeling.
Writes JSONL to gold/raw/items.jsonl: one line per fetched article with metadata
and extracted body text. Polite by construction: sequential requests, delay between
every fetch, no retries against rate limits.

Usage: .venv/bin/python scripts/fetch_gold_raw.py [max_items_per_feed]
"""

from __future__ import annotations

import json
import sys
import time
import urllib.request
from pathlib import Path
from xml.etree import ElementTree

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "gold" / "raw" / "items.jsonl"
DELAY_S = 2.5

FEEDS = {
    "bbc": "http://feeds.bbci.co.uk/news/world/rss.xml",
    "guardian": "https://www.theguardian.com/world/rss",
    "npr": "https://feeds.npr.org/1001/rss.xml",
    "aljazeera": "https://www.aljazeera.com/xml/rss/all.xml",
    "dw": "https://rss.dw.com/rdf/rss-en-all",
    "fox": "https://moxie.foxnews.com/google-publisher/latest.xml",
    "ap": "https://apnews.com/rss",
    "nyt": "https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml",
}

UA = {"User-Agent": "NewsExtractionGoldSet/0.1 (research; contact: local)"}


def get(url: str, timeout: int = 25) -> bytes:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def parse_feed(xml: bytes, source: str, limit: int) -> list[dict]:
    root = ElementTree.fromstring(xml)
    items = []
    for item in root.iter("item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        pub = (item.findtext("pubDate") or "").strip()
        if title and link:
            items.append({"source": source, "title": title, "url": link, "published": pub})
        if len(items) >= limit:
            break
    return items


def extract_text(html: bytes) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for bad in soup(["script", "style", "nav", "header", "footer", "aside"]):
        bad.decompose()
    ps = [p.get_text(" ", strip=True) for p in soup.find_all("p")]
    ps = [p for p in ps if len(p.split()) >= 5]
    return "\n".join(ps)


def main() -> None:
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 6
    OUT.parent.mkdir(parents=True, exist_ok=True)

    candidates: list[dict] = []
    for source, url in FEEDS.items():
        try:
            items = parse_feed(get(url), source, limit)
            print(f"[feed] {source}: {len(items)} items")
            candidates.extend(items)
        except Exception as e:  # noqa: BLE001 - log and continue; feeds are optional
            print(f"[feed] {source}: FAILED {type(e).__name__}: {e}")
        time.sleep(DELAY_S)

    seen = set()
    with OUT.open("a") as fh:
        for i, c in enumerate(candidates):
            if c["url"] in seen:
                continue
            seen.add(c["url"])
            rec = dict(c)
            rec["item_id"] = f"gold-{int(time.time())}-{i:03d}"
            rec["captured"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            try:
                rec["text"] = extract_text(get(c["url"]))
                rec["fetch_ok"] = True
            except Exception as e:  # noqa: BLE001
                rec["text"] = ""
                rec["fetch_ok"] = False
                rec["fetch_error"] = f"{type(e).__name__}: {e}"
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
            print(f"[art] {rec['item_id']} {c['source']:10s} ok={rec['fetch_ok']} "
                  f"chars={len(rec['text'])}")
            time.sleep(DELAY_S)

    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
