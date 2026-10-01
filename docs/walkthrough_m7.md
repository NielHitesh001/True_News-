# Milestone 7 Walkthrough: Event Briefs with Full Drill-Down

## Overview
Milestone 7 delivers the user-facing presentation layer. It synthesizes structured, multi-section neutral event briefs from corroboration ledgers, provides side-by-side dispute comparison tables, sequences chronological event timelines, performs source diversity audits, and exports both clean Markdown and responsive standalone HTML briefs with complete drill-down provenance.

---

## Key Modules Built

### 1. Brief Generator (`newsx.brief.BriefGenerator`)
- **Neutral Headline Synthesizer**: Generates clean, factual event titles without clickbait or editorialized qualifiers.
- **Section Partitioning & Ranking**:
  - **Core Facts**: Tier 1 (`PRIMARY_CONFIRMED`) and Tier 2 (`INDEPENDENTLY_CORROBORATED`), prioritized with Tier 1 first followed by independent origin count descending.
  - **Disputed Points**: Paired contradictory claims displayed side-by-side with speaker/outlet attribution and verbatim source quotes.
  - **Single-Source Context**: Tier 3 single-source claims isolated from core consensus.
  - **Known Unknowns**: Missing primary record alerts and diversity deficiency notices.
- **Chronological Timeline**: Identifies temporal expressions and orders events chronologically.
- **Source Ledger & Diversity Audit**: Aggregates all reporting sources, verifies independent vs. syndicated origin, and checks diversity rule compliance.

### 2. Multi-Format Renderers (`newsx.presenter`)
- **MarkdownBriefRenderer**: Formats structured briefs into Markdown (`data/briefs/<event_id>.md`) with provenance details, links, and change records.
- **HtmlBriefRenderer**: Generates interactive HTML briefs (`data/briefs/<event_id>.html`) with collapsible `<details>` drawers for raw passage inspection and color-coded tier badges.
- **ConsoleBriefRenderer**: Formats ANSI/text summaries for terminal CLI output.

### 3. Pipeline & CLI Integration
- Added `newsx brief --event <id>` subcommand to `newsx.cli`.
- Added `make brief EVENT=<id>` Makefile target.

---

## Verification & Benchmark Results

### Full Test Suite (61 tests passed)
```
PYTHONPATH=src:. .venv/bin/python -m pytest tests/ -v
============================== 61 passed in 1.02s ==============================
```

### Benchmark Script (`scripts/evaluate_briefs.py`)
- Evaluated on all gold benchmark events:
  - `event-key-bridge-01` (hard-fact): 4 Tier 1 Primary Confirmed core facts verified from NTSB report.
  - `event-us-jobs-01` (numeric): Core facts and single-source metrics verified.
  - `event-south-china-sea-01` (contested): Disputed point verified with side-by-side opposing claims.
- 100% of claims retain unbroken provenance links (`source_id`, `item_id`, `passage_id`, URLs).
