"""Collector Component (M2).

Handles polite ingestion of articles from RSS/Atom feeds, direct URLs, and offline archives.
Persists raw payload snapshots and records collection audit logs (spec §4/§6).
"""

from __future__ import annotations

import hashlib
import json
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any, Optional
from xml.etree import ElementTree

from .registry import SourceRegistry
from .schemas import ArticleType, AuditEntry, Item
from .storage import Storage

DEFAULT_RAW_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "raw"
STAGE_VERSION = "1.0.0"
USER_AGENT = "NewsX-ExtractionTool/1.0 (+https://github.com/news-extraction-tool; research bot)"


class Collector:
    """Ingests news articles with polite rate limiting and archival."""

    def __init__(
        self,
        storage: Storage,
        registry: SourceRegistry,
        raw_dir: Optional[Path] = None,
        request_delay_s: float = 0.5,
    ) -> None:
        self.storage = storage
        self.registry = registry
        self.raw_dir = raw_dir or DEFAULT_RAW_DIR
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.request_delay_s = request_delay_s
        self._last_request_time: dict[str, float] = {}

    def _rate_limit(self, domain: str) -> None:
        now = time.time()
        last = self._last_request_time.get(domain, 0.0)
        elapsed = now - last
        if elapsed < self.request_delay_s:
            time.sleep(self.request_delay_s - elapsed)
        self._last_request_time[domain] = time.time()

    def fetch_url(self, url: str, timeout: int = 15) -> tuple[bytes, dict[str, str]]:
        domain = urllib.parse.urlparse(url).netloc
        self._rate_limit(domain)

        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": USER_AGENT,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            },
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            content = resp.read()
            headers = dict(resp.headers)
            return content, headers

    def save_raw_payload(self, identifier: str, content: bytes, meta: dict[str, Any]) -> Path:
        content_hash = hashlib.sha256(content).hexdigest()[:16]
        filename = f"{identifier}_{content_hash}.json"
        target_path = self.raw_dir / filename
        target_path.parent.mkdir(parents=True, exist_ok=True)

        payload = {
            "identifier": identifier,
            "meta": meta,
            "content_hash": content_hash,
            "content_utf8": content.decode("utf-8", errors="replace"),
            "captured_at": datetime.now(timezone.utc).isoformat(),
        }
        with target_path.open("w", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False, indent=2))

        return target_path

    def ingest_raw_record(
        self,
        source_id: str,
        url: str,
        title: str,
        raw_text: str,
        byline: str = "",
        dateline: str = "",
        published_time: Optional[datetime] = None,
        article_type: ArticleType = ArticleType.REPORTING,
        custom_id: Optional[str] = None,
    ) -> Item:
        """Ingest a pre-fetched or direct article payload into storage."""
        # Ensure source exists in registry and is saved to storage
        source = self.registry.get_or_raise(source_id)
        self.storage.save_source(source)

        item_id = custom_id or f"item-{source_id}-{hashlib.sha256(url.encode()).hexdigest()[:12]}"
        now = datetime.now(timezone.utc)

        # Archive raw text
        self.save_raw_payload(
            item_id,
            raw_text.encode("utf-8"),
            {"source_id": source_id, "url": url, "title": title, "byline": byline},
        )

        item = Item(
            id=item_id,
            source_id=source_id,
            url=url,  # type: ignore
            title=title,
            byline=byline,
            dateline=dateline,
            published_time=published_time,
            captured_time=now,
            edit_history=[],
            cleaned_text=raw_text,
            original_language=source.language or "en",
            article_type=article_type,
        )

        self.storage.save_item(item)

        # Audit trail
        self.storage.write_audit_entry(
            AuditEntry(
                stage="collection",
                stage_version=STAGE_VERSION,
                input_id=url,
                output_id=item.id,
                what_changed=f"Ingested raw item '{title}' from source {source_id}",
                when=now,
            )
        )

        return item

    def parse_rss_feed(self, xml_bytes: bytes, source_id: str, limit: int = 10) -> list[dict[str, Any]]:
        root = ElementTree.fromstring(xml_bytes)
        items: list[dict[str, Any]] = []

        # Find channel items
        for item in root.iter("item"):
            title = (item.findtext("title") or "").strip()
            link = (item.findtext("link") or "").strip()
            pub_date_str = item.findtext("pubDate")
            desc = (item.findtext("description") or "").strip()

            pub_dt: Optional[datetime] = None
            if pub_date_str:
                try:
                    pub_dt = parsedate_to_datetime(pub_date_str)
                except Exception:
                    pub_dt = None

            if title and link:
                items.append({
                    "source_id": source_id,
                    "title": title,
                    "url": link,
                    "published_time": pub_dt,
                    "description": desc,
                })
            if len(items) >= limit:
                break

        return items
