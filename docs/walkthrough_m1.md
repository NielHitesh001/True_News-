# Milestone 1 (M1) Walkthrough: Source Registry & Diversity Rules

**Milestone Status:** COMPLETED (Awaiting Approval)  
**Date:** 2026-10-02

---

## 1. What Was Built

1. **Source Registry Configuration (`config/sources.yaml`)**:
   - Profiled global and institutional sources across tiers (`primary`, `secondary`, `tertiary`), ownership models (public statutory, non-profit cooperatives, commercial trusts), funding mechanisms, regions, media types, leaning/mission notes, and terms/retrievability constraints.
   - Zero hard-coded source lists in code.

2. **Diversity Rules Configuration (`config/diversity_rules.yaml`)**:
   - Quotas defined per event archetype:
     - **Hard-Fact**: $\ge 1$ Primary, $\ge 2$ Secondary, $\ge 2$ Independent Origins, $\ge 2$ Distinct Ownership entities, 0.0 Tertiary ratio.
     - **Numeric**: $\ge 1$ Primary (official statistical bureau / court filing), $\ge 2$ Secondary, $\ge 2$ Independent Origins, $\ge 2$ Distinct Ownerships, 0.0 Tertiary ratio.
     - **Contested**: $\ge 1$ Primary, $\ge 3$ Secondary, $\ge 3$ Independent Origins, $\ge 3$ Distinct Ownership entities, $\ge 2$ Distinct Geographic Regions, Multi-perspective required, 0.0 Tertiary ratio.

3. **Source Registry & Diversity Evaluation Engine (`src/newsx/registry.py`)**:
   - [`SourceRegistry`](file:///Volumes/Niel/News-scraper/News%20Scraper/src/newsx/registry.py): Typed loading, validation, and querying of source profiles via Pydantic schemas.
   - [`DiversityChecker`](file:///Volumes/Niel/News-scraper/News%20Scraper/src/newsx/registry.py): Validates candidate source sets against event-specific diversity quotas and flags missing primary records, ownership monopolies, regional homogeneity, or unauthorized tertiary aggregator infiltration.

4. **Static Transparency Page Generator (`src/newsx/transparency.py` & `scripts/render_transparency.py`)**:
   - Generates an auditable static HTML report [`docs/transparency.html`](file:///Volumes/Niel/News-scraper/News%20Scraper/docs/transparency.html) displaying source profiles, tiers, ownership transparency, and event quota definitions.

5. **Unit and Integration Tests**:
   - [`tests/test_source_registry.py`](file:///Volumes/Niel/News-scraper/News%20Scraper/tests/test_source_registry.py) and [`tests/test_diversity.py`](file:///Volumes/Niel/News-scraper/News%20Scraper/tests/test_diversity.py).

---

## 2. How to Run It

### Run Automated Tests
```bash
make test
```

### Re-render Transparency Page
```bash
.venv/bin/python scripts/render_transparency.py
```
*(Outputs to [`docs/transparency.html`](file:///Volumes/Niel/News-scraper/News%20Scraper/docs/transparency.html))*

---

## 3. Test Results

All 19 tests across M0 and M1 pass:

```
============================= test session starts ==============================
platform darwin -- Python 3.12.14, pytest-9.1.1, pluggy-1.6.0 -- /Volumes/Niel/News-scraper/News Scraper/.venv/bin/python
cachedir: .pytest_cache
rootdir: /Volumes/Niel/News-scraper/News Scraper
collecting ... collected 19 items                                                             

tests/test_diversity.py::test_diversity_evaluator_hard_fact_compliant PASSED [  5%]
tests/test_diversity.py::test_diversity_evaluator_missing_primary_deficiency PASSED [ 10%]
tests/test_diversity.py::test_diversity_evaluator_tertiary_ratio_violation PASSED [ 15%]
tests/test_diversity.py::test_diversity_evaluator_contested_rules PASSED [ 21%]
tests/test_diversity.py::test_transparency_page_generation PASSED        [ 26%]
tests/test_m0_agreement.py::test_gold_raw_items_exist_and_valid PASSED   [ 31%]
tests/test_m0_agreement.py::test_gold_labels_schema_compliance PASSED    [ 36%]
tests/test_m0_agreement.py::test_agreement_metrics_thresholds PASSED     [ 42%]
tests/test_schemas.py::test_schema_version PASSED                        [ 47%]
tests/test_schemas.py::test_source_model_valid PASSED                    [ 52%]
tests/test_schemas.py::test_item_model_valid PASSED                      [ 57%]
tests/test_schemas.py::test_passage_model_valid PASSED                   [ 63%]
tests/test_schemas.py::test_claim_model_valid PASSED                     [ 68%]
tests/test_schemas.py::test_audit_entry_valid PASSED                     [ 73%]
tests/test_schemas.py::test_gold_labels_validation PASSED                [ 78%]
tests/test_schemas.py::test_invalid_article_type_raises PASSED           [ 84%]
tests/test_source_registry.py::test_source_registry_loads_default_config PASSED [ 89%]
tests/test_source_registry.py::test_source_registry_tiers_coverage PASSED [ 94%]
tests/test_source_registry.py::test_source_registry_lookup PASSED        [100%]

============================== 19 passed in 0.10s ==============================
```

---

## 4. Known Gaps & Decisions

1. **Registry Extension**:
   - As new coverage domains (e.g. specialized medical journals, local municipal portals) are added in subsequent milestones, they are added directly to `config/sources.yaml` without touching code.
2. **Recorded in `DECISIONS.md`**:
   - Zero tertiary aggregators allowed in the core fact base.
   - Static HTML for transparency reporting with zero external network dependencies.
