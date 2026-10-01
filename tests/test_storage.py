"""Unit tests for Storage and Database layer (M2)."""

from __future__ import annotations

from datetime import datetime, timezone
import pytest

from newsx.schemas import (
    ArticleType,
    AuditEntry,
    Event,
    Item,
    Passage,
    PassageType,
    Source,
    SourceStatus,
    SourceTier,
)
from newsx.storage import Storage


@pytest.fixture
def storage(tmp_path):
    db_file = tmp_path / "test_newsx.db"
    audit_file = tmp_path / "test_audit.jsonl"
    return Storage(db_path=db_file, audit_path=audit_file)


def test_storage_source_crud(storage):
    src = Source(
        id="test-src-1",
        name="Test Source",
        tier=SourceTier.SECONDARY,
        ownership="Test Co",
        funding="Subscriptions",
        region="North America",
        language="en",
        medium="wire",
        status=SourceStatus.ACTIVE,
    )
    storage.save_source(src)

    fetched = storage.get_source("test-src-1")
    assert fetched is not None
    assert fetched.name == "Test Source"
    assert fetched.tier == SourceTier.SECONDARY


def test_storage_item_and_passages(storage):
    src = Source(
        id="src-ap",
        name="Associated Press",
        tier=SourceTier.SECONDARY,
        ownership="Coop",
        funding="Fees",
        region="Global",
        language="en",
        medium="wire",
    )
    storage.save_source(src)

    now = datetime.now(timezone.utc)
    item = Item(
        id="item-test-01",
        source_id="src-ap",
        url="https://apnews.com/article/1",
        title="Breaking News Story",
        byline="Jane Doe",
        dateline="WASHINGTON",
        published_time=now,
        captured_time=now,
        edit_history=[],
        cleaned_text="First sentence. Second sentence.",
        original_language="en",
        article_type=ArticleType.REPORTING,
    )
    storage.save_item(item)

    fetched_item = storage.get_item("item-test-01")
    assert fetched_item is not None
    assert fetched_item.title == "Breaking News Story"

    passages = [
        Passage(id="psg-01", item_id="item-test-01", position=0, text="First sentence.", passage_type=PassageType.OBSERVED_EVENT),
        Passage(id="psg-02", item_id="item-test-01", position=1, text="Second sentence.", passage_type=PassageType.OBSERVED_EVENT),
    ]
    storage.save_passages(passages)

    fetched_psgs = storage.get_passages_for_item("item-test-01")
    assert len(fetched_psgs) == 2
    assert fetched_psgs[0].text == "First sentence."
    assert fetched_psgs[1].position == 1


def test_storage_audit_log(storage):
    now = datetime.now(timezone.utc)
    audit = AuditEntry(
        stage="normalization",
        stage_version="1.0.0",
        input_id="item-test-01",
        output_id=None,
        what_changed="Cleaned HTML boilerplate",
        when=now,
    )
    storage.write_audit_entry(audit)

    trail = storage.get_audit_trail_for_input("item-test-01")
    assert len(trail) == 1
    assert trail[0].stage == "normalization"
    assert trail[0].what_changed == "Cleaned HTML boilerplate"

    # Check JSONL file exists and is populated
    assert storage.audit_path.exists()
    assert "normalization" in storage.audit_path.read_text(encoding="utf-8")
