# Raw News Extraction Tool (Antigravity NewsX)

An open, verifiable, zero-recurring-cost news extraction tool that collects coverage of current events from diverse sources, separates reporting from opinion, extracts atomic factual claims with dual-layer attribution, neutralizes loaded wording without semantic loss, clusters equivalent claims into an event ledger, detects direct contradictions, assigns 5-tier confidence ratings, and presents transparent briefs with complete drill-down provenance.

---

## Key Principles & Normative Guarantees

1. **Extractive-First Span Grounding**: Every atomic claim must anchor to an exact character span in the source passage; unanchored propositions are rejected.
2. **Attribution Layering**: Attribution is strictly separated from assertion (Layer 1: that X made statement Y; Layer 2: propositional content).
3. **Independent Origin Counting**: Syndicated wire stories collapse to 1 origin so repetition volume does not inflate claim credibility.
4. **Reversible Neutralization**: Loaded language and spin are removed with 100% reversible `ChangeRecord` annotations while preserving checkable numbers and named entities.
5. **Visible Uncertainty & Side-by-Side Disputes**: Contradictory claims are explicitly highlighted side-by-side with original attributions.
6. **Zero Recurring Cost**: Runs completely offline or with local open-weight models (Ollama/deterministic fallbacks) without paid API dependencies.

---

## System Architecture & Milestone Roadmap

- **M0: Definitions & Agreement** ([`docs/taxonomy.md`](docs/taxonomy.md), [`docs/labeling-guide.md`](docs/labeling-guide.md)) — Normative taxonomy, Pydantic schemas, 12 gold articles, inter-annotator Kappa $\ge 0.97$, span F1 $= 1.0$.
- **M1: Source Registry & Diversity** ([`config/sources.yaml`](config/sources.yaml), [`config/diversity_rules.yaml`](config/diversity_rules.yaml)) — Source tiers (Primary, Secondary, Tertiary), ownership/regional quotas, and static HTML transparency page generator.
- **M2: Collection & Normalization** ([`src/newsx/collector.py`](src/newsx/collector.py), [`src/newsx/storage.py`](src/newsx/storage.py)) — SQLite relational storage, JSONL immutable audit trail, polite collector, n-gram deduplication, quote-preserving sentence segmentation.
- **M3: Content Triage** ([`src/newsx/triage.py`](src/newsx/triage.py)) — Article classification (Reporting, Opinion, Analysis, Sponsored) and passage fact-base routing.
- **M4: Claim Extraction** ([`src/newsx/extractor.py`](src/newsx/extractor.py)) — Semantic slot decomposition (`who`, `what`, `when`, `where`, `how_much`), exact character span anchoring, and dual-layer attribution.
- **M5: Neutralization** ([`src/newsx/neutralizer.py`](src/newsx/neutralizer.py)) — Neutral rewrites, intensifier/charged-verb replacement, factual emotion whitelist, meaning preservation verification.
- **M6: Clustering & Corroboration** ([`src/newsx/corroboration.py`](src/newsx/corroboration.py)) — Independent origin resolution (syndication collapse), slot-based claim clustering, numeric/polarity contradiction detection, 5-tier confidence hierarchy.
- **M7: Presentation & Event Briefs** ([`src/newsx/brief.py`](src/newsx/brief.py), [`src/newsx/presenter.py`](src/newsx/presenter.py)) — Multi-section neutral briefs with side-by-side dispute tables, chronological timelines, Markdown and interactive HTML exports.
- **M8: Continuous & Multi-Event Pipeline** ([`src/newsx/continuous.py`](src/newsx/continuous.py)) — Incremental article routing, real-time confidence promotions (Tier 3 $\rightarrow$ Tier 2 $\rightarrow$ Tier 1), publisher retraction propagation, and structured brief diffing.
- **M9: Benchmark Suite & Validation** ([`scripts/evaluate_all.py`](scripts/evaluate_all.py)) — Unified evaluation harness across all milestones.

---

## Production Benchmark Scorecard

| Stage / Milestone | Achieved Metric | Target | Status |
| :--- | :--- | :--- | :--- |
| **M0: Definitions & Agreement** | Kappa = 1.000, Span F1 = 1.000 | Kappa $\ge$ 0.85, F1 $\ge$ 0.90 | ✅ PASS |
| **M1: Source Registry & Quotas** | 18 sources (6 primary) | $\ge$ 10 sources, $\ge$ 4 primary | ✅ PASS |
| **M2: Collection & Normalization** | SQLite CRUD + JSONL Audit Trail (12 items) | Deterministic Storage & Audit Logs | ✅ PASS |
| **M3: Content Triage** | Article Acc = 100.0%, Route Acc = 100.0% | Accuracy $\ge$ 90% | ✅ PASS |
| **M4: Claim Extraction** | Span Grounding F1 = 1.000, Provenance = 100% | Grounding F1 $\ge$ 0.90, Provenance = 100% | ✅ PASS |
| **M5: Neutralization** | Reversibility = 100%, Retention = 100% | Reversibility = 100%, Retention = 100% | ✅ PASS |
| **M6: Corroboration & Tiers** | Syndication collapse + 5-Tier hierarchy + Disputes | 100% Invariants Passed | ✅ PASS |
| **M7: Presentation & Briefs** | Markdown + HTML + Terminal Drill-Downs | 100% Drill-Down Provenance | ✅ PASS |
| **M8: Continuous & Retractions** | Dynamic Tier Promotions (T3 $\rightarrow$ T2 $\rightarrow$ T1) + Diffing | 100% Invariants Passed | ✅ PASS |

---

## Quickstart & CLI Commands

```bash
# 1. Run full unit and integration test suite (67 tests)
make test

# 2. Run unified full-system benchmark harness across all stages
make benchmark

# 3. Generate static source transparency registry page
make transparency

# 4. Ingest and process an event
make run EVENT=event-key-bridge-01

# 5. Generate and export structured event brief (Markdown + standalone HTML)
make brief EVENT=event-key-bridge-01
make brief EVENT=event-south-china-sea-01
```

Generated brief outputs are saved to `data/briefs/<event_id>.md` and `data/briefs/<event_id>.html`.

## Local editorial workspace

Launch the Stitch-inspired TrueNews interface, backed by the existing SQLite ledger:

```bash
make web
```

Open [http://127.0.0.1:8787](http://127.0.0.1:8787). The workspace exposes local JSON endpoints for events, briefs, claims, ledger entries, sources, and Markdown/HTML brief exports under `/api/`.
