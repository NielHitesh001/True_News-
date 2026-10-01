"""Unit tests for Claim Extractor (M4)."""

from __future__ import annotations

import pytest
from datetime import datetime, timezone
from newsx.extractor import ClaimExtractor
from newsx.schemas import ArticleType, ClaimStatus, ClaimType, Item, Passage, PassageType, Source, SourceTier
from newsx.storage import Storage


@pytest.fixture
def extractor_env(tmp_path):
    storage = Storage(db_path=tmp_path / "test.db", audit_path=tmp_path / "audit.jsonl")
    storage.save_source(Source(id="reuters", name="Reuters", tier=SourceTier.SECONDARY, ownership="Thomson", funding="Ads", region="Global", language="en", medium="wire"))
    extractor = ClaimExtractor(storage)
    return extractor, storage


def test_extractor_attributed_statement(extractor_env):
    extractor, storage = extractor_env

    pub_dt = datetime(2024, 9, 12, 12, 0, tzinfo=timezone.utc)
    item = Item(
        id="item-test-ecb",
        source_id="reuters",
        url="https://reuters.com/ecb-1",
        title="ECB Rate Decision",
        published_time=pub_dt,
        captured_time=pub_dt,
        cleaned_text="ECB President Christine Lagarde told a press conference that inflation is expected to decline.",
        article_type=ArticleType.REPORTING,
    )
    storage.save_item(item)

    passage = Passage(
        id="psg-test-01",
        item_id="item-test-ecb",
        position=0,
        text="ECB President Christine Lagarde told a press conference that inflation is expected to decline.",
        passage_type=PassageType.ATTRIBUTED_STATEMENT,
    )
    storage.save_passages([passage])

    claims = extractor.extract_claims_from_passage(item, passage)
    assert len(claims) == 1

    c = claims[0]
    assert c.claim_type == ClaimType.STATEMENT
    assert c.attribution_speaker == "ECB President Christine Lagarde"
    assert c.attribution_anonymous is False
    assert c.status == ClaimStatus.EXTRACTED
    assert c.provenance_chain == ["reuters", "item-test-ecb", "psg-test-01"]


def test_extractor_quantitative_slots(extractor_env):
    extractor, storage = extractor_env

    pub_dt = datetime(2024, 10, 4, 12, 30, tzinfo=timezone.utc)
    item = Item(
        id="item-test-bls",
        source_id="reuters",
        url="https://reuters.com/jobs-1",
        title="Jobs Report",
        published_time=pub_dt,
        captured_time=pub_dt,
        cleaned_text="Total nonfarm payroll employment increased by 254,000 in September.",
        article_type=ArticleType.REPORTING,
    )
    storage.save_item(item)

    passage = Passage(
        id="psg-test-02",
        item_id="item-test-bls",
        position=0,
        text="Total nonfarm payroll employment increased by 254,000 in September.",
        passage_type=PassageType.QUANTITATIVE,
    )
    storage.save_passages([passage])

    claims = extractor.extract_claims_from_passage(item, passage)
    assert len(claims) == 1

    c = claims[0]
    assert c.claim_type == ClaimType.QUANTITY
    assert c.how_much == "254,000"
    assert c.when == "September"
    assert c.status == ClaimStatus.EXTRACTED


def test_extractor_opinion_article_produces_no_claims(extractor_env):
    extractor, storage = extractor_env

    pub_dt = datetime(2024, 7, 18, 12, 0, tzinfo=timezone.utc)
    item = Item(
        id="item-test-op",
        source_id="reuters",
        url="https://reuters.com/opinion-1",
        title="Opinion Column",
        published_time=pub_dt,
        captured_time=pub_dt,
        cleaned_text="The committee voted 6-3 yesterday.",
        article_type=ArticleType.OPINION,
    )
    storage.save_item(item)

    passage = Passage(
        id="psg-test-03",
        item_id="item-test-op",
        position=0,
        text="The committee voted 6-3 yesterday.",
        passage_type=PassageType.QUANTITATIVE,
    )
    storage.save_passages([passage])

    # Should produce 0 claims because article is Opinion
    claims = extractor.process_item_passages(item, [passage])
    assert len(claims) == 0
