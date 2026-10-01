"""Unit tests for Event Brief Generation and Rendering (M7)."""

from __future__ import annotations

from datetime import datetime, timezone
import pytest

from newsx.brief import BriefGenerator
from newsx.corroboration import Corroborator
from newsx.presenter import ConsoleBriefRenderer, HtmlBriefRenderer, MarkdownBriefRenderer
from newsx.registry import SourceRegistry
from newsx.schemas import (
    ArticleType,
    BriefFact,
    Claim,
    ClaimStatus,
    ClaimType,
    ConfidenceTier,
    DisputedPoint,
    Item,
    LedgerEntry,
    Passage,
    PassageType,
    SourceTier,
    TimelineEntry,
)
from newsx.storage import Storage


@pytest.fixture
def brief_env(tmp_path):
    storage = Storage(db_path=tmp_path / "test.db", audit_path=tmp_path / "audit.jsonl")
    registry = SourceRegistry()
    for s in registry.all_sources():
        storage.save_source(s)
    generator = BriefGenerator(storage, registry)
    return generator, storage, registry


def test_brief_generator_ranking_tier1_over_tier2(brief_env):
    generator, storage, registry = brief_env
    event_id = "test-event-01"

    item_prim = Item(
        id="it-prim",
        source_id="ntsb-gov",
        url="https://ntsb.gov/1",
        title="Official Accident Report",
        cleaned_text="The NTSB reported six workers died in the collapse.",
        captured_time="2024-03-26T00:00:00Z",  # type: ignore
    )
    storage.save_item(item_prim)

    p_prim = Passage(
        id="p-prim",
        item_id="it-prim",
        position=0,
        text="The NTSB reported six workers died in the collapse.",
        passage_type=PassageType.QUANTITATIVE,
    )
    storage.save_passage(p_prim)

    c_prim = Claim(
        id="c-prim",
        passage_id="p-prim",
        claim_type=ClaimType.QUANTITY,
        what="died in collapse",
        how_much="six workers",
        original_wording="The NTSB reported six workers died in the collapse.",
        provenance_chain=["ntsb-gov", "it-prim", "p-prim"],
        status=ClaimStatus.EXTRACTED,
    )
    storage.save_claim(c_prim)

    # Save ledger entries: one Tier 2, one Tier 1
    entry_tier2 = LedgerEntry(
        id="l-2",
        canonical_claim="Search and rescue teams deployed twelve boats.",
        equivalent_claim_ids=[],
        supporting_source_ids=["reuters", "associated-press", "the-guardian"],
        independent_origin_count=3,
        confidence_tier=ConfidenceTier.INDEPENDENTLY_CORROBORATED,
    )
    entry_tier1 = LedgerEntry(
        id="l-1",
        canonical_claim="Six workers died in the collapse.",
        equivalent_claim_ids=["c-prim"],
        supporting_source_ids=["ntsb-gov"],
        independent_origin_count=1,
        confidence_tier=ConfidenceTier.PRIMARY_CONFIRMED,
    )
    storage.save_ledger_entry(entry_tier2)
    storage.save_ledger_entry(entry_tier1)

    brief = generator.generate_brief(event_id, event_title="Key Bridge Collapse Report")
    assert len(brief.core_facts) == 2
    # Tier 1 should be ranked before Tier 2
    assert brief.core_facts[0].tier == ConfidenceTier.PRIMARY_CONFIRMED
    assert brief.core_facts[0].claim_id == "l-1"
    assert brief.core_facts[1].tier == ConfidenceTier.INDEPENDENTLY_CORROBORATED


