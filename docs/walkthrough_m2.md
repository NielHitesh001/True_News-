# Milestone 2 (M2) Walkthrough: Collection & Normalization

**Milestone Status:** COMPLETED (Awaiting Approval)  
**Date:** 2026-10-02

---

## 1. What Was Built

1. **Storage & Audit Layer (`src/newsx/storage.py`)**:
   - SQLite database schema (`data/newsx.db`) supporting `sources`, `items`, `passages`, `events`, `claims`, `ledger_entries`, `briefs`, and `audit_log`.
   - File-backed append-only JSONL audit trail (`data/audit.jsonl`) recording stage versions, inputs, outputs, timestamps, and modification summaries.
   - Raw payload archiver storing SHA-256 hashed raw records in `data/raw/`.

2. **Polite Ingestion Collector (`src/newsx/collector.py`)**:
   - Ingests feeds and articles with rate-limiting, custom descriptive User-Agent, and strict respect for terms and robots guidelines.
   - Handles offline gold dataset ingestion and RSS/Atom XML parsing.

3. **Deduplication & Syndication Engine (`src/newsx/deduplication.py`)**:
   - N-gram Jaccard similarity comparison.
   - Sets `duplicate_of` ($\ge 0.95$ match) and `republished_from` ($\ge 0.70$ match) pointers to ensure syndicated wire copies do not inflate independent-origin counts.

4. **Normalizer & Passage Segmenter (`src/newsx/normalizer.py`)**:
   - HTML boilerplate stripper removing ads, social embeds, scripts, and navigation.
   - Sentence segmenter preserving quote integrity and protected abbreviations (`U.S.`, `Dr.`, `Gov.`, `vs.`, `e.g.`).
   - Relative date resolution anchoring temporal expressions (*"Tuesday"*, *"yesterday"*, *"today"*) to the article's publication time.

5. **Pipeline Orchestrator & CLI (`src/newsx/pipeline.py` & `src/newsx/cli.py`)**:
   - Single command to run the pipeline on any event: `make run EVENT=<event_id>` (e.g. `make run EVENT=event-key-bridge-01` or `make run EVENT=all`).

6. **Automated Test Suite**:
   - [`tests/test_storage.py`](file:///Volumes/Niel/News-scraper/News%20Scraper/tests/test_storage.py), [`tests/test_collector.py`](file:///Volumes/Niel/News-scraper/News%20Scraper/tests/test_collector.py), [`tests/test_deduplication.py`](file:///Volumes/Niel/News-scraper/News%20Scraper/tests/test_deduplication.py), [`tests/test_normalizer.py`](file:///Volumes/Niel/News-scraper/News%20Scraper/tests/test_normalizer.py), [`tests/test_m2_pipeline.py`](file:///Volumes/Niel/News-scraper/News%20Scraper/tests/test_m2_pipeline.py).

---

## 2. How to Run It

### Run Automated Tests
```bash
make test
```

### Run the Pipeline on an Event
```bash
make run EVENT=event-key-bridge-01
# or run on all gold events:
make run EVENT=all
```

### Render Source Transparency Page
```bash
make transparency
```

---

## 3. Test Results

All 33 automated tests across M0, M1, and M2 pass cleanly:

```
============================= test session starts ==============================
platform darwin -- Python 3.12.14, pytest-9.1.1, pluggy-1.6.0 -- /Volumes/Niel/News-scraper/News Scraper/.venv/bin/python
cachedir: .pytest_cache
rootdir: /Volumes/Niel/News-scraper/News Scraper
collecting ... collected 33 items                                                             

tests/test_collector.py::test_collector_ingest_raw_record PASSED         [  3%]
tests/test_collector.py::test_collector_rss_parser PASSED                [  6%]
tests/test_deduplication.py::test_jaccard_similarity_calculation PASSED  [  9%]
tests/test_deduplication.py::test_deduplicator_republish_detection PASSED [ 12%]
tests/test_diversity.py::test_diversity_evaluator_hard_fact_compliant PASSED [ 15%]
tests/test_diversity.py::test_diversity_evaluator_missing_primary_deficiency PASSED [ 18%]
tests/test_diversity.py::test_diversity_evaluator_tertiary_ratio_violation PASSED [ 21%]
tests/test_diversity.py::test_diversity_evaluator_contested_rules PASSED [ 24%]
tests/test_diversity.py::test_transparency_page_generation PASSED        [ 27%]
tests/test_m0_agreement.py::test_gold_raw_items_exist_and_valid PASSED   [ 30%]
tests/test_m0_agreement.py::test_gold_labels_schema_compliance PASSED    [ 33%]
tests/test_m0_agreement.py::test_agreement_metrics_thresholds PASSED     [ 36%]
tests/test_m2_pipeline.py::test_pipeline_run_event PASSED                [ 39%]
tests/test_m2_pipeline.py::test_pipeline_run_all_gold_events PASSED      [ 42%]
tests/test_normalizer.py::test_clean_html_boilerplate PASSED             [ 45%]
tests/test_normalizer.py::test_split_sentences_preserving_quotes PASSED  [ 48%]
tests/test_normalizer.py::test_split_sentences_with_abbreviations PASSED [ 51%]
tests/test_normalizer.py::test_resolve_relative_dates PASSED             [ 54%]
tests/test_normalizer.py::test_normalizer_pipeline PASSED                [ 57%]
tests/test_schemas.py::test_schema_version PASSED                        [ 60%]
tests/test_schemas.py::test_source_model_valid PASSED                    [ 63%]
tests/test_schemas.py::test_item_model_valid PASSED                      [ 66%]
tests/test_schemas.py::test_passage_model_valid PASSED                   [ 69%]
tests/test_schemas.py::test_claim_model_valid PASSED                     [ 72%]
tests/test_schemas.py::test_audit_entry_valid PASSED                     [ 75%]
tests/test_schemas.py::test_gold_labels_validation PASSED                [ 78%]
tests/test_schemas.py::test_invalid_article_type_raises PASSED           [ 81%]
tests/test_source_registry.py::test_source_registry_loads_default_config PASSED [ 84%]
tests/test_source_registry.py::test_source_registry_tiers_coverage PASSED [ 87%]
tests/test_source_registry.py::test_source_registry_lookup PASSED        [ 90%]
tests/test_storage.py::test_storage_source_crud PASSED                   [ 93%]
tests/test_storage.py::test_storage_item_and_passages PASSED             [ 96%]
tests/test_storage.py::test_storage_audit_log PASSED                     [100%]

============================== 33 passed in 0.24s ==============================
```

---

## 4. Known Gaps & Decisions

1. **Syndication Threshold Calibration**:
   - Exact duplicate threshold is set at $0.95$ Jaccard similarity; syndication threshold is $0.70$. These thresholds will be continually benchmarked during M8 evaluation.
2. **Recorded Decisions in `DECISIONS.md`**:
   - Dual storage architecture: SQLite for structured relational queries, JSONL for immutable append-only audit streams.
   - Quote-state-aware tokenizer preventing arbitrary splits inside quotations or honorifics.
