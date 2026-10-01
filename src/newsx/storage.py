"""Storage layer for SQLite database and append-only JSONL audit logs.

Provides relational indexing and ACID guarantees for pipeline records,
while maintaining a file-backed audit stream (spec §4/§5).
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from .schemas import (
    ArticleType,
    AuditEntry,
    Claim,
    ClaimStatus,
    ClaimType,
    ConfidenceTier,
    Event,
    Item,
    LedgerEntry,
    Passage,
    PassageType,
    Source,
    SourceStatus,
    SourceTier,
)

DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "newsx.db"
DEFAULT_AUDIT_LOG_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "audit.jsonl"


class Storage:
    """Manages SQLite database operations and audit logging."""

    def __init__(
        self,
        db_path: Optional[Path] = None,
        audit_path: Optional[Path] = None,
    ) -> None:
        self.db_path = db_path or DEFAULT_DB_PATH
        self.audit_path = audit_path or DEFAULT_AUDIT_LOG_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.audit_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _init_db(self) -> None:
        with self._get_connection() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS sources (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    tier TEXT NOT NULL,
                    ownership TEXT NOT NULL,
                    funding TEXT NOT NULL,
                    region TEXT NOT NULL,
                    language TEXT NOT NULL,
                    medium TEXT NOT NULL,
                    leaning_notes TEXT DEFAULT '',
                    correction_history TEXT DEFAULT '[]',
                    status TEXT DEFAULT 'active',
                    full_text_retrievable INTEGER DEFAULT 1,
                    access_notes TEXT DEFAULT ''
                );

                CREATE TABLE IF NOT EXISTS items (
                    id TEXT PRIMARY KEY,
                    source_id TEXT NOT NULL,
                    url TEXT NOT NULL,
                    title TEXT NOT NULL,
                    byline TEXT DEFAULT '',
                    dateline TEXT DEFAULT '',
                    published_time TEXT,
                    captured_time TEXT NOT NULL,
                    edit_history TEXT DEFAULT '[]',
                    cleaned_text TEXT DEFAULT '',
                    original_language TEXT DEFAULT 'en',
                    article_type TEXT DEFAULT 'reporting',
                    duplicate_of TEXT,
                    republished_from TEXT,
                    FOREIGN KEY (source_id) REFERENCES sources (id)
                );

                CREATE TABLE IF NOT EXISTS passages (
                    id TEXT PRIMARY KEY,
                    item_id TEXT NOT NULL,
                    position INTEGER NOT NULL,
                    text TEXT NOT NULL,
                    passage_type TEXT NOT NULL,
                    FOREIGN KEY (item_id) REFERENCES items (id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS events (
                    id TEXT PRIMARY KEY,
                    label TEXT NOT NULL,
                    member_item_ids TEXT DEFAULT '[]',
                    time_span_start TEXT,
                    time_span_end TEXT,
                    claim_ids TEXT DEFAULT '[]'
                );

                CREATE TABLE IF NOT EXISTS claims (
                    id TEXT PRIMARY KEY,
                    passage_id TEXT NOT NULL,
                    claim_type TEXT NOT NULL,
                    who TEXT,
                    what TEXT,
                    when_time TEXT,
                    where_loc TEXT,
                    how_much TEXT,
                    attribution_speaker TEXT,
                    attribution_anonymous INTEGER DEFAULT 0,
                    original_wording TEXT NOT NULL,
                    neutralized_wording TEXT,
                    changes TEXT DEFAULT '[]',
                    provenance_chain TEXT DEFAULT '[]',
                    status TEXT DEFAULT 'extracted',
                    FOREIGN KEY (passage_id) REFERENCES passages (id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS ledger_entries (
                    id TEXT PRIMARY KEY,
                    canonical_claim TEXT NOT NULL,
                    equivalent_claim_ids TEXT DEFAULT '[]',
                    supporting_source_ids TEXT DEFAULT '[]',
                    independent_origin_count INTEGER DEFAULT 1,
                    contradictions TEXT DEFAULT '[]',
                    omissions TEXT DEFAULT '[]',
                    confidence_tier INTEGER NOT NULL,
                    change_history TEXT DEFAULT '[]'
                );

                CREATE TABLE IF NOT EXISTS audit_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    stage TEXT NOT NULL,
                    stage_version TEXT NOT NULL,
                    input_id TEXT NOT NULL,
                    output_id TEXT,
                    what_changed TEXT NOT NULL,
                    when_time TEXT NOT NULL,
                    model_id TEXT,
                    model_settings_hash TEXT
                );

                CREATE INDEX IF NOT EXISTS idx_items_source ON items(source_id);
                CREATE INDEX IF NOT EXISTS idx_passages_item ON passages(item_id);
                CREATE INDEX IF NOT EXISTS idx_claims_passage ON claims(passage_id);
                CREATE INDEX IF NOT EXISTS idx_audit_input ON audit_log(input_id);
            """)

    # ---------------------------------------------------------------- Sources
    def save_source(self, source: Source) -> None:
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO sources (
                    id, name, tier, ownership, funding, region, language, medium,
                    leaning_notes, correction_history, status, full_text_retrievable, access_notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    name=excluded.name, tier=excluded.tier, ownership=excluded.ownership,
                    funding=excluded.funding, region=excluded.region, language=excluded.language,
                    medium=excluded.medium, leaning_notes=excluded.leaning_notes,
                    correction_history=excluded.correction_history, status=excluded.status,
                    full_text_retrievable=excluded.full_text_retrievable, access_notes=excluded.access_notes
                """,
                (
                    source.id,
                    source.name,
                    source.tier.value,
                    source.ownership,
                    source.funding,
                    source.region,
                    source.language,
                    source.medium,
                    source.leaning_notes,
                    json.dumps(source.correction_history),
                    source.status.value,
                    1 if source.full_text_retrievable else 0,
                    source.access_notes,
                ),
            )

    def get_source(self, source_id: str) -> Optional[Source]:
        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM sources WHERE id = ?", (source_id,)).fetchone()
            if not row:
                return None
            return Source(
                id=row["id"],
                name=row["name"],
                tier=SourceTier(row["tier"]),
                ownership=row["ownership"],
                funding=row["funding"],
                region=row["region"],
                language=row["language"],
                medium=row["medium"],
                leaning_notes=row["leaning_notes"],
                correction_history=json.loads(row["correction_history"]),
                status=SourceStatus(row["status"]),
                full_text_retrievable=bool(row["full_text_retrievable"]),
                access_notes=row["access_notes"],
            )

    # ---------------------------------------------------------------- Items
    def save_item(self, item: Item) -> None:
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO items (
                    id, source_id, url, title, byline, dateline, published_time,
                    captured_time, edit_history, cleaned_text, original_language,
                    article_type, duplicate_of, republished_from
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    source_id=excluded.source_id, url=excluded.url, title=excluded.title,
                    byline=excluded.byline, dateline=excluded.dateline,
                    published_time=excluded.published_time, captured_time=excluded.captured_time,
                    edit_history=excluded.edit_history, cleaned_text=excluded.cleaned_text,
                    original_language=excluded.original_language, article_type=excluded.article_type,
                    duplicate_of=excluded.duplicate_of, republished_from=excluded.republished_from
                """,
                (
                    item.id,
                    item.source_id,
                    str(item.url),
                    item.title,
                    item.byline,
                    item.dateline,
                    item.published_time.isoformat() if item.published_time else None,
                    item.captured_time.isoformat(),
                    json.dumps([t.isoformat() for t in item.edit_history]),
                    item.cleaned_text,
                    item.original_language,
                    item.article_type.value,
                    item.duplicate_of,
                    item.republished_from,
                ),
            )

    def get_item(self, item_id: str) -> Optional[Item]:
        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM items WHERE id = ?", (item_id,)).fetchone()
            if not row:
                return None
            pub_time = datetime.fromisoformat(row["published_time"]) if row["published_time"] else None
            cap_time = datetime.fromisoformat(row["captured_time"])
            edit_hist = [datetime.fromisoformat(t) for t in json.loads(row["edit_history"])]
            return Item(
                id=row["id"],
                source_id=row["source_id"],
                url=row["url"],
                title=row["title"],
                byline=row["byline"],
                dateline=row["dateline"],
                published_time=pub_time,
                captured_time=cap_time,
                edit_history=edit_hist,
                cleaned_text=row["cleaned_text"],
                original_language=row["original_language"],
                article_type=ArticleType(row["article_type"]),
                duplicate_of=row["duplicate_of"],
                republished_from=row["republished_from"],
            )

    def list_items(self) -> list[Item]:
        with self._get_connection() as conn:
            rows = conn.execute("SELECT id FROM items ORDER BY captured_time DESC").fetchall()
            return [self.get_item(r["id"]) for r in rows if r["id"]]  # type: ignore

    # ---------------------------------------------------------------- Passages
    def save_passages(self, passages: list[Passage]) -> None:
        with self._get_connection() as conn:
            for p in passages:
                conn.execute(
                    """
                    INSERT INTO passages (id, item_id, position, text, passage_type)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        item_id=excluded.item_id, position=excluded.position,
                        text=excluded.text, passage_type=excluded.passage_type
                    """,
                    (p.id, p.item_id, p.position, p.text, p.passage_type.value),
                )

    def save_passage(self, passage: Passage) -> None:
        self.save_passages([passage])

    def get_passages_for_item(self, item_id: str) -> list[Passage]:
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM passages WHERE item_id = ? ORDER BY position ASC",
                (item_id,),
            ).fetchall()
            return [
                Passage(
                    id=r["id"],
                    item_id=r["item_id"],
                    position=r["position"],
                    text=r["text"],
                    passage_type=PassageType(r["passage_type"]),
                )
                for r in rows
            ]

    def get_passages_by_item(self, item_id: str) -> list[Passage]:
        return self.get_passages_for_item(item_id)

    def get_items_by_event(self, event_id: str) -> list[Item]:
        event = self.get_event(event_id)
        if event and event.member_item_ids:
            items = []
            for it_id in event.member_item_ids:
                it = self.get_item(it_id)
                if it:
                    items.append(it)
            return items
        return self.list_items()

    # ---------------------------------------------------------------- Events
    def save_event(self, event: Event) -> None:
        with self._get_connection() as conn:
            t_start = event.time_span[0].isoformat() if event.time_span[0] else None
            t_end = event.time_span[1].isoformat() if event.time_span[1] else None
            conn.execute(
                """
                INSERT INTO events (id, label, member_item_ids, time_span_start, time_span_end, claim_ids)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    label=excluded.label, member_item_ids=excluded.member_item_ids,
                    time_span_start=excluded.time_span_start, time_span_end=excluded.time_span_end,
                    claim_ids=excluded.claim_ids
                """,
                (
                    event.id,
                    event.label,
                    json.dumps(event.member_item_ids),
                    t_start,
                    t_end,
                    json.dumps(event.claim_ids),
                ),
            )

    def get_event(self, event_id: str) -> Optional[Event]:
        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()
            if not row:
                return None
            t_start = datetime.fromisoformat(row["time_span_start"]) if row["time_span_start"] else None
            t_end = datetime.fromisoformat(row["time_span_end"]) if row["time_span_end"] else None
            return Event(
                id=row["id"],
                label=row["label"],
                member_item_ids=json.loads(row["member_item_ids"]),
                time_span=(t_start, t_end),
                claim_ids=json.loads(row["claim_ids"]),
            )

    # ---------------------------------------------------------------- Claims
    def save_claim(self, claim: Claim) -> None:
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO claims (
                    id, passage_id, claim_type, who, what, when_time, where_loc,
                    how_much, attribution_speaker, attribution_anonymous, original_wording,
                    neutralized_wording, changes, provenance_chain, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    passage_id=excluded.passage_id, claim_type=excluded.claim_type,
                    who=excluded.who, what=excluded.what, when_time=excluded.when_time,
                    where_loc=excluded.where_loc, how_much=excluded.how_much,
                    attribution_speaker=excluded.attribution_speaker,
                    attribution_anonymous=excluded.attribution_anonymous,
                    original_wording=excluded.original_wording,
                    neutralized_wording=excluded.neutralized_wording,
                    changes=excluded.changes, provenance_chain=excluded.provenance_chain,
                    status=excluded.status
                """,
                (
                    claim.id,
                    claim.passage_id,
                    claim.claim_type.value,
                    claim.who,
                    claim.what,
                    claim.when,
                    claim.where,
                    claim.how_much,
                    claim.attribution_speaker,
                    1 if claim.attribution_anonymous else 0,
                    claim.original_wording,
                    claim.neutralized_wording,
                    json.dumps([c.model_dump() for c in claim.changes]),
                    json.dumps(claim.provenance_chain),
                    claim.status.value,
                ),
            )

    def get_claim(self, claim_id: str) -> Optional[Claim]:
        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM claims WHERE id = ?", (claim_id,)).fetchone()
            if not row:
                return None
            changes_data = json.loads(row["changes"])
            return Claim(
                id=row["id"],
                passage_id=row["passage_id"],
                claim_type=ClaimType(row["claim_type"]),
                who=row["who"],
                what=row["what"],
                when=row["when_time"],
                where=row["where_loc"],
                how_much=row["how_much"],
                attribution_speaker=row["attribution_speaker"],
                attribution_anonymous=bool(row["attribution_anonymous"]),
                original_wording=row["original_wording"],
                neutralized_wording=row["neutralized_wording"],
                changes=changes_data,
                provenance_chain=json.loads(row["provenance_chain"]),
                status=ClaimStatus(row["status"]),
            )

    def get_claims_for_passage(self, passage_id: str) -> list[Claim]:
        with self._get_connection() as conn:
            rows = conn.execute("SELECT id FROM claims WHERE passage_id = ? ORDER BY id ASC", (passage_id,)).fetchall()
            return [self.get_claim(r["id"]) for r in rows if r["id"]]  # type: ignore

    def get_claims_by_passage(self, passage_id: str) -> list[Claim]:
        return self.get_claims_for_passage(passage_id)

    def get_claims_for_item(self, item_id: str) -> list[Claim]:
        passages = self.get_passages_for_item(item_id)
        claims: list[Claim] = []
        for p in passages:
            claims.extend(self.get_claims_for_passage(p.id))
        return claims

    # ---------------------------------------------------------------- Ledger Entries
    def save_ledger_entry(self, entry: LedgerEntry) -> None:
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO ledger_entries (
                    id, canonical_claim, equivalent_claim_ids, supporting_source_ids,
                    independent_origin_count, contradictions, omissions,
                    confidence_tier, change_history
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    canonical_claim=excluded.canonical_claim,
                    equivalent_claim_ids=excluded.equivalent_claim_ids,
                    supporting_source_ids=excluded.supporting_source_ids,
                    independent_origin_count=excluded.independent_origin_count,
                    contradictions=excluded.contradictions,
                    omissions=excluded.omissions,
                    confidence_tier=excluded.confidence_tier,
                    change_history=excluded.change_history
                """,
                (
                    entry.id,
                    entry.canonical_claim,
                    json.dumps(entry.equivalent_claim_ids),
                    json.dumps(entry.supporting_source_ids),
                    entry.independent_origin_count,
                    json.dumps(entry.contradictions),
                    json.dumps(entry.omissions),
                    entry.confidence_tier.value,
                    json.dumps(entry.change_history),
                ),
            )

    def get_ledger_entry(self, entry_id: str) -> Optional[LedgerEntry]:
        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM ledger_entries WHERE id = ?", (entry_id,)).fetchone()
            if not row:
                return None
            return LedgerEntry(
                id=row["id"],
                canonical_claim=row["canonical_claim"],
                equivalent_claim_ids=json.loads(row["equivalent_claim_ids"]),
                supporting_source_ids=json.loads(row["supporting_source_ids"]),
                independent_origin_count=row["independent_origin_count"],
                contradictions=json.loads(row["contradictions"]),
                omissions=json.loads(row["omissions"]),
                confidence_tier=ConfidenceTier(row["confidence_tier"]),
                change_history=json.loads(row["change_history"]),
            )

    def list_ledger_entries(self) -> list[LedgerEntry]:
        with self._get_connection() as conn:
            rows = conn.execute("SELECT id FROM ledger_entries ORDER BY id ASC").fetchall()
            return [self.get_ledger_entry(r["id"]) for r in rows if r["id"]]  # type: ignore

    def get_ledger_entries(self, event_id: Optional[str] = None) -> list[LedgerEntry]:
        entries = self.list_ledger_entries()
        if event_id:
            # Filter entries belonging to event if prefixed, or all if generic
            ev_entries = [e for e in entries if f"ledger-{event_id}" in e.id]
            if ev_entries:
                return ev_entries
        return entries

    # ---------------------------------------------------------------- Audit Log
    def write_audit_entry(self, entry: AuditEntry) -> None:
        iso_when = entry.when.isoformat()
        # 1. Write to SQLite
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO audit_log (
                    stage, stage_version, input_id, output_id, what_changed,
                    when_time, model_id, model_settings_hash
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    entry.stage,
                    entry.stage_version,
                    entry.input_id,
                    entry.output_id,
                    entry.what_changed,
                    iso_when,
                    entry.model_id,
                    entry.model_settings_hash,
                ),
            )
        # 2. Append to JSONL audit stream
        with self.audit_path.open("a", encoding="utf-8") as f:
            rec = entry.model_dump(mode="json")
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    def get_audit_trail_for_input(self, input_id: str) -> list[AuditEntry]:
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM audit_log WHERE input_id = ? ORDER BY id ASC",
                (input_id,),
            ).fetchall()
            return [
                AuditEntry(
                    stage=r["stage"],
                    stage_version=r["stage_version"],
                    input_id=r["input_id"],
                    output_id=r["output_id"],
                    what_changed=r["what_changed"],
                    when=datetime.fromisoformat(r["when_time"]),
                    model_id=r["model_id"],
                    model_settings_hash=r["model_settings_hash"],
                )
                for r in rows
            ]
