"""Source Registry and Diversity Evaluation Engine.

Loads configured sources and evaluates event source mixes against diversity quotas.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional
import yaml
from pydantic import BaseModel, Field

from .schemas import Source, SourceTier, SourceStatus

DEFAULT_SOURCES_PATH = Path(__file__).resolve().parent.parent.parent / "config" / "sources.yaml"
DEFAULT_RULES_PATH = Path(__file__).resolve().parent.parent.parent / "config" / "diversity_rules.yaml"


class EventQuota(BaseModel):
    description: str = ""
    min_primary_sources: int = 0
    min_secondary_sources: int = 0
    min_independent_origins: int = 0
    min_distinct_ownerships: int = 0
    min_distinct_regions: int = 0
    max_tertiary_ratio: float = 0.0
    require_primary_if_available: bool = True
    require_multi_perspective: bool = False


class DiversityEvaluationResult(BaseModel):
    event_type: str
    is_compliant: bool
    deficiencies: list[str] = Field(default_factory=list)
    primary_count: int = 0
    secondary_count: int = 0
    tertiary_count: int = 0
    distinct_ownership_count: int = 0
    distinct_region_count: int = 0
    distinct_ownerships: list[str] = Field(default_factory=list)
    distinct_regions: list[str] = Field(default_factory=list)
    tertiary_ratio: float = 0.0


class SourceRegistry:
    """Manages the registered sources, their tiers, and metadata."""

    def __init__(self, sources_path: Optional[Path] = None) -> None:
        self.sources_path = sources_path or DEFAULT_SOURCES_PATH
        self._sources: dict[str, Source] = {}
        self.reload()

    def reload(self) -> None:
        if not self.sources_path.exists():
            raise FileNotFoundError(f"Source configuration not found at {self.sources_path}")

        with self.sources_path.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        raw_sources = data.get("sources", [])
        self._sources = {}
        for item in raw_sources:
            source = Source(**item)
            self._sources[source.id] = source

    def get(self, source_id: str) -> Optional[Source]:
        return self._sources.get(source_id)

    def get_or_raise(self, source_id: str) -> Source:
        if source_id not in self._sources:
            raise KeyError(f"Source '{source_id}' is not registered in source registry.")
        return self._sources[source_id]

    def all_sources(self) -> list[Source]:
        return list(self._sources.values())

    def filter_by_tier(self, tier: SourceTier) -> list[Source]:
        return [s for s in self._sources.values() if s.tier == tier]

    def filter_by_status(self, status: SourceStatus) -> list[Source]:
        return [s for s in self._sources.values() if s.status == status]


class DiversityChecker:
    """Evaluates whether a candidate set of sources meets diversity quotas."""

    def __init__(
        self,
        registry: SourceRegistry,
        rules_path: Optional[Path] = None,
    ) -> None:
        self.registry = registry
        self.rules_path = rules_path or DEFAULT_RULES_PATH
        self._quotas: dict[str, EventQuota] = {}
        self._global_rules: dict[str, Any] = {}
        self.reload()

    def reload(self) -> None:
        if not self.rules_path.exists():
            raise FileNotFoundError(f"Diversity rules not found at {self.rules_path}")

        with self.rules_path.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        event_types = data.get("event_types", {})
        self._quotas = {k: EventQuota(**v) for k, v in event_types.items()}
        self._global_rules = data.get("global_rules", {})

    def evaluate(self, event_type: str, source_ids: list[str]) -> DiversityEvaluationResult:
        if event_type not in self._quotas:
            raise ValueError(f"Unknown event type '{event_type}'. Known: {list(self._quotas.keys())}")

        quota = self._quotas[event_type]
        sources = [self.registry.get_or_raise(sid) for sid in source_ids]

        primary_sources = [s for s in sources if s.tier == SourceTier.PRIMARY]
        secondary_sources = [s for s in sources if s.tier == SourceTier.SECONDARY]
        tertiary_sources = [s for s in sources if s.tier == SourceTier.TERTIARY]

        ownerships = sorted(set(s.ownership for s in sources))
        regions = sorted(set(s.region for s in sources))

        total = len(sources)
        tertiary_ratio = (len(tertiary_sources) / total) if total > 0 else 0.0

        deficiencies: list[str] = []

        if len(primary_sources) < quota.min_primary_sources:
            deficiencies.append(
                f"Missing primary source: requires {quota.min_primary_sources}, got {len(primary_sources)}"
            )

        if len(secondary_sources) < quota.min_secondary_sources:
            deficiencies.append(
                f"Insufficient secondary sources: requires {quota.min_secondary_sources}, got {len(secondary_sources)}"
            )

        if len(ownerships) < quota.min_distinct_ownerships:
            deficiencies.append(
                f"Insufficient ownership diversity: requires {quota.min_distinct_ownerships} distinct entities, got {len(ownerships)}"
            )

        if len(regions) < quota.min_distinct_regions:
            deficiencies.append(
                f"Insufficient regional diversity: requires {quota.min_distinct_regions} regions, got {len(regions)}"
            )

        if tertiary_ratio > quota.max_tertiary_ratio:
            deficiencies.append(
                f"Excessive tertiary sources: maximum allowed ratio is {quota.max_tertiary_ratio}, got {tertiary_ratio:.2f}"
            )

        is_compliant = len(deficiencies) == 0

        return DiversityEvaluationResult(
            event_type=event_type,
            is_compliant=is_compliant,
            deficiencies=deficiencies,
            primary_count=len(primary_sources),
            secondary_count=len(secondary_sources),
            tertiary_count=len(tertiary_sources),
            distinct_ownership_count=len(ownerships),
            distinct_region_count=len(regions),
            distinct_ownerships=ownerships,
            distinct_regions=regions,
            tertiary_ratio=tertiary_ratio,
        )