def test_brief_generator_disputed_points_paired(brief_env):
    generator, storage, registry = brief_env
    event_id = "test-event-dispute"

    item_a = Item(
        id="it-a",
        source_id="reuters",
        url="https://reuters.com/1",
        title="Disputed Action",
        cleaned_text="Coast guard vessel rammed supply ship.",
        captured_time="2024-06-17T00:00:00Z",  # type: ignore
    )
    item_b = Item(
        id="it-b",
        source_id="ap-news",
        url="https://apnews.com/1",
        title="Disputed Action Response",
        cleaned_text="Supply ship illegally intruded into sovereign waters.",
        captured_time="2024-06-17T00:00:00Z",  # type: ignore
    )
    storage.save_item(item_a)
    storage.save_item(item_b)

    p_a = Passage(id="p-a", item_id="it-a", position=0, text="Coast guard vessel rammed supply ship.", passage_type=PassageType.OBSERVED_EVENT)
    p_b = Passage(id="p-b", item_id="it-b", position=0, text="Supply ship illegally intruded into sovereign waters.", passage_type=PassageType.OBSERVED_EVENT)
    storage.save_passage(p_a)
    storage.save_passage(p_b)

    c_a = Claim(id="c-a", passage_id="p-a", claim_type=ClaimType.EVENT, what="rammed supply ship", original_wording="Coast guard vessel rammed supply ship.", provenance_chain=["reuters", "it-a", "p-a"])
    c_b = Claim(id="c-b", passage_id="p-b", claim_type=ClaimType.EVENT, what="intruded into sovereign waters", original_wording="Supply ship illegally intruded into sovereign waters.", provenance_chain=["ap-news", "it-b", "p-b"])
    storage.save_claim(c_a)
    storage.save_claim(c_b)

    l_a = LedgerEntry(
        id="l-a",
        canonical_claim="Coast guard vessel rammed supply ship.",
        equivalent_claim_ids=["c-a"],
        supporting_source_ids=["reuters"],
        independent_origin_count=1,
        contradictions=["l-b"],
        confidence_tier=ConfidenceTier.DISPUTED,
    )
    l_b = LedgerEntry(
        id="l-b",
        canonical_claim="Supply ship illegally intruded into sovereign waters.",
        equivalent_claim_ids=["c-b"],
        supporting_source_ids=["ap-news"],
        independent_origin_count=1,
        contradictions=["l-a"],
        confidence_tier=ConfidenceTier.DISPUTED,
    )
    storage.save_ledger_entry(l_a)
    storage.save_ledger_entry(l_b)

    brief = generator.generate_brief(event_id, event_title="Second Thomas Shoal Incident")
    assert len(brief.disputed_points) == 1
    dp = brief.disputed_points[0]
    assert isinstance(dp, DisputedPoint)
    assert len(dp.claims) == 2
    assert "Maritime" in dp.topic or "Collision" in dp.topic


def test_markdown_and_html_renderers(brief_env):
    generator, storage, registry = brief_env
    event_id = "test-event-render"

    item = Item(
        id="it-1",
        source_id="reuters",
        url="https://reuters.com/test",
        title="Test Event Story",
        cleaned_text="The committee convened at 9:00 a.m. on Tuesday.",
        captured_time="2024-01-01T00:00:00Z",  # type: ignore
    )
    storage.save_item(item)

    p = Passage(id="p-1", item_id="it-1", position=0, text="The committee convened at 9:00 a.m. on Tuesday.", passage_type=PassageType.OBSERVED_EVENT)
    storage.save_passage(p)

    c = Claim(
        id="c-1",
        passage_id="p-1",
        claim_type=ClaimType.EVENT,
        what="committee convened",
        when="Tuesday",
        original_wording="The committee convened at 9:00 a.m. on Tuesday.",
        neutralized_wording="The committee convened at 9:00 a.m. on Tuesday.",
        provenance_chain=["reuters", "it-1", "p-1"],
    )
    storage.save_claim(c)

    l = LedgerEntry(
        id="l-1",
        canonical_claim="The committee convened at 9:00 a.m. on Tuesday.",
        equivalent_claim_ids=["c-1"],
        supporting_source_ids=["reuters"],
        independent_origin_count=1,
        confidence_tier=ConfidenceTier.INDEPENDENTLY_CORROBORATED,
    )
    storage.save_ledger_entry(l)

    brief = generator.generate_brief(event_id, event_title="Committee Hearing")

    # Render Markdown
    md = MarkdownBriefRenderer().render(brief)
    assert "# Committee Hearing" in md
    assert "## 1. Core Verified Facts" in md
    assert "https://reuters.com/test" in md
    assert "## 6. Source Transparency & Origin Audit" in md

    # Render HTML
    html = HtmlBriefRenderer().render(brief)
    assert "<title>Committee Hearing - Neutral Event Brief</title>" in html
    assert "Tier 2: Corroborated" in html
    assert "<details class=\"drill-down\">" in html
    assert "reuters" in html

    # Render Console
    console_out = ConsoleBriefRenderer().render(brief)
    assert "EVENT BRIEF: Committee Hearing" in console_out
    assert "[1. CORE VERIFIED FACTS]" in console_out
