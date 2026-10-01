"""Pipeline Orchestrator (M2).

Connects collection, deduplication, normalization, and storage into a unified workflow.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .collector import Collector
from .deduplication import Deduplicator
from .normalizer import Normalizer
from .registry import DiversityChecker, SourceRegistry
from .brief import BriefGenerator
from .corroboration import Corroborator
from .extractor import ClaimExtractor
from .neutralizer import Neutralizer
from .presenter import ConsoleBriefRenderer, HtmlBriefRenderer, MarkdownBriefRenderer
from .schemas import ArticleType, AuditEntry, Brief, Event, Item, Passage
from .storage import Storage
from .triage import TriageEngine

STAGE_VERSION = "1.0.0"


class Pipeline:
    """End-to-end pipeline runner for news extraction."""

    def __init__(
        self,
        storage: Optional[Storage] = None,
        registry: Optional[SourceRegistry] = None,
    ) -> None:
        self.storage = storage or Storage()
        self.registry = registry or SourceRegistry()
        self.diversity_checker = DiversityChecker(self.registry)
        self.collector = Collector(self.storage, self.registry)
        self.deduplicator = Deduplicator(self.storage)
        self.normalizer = Normalizer(self.storage)
        self.triager = TriageEngine(self.storage)
        self.extractor = ClaimExtractor(self.storage)
        self.neutralizer = Neutralizer(self.storage)
        self.corroborator = Corroborator(self.storage, self.registry)
        self.brief_generator = BriefGenerator(self.storage, self.registry, self.diversity_checker)

    def process_raw_item(
        self,
        source_id: str,
        url: str,
        title: str,
        raw_text: str,
        byline: str = "",
        dateline: str = "",
        published_time: Optional[datetime] = None,
        article_type: ArticleType = ArticleType.REPORTING,
        custom_id: Optional[str] = None,
    ) -> tuple[Item, list[Passage], list[Claim]]:
        # 1. Ingest
        item = self.collector.ingest_raw_record(
            source_id=source_id,
            url=url,
            title=title,
            raw_text=raw_text,
            byline=byline,
            dateline=dateline,
            published_time=published_time,
            article_type=article_type,
            custom_id=custom_id,
        )

        # 2. Deduplicate
        item = self.deduplicator.process_item(item)

        # 3. Normalize & Segment
        passages = self.normalizer.normalize_item(item)

        # 4. Triage (Article & Passage level classification)
        self.triager.triage_item(item, passages)

        # 5. Extract atomic claims from factual passages
        claims = self.extractor.process_item_passages(item, passages)

        # 6. Neutralize loaded wording with change tracking
        neutralized_claims = self.neutralizer.process_claims(claims)

        return item, passages, neutralized_claims

    def run_event_from_gold_file(self, event_id: str, gold_file: Optional[Path] = None) -> Event:
        gold_path = gold_file or (Path(__file__).resolve().parent.parent.parent / "gold" / "raw" / "items.jsonl")
        if not gold_path.exists():
            raise FileNotFoundError(f"Gold raw items not found at {gold_path}")

        matched_records = []
        with gold_path.open("r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                rec = json.loads(line)
                if rec.get("event_id") == event_id or event_id == "all":
                    matched_records.append(rec)

        if not matched_records:
            raise ValueError(f"No records found for event_id '{event_id}' in {gold_path}")

        member_ids: list[str] = []
        all_claim_ids: list[str] = []
        times: list[datetime] = []
        event_label = matched_records[0].get("event_id", event_id)

        for rec in matched_records:
            pub_time = datetime.fromisoformat(rec["published"]) if rec.get("published") else None
            if pub_time:
                times.append(pub_time)

            art_type = ArticleType.REPORTING
            if rec.get("item_id") == "gold-art-007":
                art_type = ArticleType.ANALYSIS
            elif rec.get("item_id") == "gold-art-011":
                art_type = ArticleType.OPINION

            item, passages, claims = self.process_raw_item(
                source_id=rec["source"],
                url=rec["url"],
                title=rec["title"],
                raw_text=rec["text"],
                byline=rec.get("byline", ""),
                dateline=rec.get("dateline", ""),
                published_time=pub_time,
                article_type=art_type,
                custom_id=rec["item_id"],
            )
            member_ids.append(item.id)
            all_claim_ids.extend([c.id for c in claims])

        time_span = (min(times) if times else None, max(times) if times else None)

        # Collect claim objects for event
        all_claims = [self.storage.get_claim(cid) for cid in all_claim_ids]
        valid_claims = [c for c in all_claims if c is not None]
        all_source_ids = [rec["source"] for rec in matched_records]

        # Corroboration & Clustering
        ledger_entries = self.corroborator.cluster_event_claims(
            event_id=event_id,
            claims=valid_claims,
            all_event_source_ids=all_source_ids,
        )

        event = Event(
            id=event_id,
            label=event_label,
            member_item_ids=member_ids,
            time_span=time_span,
            claim_ids=all_claim_ids,
        )
        self.storage.save_event(event)

        now = datetime.now(timezone.utc)
        self.storage.write_audit_entry(
            AuditEntry(
                stage="event_assembly",
                stage_version=STAGE_VERSION,
                input_id=event_id,
                output_id=event.id,
                what_changed=(
                    f"Assembled event with {len(member_ids)} items, {len(all_claim_ids)} claims, "
                    f"and {len(ledger_entries)} ledger entries"
                ),
                when=now,
            )
        )

        return event

    def generate_event_brief(
        self,
        event_id: str,
        event_title: Optional[str] = None,
        event_category: str = "hard_fact",
        output_dir: Optional[Path] = None,
    ) -> tuple[Brief, Path, Path]:
        """Generates a structured Brief for the event and renders both Markdown and HTML exports."""
        brief = self.brief_generator.generate_brief(
            event_id=event_id,
            event_title=event_title,
            event_category=event_category,
        )

        out_dir = output_dir or Path("data/briefs")
        out_dir.mkdir(parents=True, exist_ok=True)

        md_path = out_dir / f"{event_id}.md"
        html_path = out_dir / f"{event_id}.html"

        md_content = MarkdownBriefRenderer().render(brief)
        html_content = HtmlBriefRenderer().render(brief)

        md_path.write_text(md_content, encoding="utf-8")
        html_path.write_text(html_content, encoding="utf-8")

        return brief, md_path, html_path
