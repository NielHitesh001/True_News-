"""Unit tests for Collector Component (M2)."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import pytest

from newsx.collector import Collector
from newsx.registry import SourceRegistry
from newsx.schemas import ArticleType, SourceTier
from newsx.storage import Storage


@pytest.fixture
def collector_env(tmp_path):
    db_file = tmp_path / "test_newsx.db"
    audit_file = tmp_path / "test_audit.jsonl"
    raw_dir = tmp_path / "raw"
    storage = Storage(db_path=db_file, audit_path=audit_file)
    registry = SourceRegistry()
    collector = Collector(storage, registry, raw_dir=raw_dir)
    return collector, storage, raw_dir


def test_collector_ingest_raw_record(collector_env):
    collector, storage, raw_dir = collector_env

    now = datetime.now(timezone.utc)
    item = collector.ingest_raw_record(
        source_id="reuters",
        url="https://www.reuters.com/world/sample-story-1",
        title="Sample Test Headline",
        raw_text="This is raw article body text.",
        byline="John Reporter",
        published_time=now,
        article_type=ArticleType.REPORTING,
        custom_id="test-item-001",
    )

    assert item.id == "test-item-001"
    assert item.source_id == "reuters"

    # Verify persisted in database
    db_item = storage.get_item("test-item-001")
    assert db_item is not None
    assert db_item.title == "Sample Test Headline"

    # Verify raw payload archived
    raw_files = list(raw_dir.glob("test-item-001_*.json"))
    assert len(raw_files) == 1
    assert "This is raw article body text." in raw_files[0].read_text(encoding="utf-8")

    # Verify audit log recorded
    trail = storage.get_audit_trail_for_input("https://www.reuters.com/world/sample-story-1")
    assert len(trail) == 1
    assert trail[0].stage == "collection"


def test_collector_rss_parser(collector_env):
    collector, _, _ = collector_env

    sample_rss = b"""<?xml version="1.0" encoding="UTF-8"?>
    <rss version="2.0">
      <channel>
        <title>Test Feed</title>
        <item>
          <title>Test Article Title 1</title>
          <link>https://example.com/art-1</link>
          <pubDate>Mon, 10 Jun 2024 14:00:00 GMT</pubDate>
          <description>Summary of article 1</description>
        </item>
        <item>
          <title>Test Article Title 2</title>
          <link>https://example.com/art-2</link>
          <pubDate>Tue, 11 Jun 2024 15:30:00 GMT</pubDate>
          <description>Summary of article 2</description>
        </item>
      </channel>
    </rss>
    """

    parsed = collector.parse_rss_feed(sample_rss, source_id="ap-news", limit=5)
    assert len(parsed) == 2
    assert parsed[0]["title"] == "Test Article Title 1"
    assert parsed[0]["url"] == "https://example.com/art-1"
    assert parsed[0]["published_time"] is not None
