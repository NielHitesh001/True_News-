"""Unit tests for Normalizer & Sentence Segmentation (M2)."""

from __future__ import annotations

from datetime import datetime, timezone
import pytest

from newsx.normalizer import (
    Normalizer,
    clean_html_boilerplate,
    resolve_relative_dates,
    split_sentences_preserving_quotes,
)
from newsx.schemas import ArticleType, Item, PassageType, Source, SourceTier
from newsx.storage import Storage


def test_clean_html_boilerplate():
    html_raw = """
    <html>
      <head><title>Test News</title></head>
      <body>
        <nav><a href="/home">Home</a></nav>
        <header><h1>News Site Header</h1></header>
        <div class="ad-banner">Buy stuff now</div>
        <p>The National Transportation Safety Board issued its preliminary report on the collision.</p>
        <div class="social-share">Share on Twitter</div>
        <p>Six road maintenance workers tragically died in the bridge collapse.</p>
        <footer><p>Copyright 2024</p></footer>
      </body>
    </html>
    """
    cleaned = clean_html_boilerplate(html_raw)
    assert "The National Transportation Safety Board" in cleaned
    assert "Six road maintenance workers" in cleaned
    assert "Home" not in cleaned
    assert "Buy stuff now" not in cleaned
    assert "Copyright 2024" not in cleaned


def test_split_sentences_preserving_quotes():
    text = (
        '"This milestone restores commercial maritime traffic to one of America\'s vital ports," Maryland Governor Wes Moore said in a statement. '
        "Commercial cargo vessels began scheduled transit through the channel on Tuesday morning."
    )
    sentences = split_sentences_preserving_quotes(text)
    assert len(sentences) == 2
    assert sentences[0].startswith('"This milestone')
    assert sentences[0].endswith('in a statement.')
    assert sentences[1].startswith("Commercial cargo vessels")


def test_split_sentences_with_abbreviations():
    text = "The U.S. Coast Guard and Dr. Smith arrived at 08:00 a.m. to inspect the bridge. Crews removed 50,000 tons of debris."
    sentences = split_sentences_preserving_quotes(text)
    assert len(sentences) == 2
    assert "The U.S. Coast Guard and Dr. Smith arrived" in sentences[0]
    assert sentences[1] == "Crews removed 50,000 tons of debris."


def test_resolve_relative_dates():
    pub_dt = datetime(2024, 6, 11, 12, 0, 0, tzinfo=timezone.utc)
    text = "The committee voted on the budget today and met yesterday with stakeholders."
    resolved = resolve_relative_dates(text, pub_dt)
    assert "today (2024-06-11)" in resolved
    assert "yesterday (2024-06-10)" in resolved


def test_normalizer_pipeline(tmp_path):
    storage = Storage(db_path=tmp_path / "test.db", audit_path=tmp_path / "audit.jsonl")
    storage.save_source(Source(id="ap-news", name="AP", tier=SourceTier.SECONDARY, ownership="AP", funding="Fee", region="US", language="en", medium="wire"))
    normalizer = Normalizer(storage)

    pub_dt = datetime(2024, 5, 14, 14, 0, 0, tzinfo=timezone.utc)
    item = Item(
        id="item-test-norm",
        source_id="ap-news",
        url="https://apnews.com/story-norm",
        title="Key Bridge Report",
        published_time=pub_dt,
        captured_time=pub_dt,
        cleaned_text=(
            "<p>Total nonfarm payroll employment increased by 254,000 in September, and the unemployment rate changed little at 4.1 percent.</p>"
            "<p>\"We are making substantial progress on inflation,\" the official stated.</p>"
        ),
        article_type=ArticleType.REPORTING,
    )
    storage.save_item(item)

    passages = normalizer.normalize_item(item)
    assert len(passages) == 2
    assert passages[0].passage_type == PassageType.QUANTITATIVE
    assert passages[1].passage_type == PassageType.ATTRIBUTED_STATEMENT

    # Verify passages in DB
    db_psgs = storage.get_passages_for_item("item-test-norm")
    assert len(db_psgs) == 2
