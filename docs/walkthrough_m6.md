# Milestone 6 Walkthrough: Clustering, Contradiction Detection & Confidence Tiering

## Overview
Milestone 6 implements the cross-source corroboration engine. It groups equivalent atomic claims into unified clusters, detects direct contradictions (such as conflicting numbers or assertions), traces syndication chains to count true independent origins, and assigns strict 5-tier confidence ratings.

---

## Key Modules Built

### 1. Independent Origin Resolver (`newsx.corroboration.IndependentOriginResolver`)
- Traverses syndication links (`republished_from`, `duplicate_of`) stored on `Item` records.
- Ensures wire stories reproduced across multiple outlets (e.g., AP/Reuters copies in local newspapers) collapse to **1 independent origin**.
- Verifies that credibility is driven by independent reporting, not syndication volume.

### 2. Semantic Slot & Jaccard Claim Clustering (`newsx.corroboration.ClaimMatcher`)
- Groups claims into `ClaimCluster` instances based on semantic slot overlap (`subject`, `predicate`, `object`, `value`, `unit`) and token Jaccard similarity ($\ge 0.60$).
- Clusters equivalent claims across different reporting sources without losing fine-grained provenance.

### 3. Contradiction Detection (`newsx.corroboration.ContradictionDetector`)
- Automatically flags conflicting claims within the same event/cluster:
  - **Numeric divergence**: Different quantities/values reported for the same metric/entity.
  - **Status/polarity divergence**: Mutually exclusive statements without chronological reconciliation.
- Cross-references conflicting claim IDs in `contradiction_ids` and marks claims as disputed.

### 4. 5-Tier Confidence Engine (`newsx.corroboration.ConfidenceTierEngine`)
Assigns normative confidence tiers to claims based on source provenance and corroboration:
- **Tier 1 (`PRIMARY_CONFIRMED`)**: Supported by $\ge 1$ Tier 1 Primary origin (official reports, agency statements, regulatory filings).
- **Tier 2 (`INDEPENDENTLY_CORROBORATED`)**: Supported by $\ge 2$ independent secondary origins with no active contradictions.
- **Tier 3 (`SINGLE_SOURCE`)**: Supported by exactly 1 independent origin with no active contradictions.
- **Tier 4 (`DISPUTED`)**: Contradiction detected across reporting sources; presented side-by-side.
- **Tier 5 (`UNVERIFIED_OR_RETRACTED`)**: Single anonymous assertion or retracted claim.

---

## Benchmark & Test Results

```
============================== 57 passed in 0.80s ==============================
```

- `tests/test_corroboration.py`: Verified syndication collapse, Tier 1 primary confirmation, and Tier 4 dispute flags on contradiction.
- `tests/test_m6_gold_evaluation.py`: Evaluated full corroboration pipeline over all 12 gold articles across 3 event types (`ev-hardfact-01`, `ev-numeric-02`, `ev-contested-03`).
- All 57 unit and integration tests across M0–M6 pass cleanly with 100% determinism.
