"""Unit tests for Deduplication and Syndication Detection (M2)."""

from __future__ import annotations

from datetime import datetime, timezone
import pytest

from newsx.deduplication import Deduplicator, calculate_jaccard_similarity, tokenize_text
from newsx.schemas import ArticleType, Item, Source, SourceTier
from newsx.storage import Storage


@pytest.fixture
def dedup_env(tmp_path):
    db_file = tmp_path / "test_newsx.db"
    audit_file = tmp_path / "test_audit.jsonl"
    storage = Storage(db_path=db_file, audit_path=audit_file)
    deduplicator = Deduplicator(storage, exact_threshold=0.90, republish_threshold=0.60)
    return deduplicator, storage


def test_jaccard_similarity_calculation():
    text_a = "The central bank lowered its key interest rate by 25 basis points on Thursday."
    text_b = "The central bank lowered its key interest rate by 25 basis points on Thursday."
    text_c = "A massive earthquake struck the northern coast triggering high waves."

    tokens_a = tokenize_text(text_a)
    tokens_b = tokenize_text(text_b)
    tokens_c = tokenize_text(text_c)

    assert calculate_jaccard_similarity(tokens_a, tokens_b) == 1.0
    assert calculate_jaccard_similarity(tokens_a, tokens_c) == 0.0


def test_deduplicator_republish_detection(dedup_env):
    deduplicator, storage = dedup_env

    # Source setup
    storage.save_source(Source(id="reuters", name="Reuters", tier=SourceTier.SECONDARY, ownership="Thomson", funding="Ads", region="Global", language="en", medium="wire"))
    storage.save_source(Source(id="the-guardian", name="The Guardian", tier=SourceTier.SECONDARY, ownership="Scott Trust", funding="Subs", region="Europe", language="en", medium="online"))

    now = datetime.now(timezone.utc)
    original_text = (
        "The European Central Bank lowered its key deposit facility rate by 25 basis points to 3.50 percent on Thursday. "
        "The Governing Council voted unanimously in favor of the reduction following a previous rate cut in June."
    )

    # Ingest original wire
    wire_item = Item(
        id="item-wire-01",
        source_id="reuters",
        url="https://reuters.com/ecb-cut-01",
        title="ECB cuts rates by 25 bps",
        cleaned_text=original_text,
        captured_time=now,
    )
    storage.save_item(wire_item)

    # Ingest syndicated article with minor outlet framing
    syndicated_text = (
        "The European Central Bank lowered its key deposit facility rate by 25 basis points to 3.50 percent on Thursday. "
        "The Governing Council voted unanimously in favor of the reduction following a previous rate cut in June, reports Reuters."
    )
    syndicated_item = Item(
        id="item-synd-01",
        source_id="the-guardian",
        url="https://guardian.com/ecb-cut-synd",
        title="ECB trims interest rates",
        cleaned_text=syndicated_text,
        captured_time=now,
    )

    processed = deduplicator.process_item(syndicated_item)

    # Should detect republishing
    assert processed.republished_from == "item-wire-01" or processed.duplicate_of == "item-wire-01"

    # Verify audit entry
    trail = storage.get_audit_trail_for_input("item-synd-01")
    assert len(trail) >= 1
    assert trail[0].stage == "deduplication"
