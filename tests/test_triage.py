"""Unit tests for Triage Engine (M3)."""

from __future__ import annotations

import pytest
from datetime import datetime, timezone
from newsx.schemas import ArticleType, Item, Passage, PassageType, Source, SourceTier
from newsx.storage import Storage
from newsx.triage import ArticleTriager, PassageTriager, TriageEngine, DEFAULT_TRIAGE_RULES_PATH
import yaml


@pytest.fixture
def triage_rules():
    with DEFAULT_TRIAGE_RULES_PATH.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def test_article_triager_opinion_url(triage_rules):
    triager = ArticleTriager(triage_rules)
    item = Item(
        id="test-op-1",
        source_id="the-guardian",
        url="https://www.theguardian.com/commentisfree/2024/jul/18/housing-crisis",
        title="Housing Crisis Failure",
        cleaned_text="The government policy is failing.",
        captured_time=datetime.now(timezone.utc),
    )
    res = triager.classify(item)
    assert res.article_type == ArticleType.OPINION


def test_article_triager_analysis_headline(triage_rules):
    triager = ArticleTriager(triage_rules)
    item = Item(
        id="test-an-1",
        source_id="reuters",
        url="https://www.reuters.com/markets/ecb-rate-cut-explainer",
        title="Analysis: Why the ECB cut interest rates",
        cleaned_text="The decision signals a new monetary phase.",
        captured_time=datetime.now(timezone.utc),
    )
    res = triager.classify(item)
    assert res.article_type == ArticleType.ANALYSIS


def test_article_triager_sponsored_content(triage_rules):
    triager = ArticleTriager(triage_rules)
    item = Item(
        id="test-sp-1",
        source_id="reuters",
        url="https://www.reuters.com/sponsored/brand-studio/innovation-2024",
        title="Future of Clean Energy",
        byline="Brand Studio",
        cleaned_text="Discover our new commercial solutions.",
        captured_time=datetime.now(timezone.utc),
    )
    res = triager.classify(item)
    assert res.article_type == ArticleType.SPONSORED


def test_passage_triager_rhetoric_routing(triage_rules):
    triager = PassageTriager(triage_rules)
    psg = Passage(
        id="psg-rhet-1",
        item_id="test-op-1",
        position=0,
        text="This disastrous deregulation is an act of pure vandalism that must be resisted.",
        passage_type=PassageType.OBSERVED_EVENT,
    )
    res = triager.classify_passage(psg, ArticleType.OPINION)
    assert res.passage_type == PassageType.RHETORIC
    assert res.feeds_fact_base is False


def test_passage_triager_quantitative_reporting(triage_rules):
    triager = PassageTriager(triage_rules)
    psg = Passage(
        id="psg-quant-1",
        item_id="test-rep-1",
        position=0,
        text="Total nonfarm payroll employment increased by 254,000 in September.",
        passage_type=PassageType.OBSERVED_EVENT,
    )
    res = triager.classify_passage(psg, ArticleType.REPORTING)
    assert res.passage_type == PassageType.QUANTITATIVE
    assert res.feeds_fact_base is True


def test_passage_triager_analysis_excluded_from_fact_base(triage_rules):
    triager = PassageTriager(triage_rules)
    psg = Passage(
        id="psg-an-psg-1",
        item_id="test-an-1",
        position=0,
        text="The court fined the company €2.42 billion.",
        passage_type=PassageType.OBSERVED_EVENT,
    )
    # Even if passage looks quantitative, analysis articles do not feed the fact base
    res = triager.classify_passage(psg, ArticleType.ANALYSIS)
    assert res.feeds_fact_base is False
