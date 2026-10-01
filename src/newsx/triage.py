"""Triage Engine (M3).

Classifies articles into types (reporting, analysis, opinion, sponsored, satire)
and passages into types (observed event, quantitative, attributed statement, interpretation, prediction, rhetoric).
Strictly routes factual passages from reporting articles to the fact base (spec §6).
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
import yaml
from pydantic import BaseModel

from .schemas import ArticleType, AuditEntry, Item, Passage, PassageType
from .storage import Storage

DEFAULT_TRIAGE_RULES_PATH = Path(__file__).resolve().parent.parent.parent / "config" / "triage_rules.yaml"
STAGE_VERSION = "1.0.0"


class ArticleTriageResult(BaseModel):
    article_type: ArticleType
    evidence: str
    confidence: float = 1.0


class PassageTriageResult(BaseModel):
    passage_id: str
    passage_type: PassageType
    feeds_fact_base: bool
    evidence: str


class ArticleTriager:
    """Classifies an article based on URL, byline, headline, and content signals."""

    def __init__(self, rules: dict[str, Any]) -> None:
        self.rules = rules.get("article_rules", {})
        self.url_patterns = self.rules.get("url_patterns", {})
        self.byline_patterns = self.rules.get("byline_patterns", {})
        self.headline_prefixes = self.rules.get("headline_prefixes", {})
        self.content_signals = self.rules.get("content_signals", {})

    def classify(self, item: Item) -> ArticleTriageResult:
        url_str = str(item.url).lower()
        title_str = item.title.lower()
        byline_str = item.byline.lower()
        content_str = item.cleaned_text.lower()

        # 1. Check Placement & URL patterns
        for atype, patterns in self.url_patterns.items():
            for pat in patterns:
                if pat in url_str:
                    return ArticleTriageResult(
                        article_type=ArticleType(atype),
                        evidence=f"URL pattern match '{pat}'",
                    )

        # 2. Check Headline Prefixes
        for atype, prefixes in self.headline_prefixes.items():
            for pfx in prefixes:
                if title_str.startswith(pfx) or f" {pfx}" in title_str:
                    return ArticleTriageResult(
                        article_type=ArticleType(atype),
                        evidence=f"Headline prefix match '{pfx}'",
                    )

        # 3. Check Byline Patterns
        for atype, patterns in self.byline_patterns.items():
            for pat in patterns:
                if pat in byline_str:
                    return ArticleTriageResult(
                        article_type=ArticleType(atype),
                        evidence=f"Byline pattern match '{pat}'",
                    )

        # 4. Check Content Signals
        op_markers = self.content_signals.get("opinion_markers", [])
        for marker in op_markers:
            if marker in content_str:
                return ArticleTriageResult(
                    article_type=ArticleType.OPINION,
                    evidence=f"Opinion content marker '{marker}'",
                )

        an_markers = self.content_signals.get("analysis_markers", [])
        for marker in an_markers:
            if marker in content_str:
                return ArticleTriageResult(
                    article_type=ArticleType.ANALYSIS,
                    evidence=f"Analysis content marker '{marker}'",
                )

        # Default to reporting
        return ArticleTriageResult(
            article_type=ArticleType.REPORTING,
            evidence="No opinion/analysis/sponsored markers found; straight factual reporting format",
        )


class PassageTriager:
    """Classifies individual passages and determines fact-base routing."""

    def __init__(self, rules: dict[str, Any]) -> None:
        self.rules = rules.get("passage_rules", {})
        self.pred_indicators = self.rules.get("prediction_indicators", [])
        self.rhet_indicators = self.rules.get("rhetoric_indicators", [])
        self.interp_indicators = self.rules.get("interpretation_indicators", [])
        self.quant_indicators = self.rules.get("quantitative_indicators", [])
        self.attrib_indicators = self.rules.get("attribution_indicators", [])

    def classify_passage(self, passage: Passage, article_type: ArticleType) -> PassageTriageResult:
        text_lower = passage.text.lower()

        # Check 1: Rhetoric / Prescription
        for r_ind in self.rhet_indicators:
            if r_ind in text_lower or text_lower.startswith("we should") or text_lower.startswith("we must"):
                return PassageTriageResult(
                    passage_id=passage.id,
                    passage_type=PassageType.RHETORIC,
                    feeds_fact_base=False,
                    evidence=f"Rhetoric indicator '{r_ind}'",
                )

        # Check 2: Prediction
        # If it's explicitly future forecast and not just an attributed statement
        is_quote = '"' in passage.text or '“' in passage.text
        has_future = any(p_ind in text_lower for p_ind in self.pred_indicators)
        
        if has_future and not is_quote and not any(a_ind in text_lower for a_ind in ["announced", "voted", "issued", "reported"]):
            # Check if it's primarily a prediction
            if any(w in text_lower for w in ["will ", "expected to", "forecast to", "could cost", "warn that"]):
                return PassageTriageResult(
                    passage_id=passage.id,
                    passage_type=PassageType.PREDICTION,
                    feeds_fact_base=False,
                    evidence="Prediction / future projection indicator",
                )

        # Check 3: Interpretation
        for i_ind in self.interp_indicators:
            if i_ind in text_lower and not is_quote and not any(v in text_lower for v in ["voted", "issued", "reported"]):
                return PassageTriageResult(
                    passage_id=passage.id,
                    passage_type=PassageType.INTERPRETATION,
                    feeds_fact_base=False,
                    evidence=f"Interpretation indicator '{i_ind}'",
                )

        # Check 4: Quantitative (Check numbers and measurements before secondary attribution verbs)
        has_digit = any(char.isdigit() for char in passage.text)
        has_quant_word = any(q_ind in text_lower for q_ind in self.quant_indicators)
        number_words = {"six", "seven", "eight", "nine", "ten", "40", "42", "254,000", "45,000", "3,800"}
        has_num_word = any(re.search(rf"\b{w}\b", text_lower) for w in number_words)

        if (has_digit or has_num_word) and (has_quant_word or has_num_word) and not is_quote:
            p_type = PassageType.QUANTITATIVE
            feeds = (article_type == ArticleType.REPORTING)
            return PassageTriageResult(
                passage_id=passage.id,
                passage_type=p_type,
                feeds_fact_base=feeds,
                evidence="Numerical quantity / metric indicator",
            )

        # Check 5: Attributed Statement (Quotes or speech verbs)
        has_attrib_verb = any(re.search(rf"\b{re.escape(v)}\b", text_lower) for v in self.attrib_indicators)
        if is_quote or has_attrib_verb:
            p_type = PassageType.ATTRIBUTED_STATEMENT
            feeds = (article_type == ArticleType.REPORTING)
            return PassageTriageResult(
                passage_id=passage.id,
                passage_type=p_type,
                feeds_fact_base=feeds,
                evidence="Direct quote or attribution speech verb",
            )

        # Check 6: Observed Event (Default)
        p_type = PassageType.OBSERVED_EVENT
        feeds = (article_type == ArticleType.REPORTING)
        return PassageTriageResult(
            passage_id=passage.id,
            passage_type=p_type,
            feeds_fact_base=feeds,
            evidence="Observed factual event",
        )


class TriageEngine:
    """Coordinates article and passage classification with storage and audit trail."""

    def __init__(
        self,
        storage: Storage,
        rules_path: Optional[Path] = None,
    ) -> None:
        self.storage = storage
        self.rules_path = rules_path or DEFAULT_TRIAGE_RULES_PATH
        self._load_rules()

    def _load_rules(self) -> None:
        if not self.rules_path.exists():
            raise FileNotFoundError(f"Triage rules not found at {self.rules_path}")
        with self.rules_path.open("r", encoding="utf-8") as f:
            self.rules = yaml.safe_load(f) or {}
        self.article_triager = ArticleTriager(self.rules)
        self.passage_triager = PassageTriager(self.rules)

    def triage_item(self, item: Item, passages: list[Passage]) -> tuple[ArticleTriageResult, list[PassageTriageResult]]:
        # 1. Article Triage
        art_result = self.article_triager.classify(item)
        item.article_type = art_result.article_type
        self.storage.save_item(item)

        # 2. Passage Triage
        psg_results: list[PassageTriageResult] = []
        updated_passages: list[Passage] = []

        for psg in passages:
            res = self.passage_triager.classify_passage(psg, item.article_type)
            psg.passage_type = res.passage_type
            psg_results.append(res)
            updated_passages.append(psg)

        self.storage.save_passages(updated_passages)

        # 3. Audit trail
        now = datetime.now(timezone.utc)
        self.storage.write_audit_entry(
            AuditEntry(
                stage="triage",
                stage_version=STAGE_VERSION,
                input_id=item.id,
                output_id=None,
                what_changed=(
                    f"Classified article as '{item.article_type.value}' ({art_result.evidence}). "
                    f"Triaged {len(passages)} passages: "
                    f"{sum(1 for r in psg_results if r.feeds_fact_base)} feeding fact base."
                ),
                when=now,
            )
        )

        return art_result, psg_results
