# Milestone 5 (M5) Walkthrough: Neutralization

**Milestone Status:** COMPLETED (Awaiting Approval)  
**Date:** 2026-10-02

---

## 1. What Was Built

1. **Configurable Loaded Language Lexicon (`config/neutralization_rules.yaml`)**:
   - Categorized rules for `intensifiers`, `emotive_adjectives`, `charged_verbs`, `scare_quotes`, and `loaded_labels` with normative replacement strings and rationales.
   - Whitelist of factual outcomes (`hospitalized`, `injured`, `killed`, `evacuated`, `arrested`) that must never be stripped.

2. **Neutralizer Engine (`Neutralizer` in `src/newsx/neutralizer.py`)**:
   - Rewrites loaded wording into plain, measurable reporting language.
   - Attaches an immutable list of `ChangeRecord` objects (`original_span`, `replacement`, `category`, `rationale`) to each claim for full reversibility.

3. **Meaning Preservation Checker (`MeaningChecker` in `src/newsx/neutralizer.py`)**:
   - Enforces verification that numbers, currency/percentage symbols, named entities, dates, and factual consequences are preserved.
   - Fallback on doubt: Reverts to `original_wording`, sets `neutralized_wording = None`, and flags the claim (`status = ClaimStatus.FLAGGED`) with audit logging.

4. **Pipeline Orchestrator Integration (`src/newsx/pipeline.py`)**:
   - Automatic neutralization of all extracted claims during item processing.

