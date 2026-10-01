"""News extraction pipeline package."""

from .collector import Collector
from .continuous import ContinuousEngine, EventMatcher
from .corroboration import Corroborator, IndependentOriginResolver
from .deduplication import Deduplicator
from .extractor import ClaimExtractor
from .models import BaseModelClient, DeterministicExtractorClient, OllamaModelClient
from .neutralizer import MeaningChecker, Neutralizer
from .normalizer import Normalizer
from .pipeline import Pipeline
from .registry import DiversityChecker, DiversityEvaluationResult, EventQuota, SourceRegistry
from .schemas import (
    RECORD_SCHEMA_VERSION,
    ArticleType,
    AuditEntry,
    Brief,
    BriefDiff,
    BriefFact,
    ChangeRecord,
    Claim,
    ClaimStatus,
    ClaimType,
    ConfidenceTier,
    DisputedPoint,
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
    SourceLedgerItem,
    SourceStatus,
    SourceTier,
    TimelineEntry,
)
from .storage import Storage
from .transparency import generate_transparency_html, render_transparency_page
from .triage import ArticleTriager, ArticleTriageResult, PassageTriager, PassageTriageResult, TriageEngine

__all__ = [
    "RECORD_SCHEMA_VERSION",
    "SourceTier",
    "SourceStatus",
    "ArticleType",
    "PassageType",
    "ClaimType",
    "ClaimStatus",
    "ConfidenceTier",
    "GoldArticleLabel",
    "GoldPassageLabel",
    "GoldClaimLabel",
    "GoldEventGroup",
    "Source",
    "Item",
    "Passage",
    "ChangeRecord",
    "Claim",
    "Event",
    "LedgerEntry",
    "BriefFact",
    "DisputedPoint",
    "TimelineEntry",
    "SourceLedgerItem",
    "Brief",
    "BriefDiff",
    "AuditEntry",
    "SourceRegistry",
    "DiversityChecker",
    "EventQuota",
    "DiversityEvaluationResult",
    "generate_transparency_html",
    "render_transparency_page",
    "Storage",
    "Collector",
    "Deduplicator",
    "Normalizer",
    "Pipeline",
    "ArticleTriager",
    "ArticleTriageResult",
    "PassageTriager",
    "PassageTriageResult",
    "TriageEngine",
    "BaseModelClient",
    "DeterministicExtractorClient",
    "OllamaModelClient",
    "ClaimExtractor",
    "Neutralizer",
    "MeaningChecker",
    "Corroborator",
    "IndependentOriginResolver",
    "ContinuousEngine",
    "EventMatcher",
]
