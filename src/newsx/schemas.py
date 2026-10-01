"""Record schemas for the news extraction pipeline.

Every stage communicates only through these records (spec §4/§5).
All models are versioned: bump RECORD_SCHEMA_VERSION on any shape change and record
the version in every file written to data/.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional, Union

from pydantic import BaseModel, Field, HttpUrl

RECORD_SCHEMA_VERSION = "1.0.0"


# ---------------------------------------------------------------- enums

class SourceTier(str, Enum):
    PRIMARY = "primary"      # official records, filings, transcripts
    SECONDARY = "secondary"  # wires and original reporting
    TERTIARY = "tertiary"    # aggregators and commentary (excluded by owner rule)


class SourceStatus(str, Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    RETIRED = "retired"


class ArticleType(str, Enum):
    REPORTING = "reporting"
    ANALYSIS = "analysis"
    OPINION = "opinion"
    SPONSORED = "sponsored"
    SATIRE = "satire"


class PassageType(str, Enum):
    OBSERVED_EVENT = "observed event"
    QUANTITATIVE = "quantitative"
    ATTRIBUTED_STATEMENT = "attributed statement"
    INTERPRETATION = "interpretation"
    PREDICTION = "prediction"
    RHETORIC = "rhetoric"


class ClaimType(str, Enum):
    EVENT = "event"
    QUANTITY = "quantity"
    STATEMENT = "statement"
    CAUSAL = "causal"


class ClaimStatus(str, Enum):
    EXTRACTED = "extracted"
    NEUTRALIZED = "neutralized"
    FLAGGED = "flagged"        # meaning-preservation check failed; original kept
    REJECTED = "rejected"      # not anchorable; never enters the fact base


class ConfidenceTier(int, Enum):
    PRIMARY_CONFIRMED = 1
    INDEPENDENTLY_CORROBORATED = 2
    SINGLE_SOURCE = 3
    DISPUTED = 4
    UNVERIFIED = 5             # separate section only


# ---------------------------------------------------------------- M0 gold-set labels

class GoldArticleLabel(BaseModel):
    """Human label for one article in the gold set (M0/M3 target)."""

    item_id: str
    article_type: ArticleType
    evidence: str = Field(description="signal phrases / section / byline that justify the label")
    labeler: str
    pass_id: str  # e.g. "A" or "B" — supports blind double-pass agreement


class GoldPassageLabel(BaseModel):
    item_id: str
    passage_index: int
    passage_type: PassageType
    feeds_fact_base: bool
    notes: str = ""
    labeler: str
    pass_id: str


class GoldClaimLabel(BaseModel):
    item_id: str
    passage_index: int
    claim_text: str                      # atomic proposition, exact span in source text
    span_start: int                      # char offset in the passage text
    span_end: int
    claim_type: ClaimType
    attribution_layer: Optional[str] = Field(
        default=None,
        description="'assertion' (that it was said) or 'content' (what was said); null if unattributed",
    )
    speaker: Optional[str] = None
    anonymous_attribution: bool = False
    labeler: str
    pass_id: str


class GoldEventGroup(BaseModel):
    """Human grouping of items into one event (M6 target)."""

    event_label: str
    event_kind: str = Field(description="hard-fact | numeric | contested")
    member_item_ids: list[str]
    labeler: str
    pass_id: str


# ---------------------------------------------------------------- pipeline records (spec §5)

class Source(BaseModel):
    id: str
    name: str
    tier: SourceTier
    ownership: str
    funding: str
    region: str
    language: str
    medium: str                       # wire / print / broadcast / online / official
    leaning_notes: str = ""
    correction_history: list[str] = []
    status: SourceStatus = SourceStatus.ACTIVE
    full_text_retrievable: bool = True
    access_notes: str = ""            # paywall, robots, terms limits — never work around


class Item(BaseModel):
    id: str
    source_id: str
    url: HttpUrl
    title: str
    byline: str = ""
    dateline: str = ""
    published_time: Optional[datetime] = None
    captured_time: datetime
    edit_history: list[datetime] = []
    cleaned_text: str = ""
    original_language: str = "en"
    article_type: ArticleType = ArticleType.REPORTING
    duplicate_of: Optional[str] = None        # item id this duplicates
    republished_from: Optional[str] = None    # item id it was republished from


class Passage(BaseModel):
    id: str
    item_id: str
    position: int
    text: str
    passage_type: PassageType


class ChangeRecord(BaseModel):
    original_span: str
    replacement: str
    category: str      # intensifier | emotive adjective | charged verb | scare quote |
                       # loaded label | insinuation | other
    rationale: str


class Claim(BaseModel):
    id: str
    passage_id: str
    claim_type: ClaimType
    who: Optional[str] = None
    what: Optional[str] = None
    when: Optional[str] = None
    where: Optional[str] = None
    how_much: Optional[str] = None
    attribution_speaker: Optional[str] = None
    attribution_anonymous: bool = False
    original_wording: str
    neutralized_wording: Optional[str] = None
    changes: list[ChangeRecord] = []
    provenance_chain: list[str] = []   # source id -> item id -> passage id
    status: ClaimStatus = ClaimStatus.EXTRACTED


class Event(BaseModel):
    id: str
    label: str
    member_item_ids: list[str]
    time_span: tuple[Optional[datetime], Optional[datetime]]
    claim_ids: list[str]


class LedgerEntry(BaseModel):
    id: str
    canonical_claim: str
    equivalent_claim_ids: list[str]
    supporting_source_ids: list[str]
    independent_origin_count: int
    contradictions: list[str] = []     # ledger entry ids it contradicts
    omissions: list[str] = []          # facts present elsewhere, absent here
    confidence_tier: ConfidenceTier
    change_history: list[str] = []


class BriefFact(BaseModel):
    claim_id: str
    tier: ConfidenceTier
    independent_source_count: int
    text: Optional[str] = None
    original_text: Optional[str] = None
    attribution_speaker: Optional[str] = None
    attribution_anonymous: bool = False
    supporting_source_ids: list[str] = []
    item_urls: list[str] = []
    passage_ids: list[str] = []
    changes: list[ChangeRecord] = []


class DisputedPoint(BaseModel):
    topic: str
    claims: list[BriefFact] = []
    explanation: str


class TimelineEntry(BaseModel):
    timestamp_str: str
    claim_id: str
    description: str
    source_ids: list[str] = []
    tier: ConfidenceTier


class SourceLedgerItem(BaseModel):
    source_id: str
    name: str
    tier: SourceTier
    independent_origin: bool
    republished_from: Optional[str] = None


class Brief(BaseModel):
    event_id: str
    neutral_headline: str
    core_facts: list[BriefFact]
    single_source_facts: list[BriefFact] = []
    disputed_points: list[Union[DisputedPoint, str]] = []
    unknowns: list[str] = []
    timeline: list[Union[TimelineEntry, str]] = []
    source_links: list[Union[HttpUrl, str]] = []
    source_ledger: list[SourceLedgerItem] = []
    diversity_compliant: bool = True
    diversity_deficiencies: list[str] = []
    version_history: list[str] = []


class BriefDiff(BaseModel):
    event_id: str
    previous_version: str
    current_version: str
    new_core_facts: list[str] = []
    promoted_facts: list[str] = []
    new_disputes: list[str] = []
    retracted_claims: list[str] = []
    summary_of_changes: str = ""


class AuditEntry(BaseModel):
    """Every stage writes one per record processed (spec §4)."""

    stage: str
    stage_version: str
    input_id: str
    output_id: Optional[str]
    what_changed: str
    when: datetime
    model_id: Optional[str] = None     # set whenever a model was involved
    model_settings_hash: Optional[str] = None
