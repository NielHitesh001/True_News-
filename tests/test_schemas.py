"""Unit tests for pipeline record schemas and gold-set models."""

from __future__ import annotations

from datetime import datetime, timezone
import pytest
from pydantic import ValidationError

from newsx.schemas import (
    RECORD_SCHEMA_VERSION,
    ArticleType,
    AuditEntry,
    Brief,
    BriefFact,
    ChangeRecord,
    Claim,
    ClaimStatus,
    ClaimType,
    ConfidenceTier,
    Event,
    GoldArticleLabel,
    GoldClaimLabel,
    GoldEventGroup,
    GoldPassageLabel,
    Item,
    LedgerEntry,
    Passage,
    PassageType,
    Source,
    SourceStatus,
    SourceTier,
)


def test_schema_version():
    assert RECORD_SCHEMA_VERSION == "1.0.0"


def test_source_model_valid():
    source = Source(
        id="src-reuters-01",
        name="Reuters",
        tier=SourceTier.SECONDARY,
        ownership="Thomson Reuters",
        funding="Commercial subscriptions and advertising",
        region="Global",
        language="en",
        medium="wire",
        leaning_notes="Centrist wire service",
        correction_history=["2024-01-05: corrected dateline"],
        status=SourceStatus.ACTIVE,
        full_text_retrievable=True,
        access_notes="Public wire excerpts available",
    )
    assert source.id == "src-reuters-01"
    assert source.tier == SourceTier.SECONDARY


def test_item_model_valid():
    now = datetime.now(timezone.utc)
    item = Item(
        id="item-001",
        source_id="src-reuters-01",
        url="https://www.reuters.com/world/news-item-001",
        title="Test Headline",
        byline="Test Author",
        dateline="WASHINGTON",
        published_time=now,
        captured_time=now,
        edit_history=[],
        cleaned_text="Test paragraph body.",
        original_language="en",
        article_type=ArticleType.REPORTING,
    )
    assert item.id == "item-001"
    assert item.article_type == ArticleType.REPORTING


def test_passage_model_valid():
    passage = Passage(
        id="psg-001",
        item_id="item-001",
        position=0,
        text="The president signed the executive order on Tuesday.",
        passage_type=PassageType.OBSERVED_EVENT,
    )
    assert passage.position == 0
    assert passage.passage_type == PassageType.OBSERVED_EVENT


def test_claim_model_valid():
    claim = Claim(
        id="claim-001",
        passage_id="psg-001",
        claim_type=ClaimType.EVENT,
        who="President",
        what="signed executive order",
        when="Tuesday",
        original_wording="The president signed the executive order on Tuesday.",
        neutralized_wording="The president signed the executive order on Tuesday.",
        changes=[],
        provenance_chain=["src-reuters-01", "item-001", "psg-001"],
        status=ClaimStatus.EXTRACTED,
    )
    assert claim.who == "President"
    assert claim.status == ClaimStatus.EXTRACTED


def test_audit_entry_valid():
    audit = AuditEntry(
        stage="normalization",
        stage_version="1.0.0",
        input_id="item-001",
        output_id="psg-001",
        what_changed="Segmented text into sentence passages",
        when=datetime.now(timezone.utc),
    )
    assert audit.stage == "normalization"


def test_gold_labels_validation():
    art = GoldArticleLabel(
        item_id="gold-art-001",
        article_type=ArticleType.REPORTING,
        evidence="Straight reporting",
        labeler="annotator_1",
        pass_id="A",
    )
    assert art.article_type == ArticleType.REPORTING

    psg = GoldPassageLabel(
        item_id="gold-art-001",
        passage_index=0,
        passage_type=PassageType.ATTRIBUTED_STATEMENT,
        feeds_fact_base=True,
        notes="",
        labeler="annotator_1",
        pass_id="A",
    )
    assert psg.feeds_fact_base is True

    claim = GoldClaimLabel(
        item_id="gold-art-001",
        passage_index=0,
        claim_text="The board issued report Tuesday.",
        span_start=0,
        span_end=33,
        claim_type=ClaimType.STATEMENT,
        attribution_layer="assertion",
        speaker="The board",
        anonymous_attribution=False,
        labeler="annotator_1",
        pass_id="A",
    )
    assert claim.span_start == 0


def test_invalid_article_type_raises():
    with pytest.raises(ValidationError):
        GoldArticleLabel(
            item_id="gold-art-001",
            article_type="invalid_type",  # type: ignore
            evidence="none",
            labeler="ann",
            pass_id="A",
        )