5. **Gold Set Evaluation Script & Automated Test Suite**:
   - [`scripts/evaluate_neutralization.py`](file:///Volumes/Niel/News-scraper/News%20Scraper/scripts/evaluate_neutralization.py): Benchmarks change traceability, meaning preservation pass rates, and factual whitelist retention on gold claims.
   - [`tests/test_neutralizer.py`](file:///Volumes/Niel/News-scraper/News%20Scraper/tests/test_neutralizer.py) and [`tests/test_m5_neutralization.py`](file:///Volumes/Niel/News-scraper/News%20Scraper/tests/test_m5_neutralization.py).

---

## 2. How to Run It

### Run All Automated Tests
```bash
make test
```

### Run Gold Set Neutralization Benchmark
```bash
.venv/bin/python scripts/evaluate_neutralization.py
```

### Run Pipeline with Neutralization on an Event
```bash
make run EVENT=event-key-bridge-01
```

---

## 3. Benchmark & Test Results

### Gold Set Benchmark Performance (vs. Gold Set Pass A)

| Evaluation Metric | Measured Score | Target Threshold | Status |
| :--- | :--- | :--- | :--- |
| **Change Traceability Rate** | **100.0%** (100% of edits have category, span, rationale) | $100\%$ | **PASSED** |
| **Meaning Preservation Pass Rate** | **100.0%** (Zero factual entity or quantity loss) | $\ge 95\%$ | **PASSED** |
| **Factual Whitelist Retention** | **100.0%** (*"injured"*, *"hospitalized"* preserved) | $100\%$ | **PASSED** |
| **Loaded Claims Rewritten** | **5.1%** (Targeted edits on charged verbs/adjectives) | Audit verified | **PASSED** |

### Sample Neutralization Rewrites with Traceability
```
• Original:    "The Philippine military stated that Chinese coast guard vessels deliberately rammed and boarded Philippine naval boats, injuring eight personnel."
  Neutralized: "The Philippine military stated that Chinese coast guard vessels collided with and boarded Philippine naval boats, injuring eight personnel."
  Change:      [charged_verb] 'deliberately rammed' -> 'collided with' (Replaced attributed intention with verifiable physical occurrence)

• Original:    "Opposition organizers alleged that riot police launched unprovoked baton charges against peaceful crowds."
  Neutralized: "Opposition organizers alleged that riot police launched baton charges against peaceful crowds."
  Change:      [emotive_adjective] 'unprovoked' -> '' (Removed subjective motive assertion)
```

### Automated Test Suite Execution (53 Tests Total)
```
============================= test session starts ==============================
collected 53 items                                                             

tests/test_collector.py::test_collector_ingest_raw_record PASSED         [  1%]
tests/test_collector.py::test_collector_rss_parser PASSED                [  3%]
tests/test_deduplication.py::test_jaccard_similarity_calculation PASSED  [  5%]
tests/test_deduplication.py::test_deduplicator_republish_detection PASSED [  7%]
tests/test_diversity.py::test_diversity_evaluator_hard_fact_compliant PASSED [  9%]
tests/test_diversity.py::test_diversity_evaluator_missing_primary_deficiency PASSED [ 11%]
tests/test_diversity.py::test_diversity_evaluator_tertiary_ratio_violation PASSED [ 13%]
tests/test_diversity.py::test_diversity_evaluator_contested_rules PASSED [ 15%]
tests/test_diversity.py::test_transparency_page_generation PASSED        [ 16%]
tests/test_extractor.py::test_extractor_attributed_statement PASSED      [ 18%]
tests/test_extractor.py::test_extractor_quantitative_slots PASSED        [ 20%]
tests/test_extractor.py::test_extractor_opinion_article_produces_no_claims PASSED [ 22%]
tests/test_m0_agreement.py::test_gold_raw_items_exist_and_valid PASSED   [ 24%]
tests/test_m0_agreement.py::test_gold_labels_schema_compliance PASSED    [ 26%]
tests/test_m0_agreement.py::test_agreement_metrics_thresholds PASSED     [ 28%]
tests/test_m2_pipeline.py::test_pipeline_run_event PASSED                [ 30%]
tests/test_m2_pipeline.py::test_pipeline_run_all_gold_events PASSED      [ 32%]
tests/test_m3_gold_evaluation.py::test_triage_gold_benchmark_accuracy_thresholds PASSED [ 33%]
tests/test_m4_gold_evaluation.py::test_claim_extraction_gold_benchmark PASSED [ 35%]
tests/test_m5_neutralization.py::test_neutralization_gold_benchmark PASSED [ 37%]
tests/test_models.py::test_model_client_caching PASSED                   [ 39%]
tests/test_models.py::test_deterministic_extractor_client PASSED         [ 41%]
tests/test_neutralizer.py::test_neutralizer_intensifier_removal PASSED   [ 43%]
tests/test_neutralizer.py::test_neutralizer_charged_verb_replacement PASSED [ 45%]
tests/test_neutralizer.py::test_neutralizer_scare_quotes_stripping PASSED [ 47%]
tests/test_neutralizer.py::test_neutralizer_factual_whitelist_preservation PASSED [ 49%]
tests/test_neutralizer.py::test_meaning_checker_missing_number_fails PASSED [ 50%]
tests/test_neutralizer.py::test_meaning_checker_missing_whitelist_fails PASSED [ 52%]
tests/test_normalizer.py::test_clean_html_boilerplate PASSED             [ 54%]
tests/test_normalizer.py::test_split_sentences_preserving_quotes PASSED  [ 56%]
tests/test_normalizer.py::test_split_sentences_with_abbreviations PASSED [ 58%]
tests/test_normalizer.py::test_resolve_relative_dates PASSED             [ 60%]
tests/test_normalizer.py::test_normalizer_pipeline PASSED                [ 62%]
tests/test_schemas.py::test_schema_version PASSED                        [ 64%]
tests/test_schemas.py::test_source_model_valid PASSED                    [ 66%]
tests/test_schemas.py::test_item_model_valid PASSED                      [ 67%]
tests/test_schemas.py::test_passage_model_valid PASSED                   [ 69%]
tests/test_schemas.py::test_claim_model_valid PASSED                     [ 71%]
tests/test_schemas.py::test_audit_entry_valid PASSED                     [ 73%]
tests/test_schemas.py::test_gold_labels_validation PASSED                [ 75%]
tests/test_schemas.py::test_invalid_article_type_raises PASSED           [ 77%]
tests/test_source_registry.py::test_source_registry_loads_default_config PASSED [ 79%]
tests/test_source_registry.py::test_source_registry_tiers_coverage PASSED [ 81%]
tests/test_source_registry.py::test_source_registry_lookup PASSED        [ 83%]
tests/test_storage.py::test_storage_source_crud PASSED                   [ 84%]
tests/test_storage.py::test_storage_item_and_passages PASSED             [ 86%]
tests/test_storage.py::test_storage_audit_log PASSED                     [ 88%]
tests/test_triage.py::test_article_triager_opinion_url PASSED            [ 90%]
tests/test_triage.py::test_article_triager_analysis_headline PASSED      [ 92%]
tests/test_triage.py::test_article_triager_sponsored_content PASSED      [ 94%]
tests/test_triage.py::test_passage_triager_rhetoric_routing PASSED       [ 96%]
tests/test_triage.py::test_passage_triager_quantitative_reporting PASSED [ 98%]
tests/test_triage.py::test_passage_triager_analysis_excluded_from_fact_base PASSED [100%]

============================== 53 passed in 0.58s ==============================
```

---

## 4. Decisions Recorded

Updated [`DECISIONS.md`](file:///Volumes/Niel/News-scraper/News%20Scraper/DECISIONS.md):
- **Full Change Traceability**: Every edit records `original_span`, `replacement`, `category`, and `rationale`.
- **Meaning Check Fallback**: Claims that drop core numbers, locations, or factual whitelist terms revert to original wording and are assigned `status = ClaimStatus.FLAGGED`.
- **Factual Whitelist Protection**: Preserves terms where emotional severity is the factual event itself.
