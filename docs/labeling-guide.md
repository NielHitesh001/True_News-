# LABELING GUIDE (M0)

How to label an article for the gold set. Work top-down: article type first, then
passages, then claims. Label what is on the page, not what you know about the world.
If genuinely ambiguous, label `notes` with the doubt — do not guess silently
(spec §1.4).

Required output per article: one `GoldArticleLabel`, one `GoldPassageLabel` per
passage, and `GoldClaimLabel`s for every claim in factual passages. Save as JSON
under `gold/labels/pass<A|B>/`.

## Step 1 — Article type (`GoldArticleLabel`)

Signals, in order of weight:

1. **Placement/label**: URL or page says `/opinion`, "Op-Ed", "Editorial", "Review",
   "Analysis", "Explainer", "Sponsored", "Paid content", "Partner content",
   brand-studio name → that type. Placement outranks tone.
2. **Byline role**: "Columnist", "Contributing opinion writer", "Chief correspondent
   (analysis desk)".
3. **Content signals** (only if 1–2 are absent):
   - Opinion: prescriptions or evaluations as the author's own view — should/must,
     good/bad/shameful/praiseworthy, "I believe".
   - Analysis: interpretation dominates; reported facts serve the interpretation.
   - Reporting: observed events, quantities, attributed statements dominate;
     interpretation, if any, is clearly marked and subordinate.
4. **Sponsored**: any paid-placement marking, however subtle (footer disclosure counts).
   If disclosure exists, type is sponsored even when the body reads as reporting.
5. **Satire**: site is a known satire outlet or the piece is self-evidently absurd
   presented straight.

Record the signal you used in `evidence` (quote it). Never label from the outlet's
general reputation — one outlet publishes all types.

## Step 2 — Passage type (`GoldPassageLabel`)

Split the body into sentence-level passages (keep quotes intact as one passage).
For each, choose exactly one passage type per `docs/taxonomy.md` §6. Quick tests,
in order:

1. Is it a prediction (future-tensed assertion, incl. attributed)? → prediction.
2. Is it the author's/analyst's interpretation, motive-reading, or significance
   claim? → interpretation.
3. Is it a quote or paraphrase of what an identifiable party said/wrote? →
   attributed statement.
4. Is it primarily a number, date, tally, measurement? → quantitative.
5. Is it a directly reported occurrence? → observed event.
6. Is it rhetorical questioning, exclamation, direct address? → rhetoric.

`feeds_fact_base` = type is one of observed event / quantitative / attributed
statement **and** the article type is reporting — for opinion/analysis/sponsored
items this stays false even for factual-looking passages (spec §6 triage);
satire: always false.

## Step 3 — Claims (`GoldClaimLabel`)

Only for passages with `feeds_fact_base = true`.

1. **Anchor first.** Find the exact character span (`span_start`, `span_end`) in the
   passage text that supports the claim. No span → no claim (rejected candidates may
   be noted in `notes`).
2. **Atomicity.** One verifiable proposition per claim. Split conjunctions:
   "X happened and Y happened" → two claims. Do not split what is one proposition
   ("the committee voted 6–3" is one claim: actor, action, and count together).
3. **Attribution split.** An attributed statement yields two labels:
   - `attribution_layer = "assertion"`, `speaker` = who said it: the fact that they
     said it. `claim_type = statement`.
   - `attribution_layer = "content"`: the proposition they uttered, with its own
     `claim_type` (event/quantity/causal/prediction-held). Anonymous source →
     `anonymous_attribution = true`.
4. **Types.** Use taxonomy claim types. Causal claims need explicit causal wording
   (caused, led to, because of, as a result of); mere sequence is not causation.
5. **No filling in.** If the passage says "several", the claim says "several" —
   never substitute a number. World knowledge must not repair the text.

## Worked example

Passage (from a reporting article): `The agency said Tuesday that flash floods had
killed at least 40 people, a devastating toll that officials blamed on record rainfall.`

- P1: whole sentence → attributed statement → feeds fact base.
- Claims:
  1. "The agency said [content]" — assertion layer, speaker = the agency, span = first
     clause.
  2. "flash floods had killed at least 40 people" — content layer, quantity/event,
     span exact. Note "at least" stays in the claim text.
  3. "officials blamed [the deaths] on record rainfall" — content layer, causal
     (explicit "blamed"), anonymous? No — "officials" is a group attribution;
     mark `anonymous_attribution = true` (no identifiable party).
- NOT a claim: "a devastating toll" — loaded evaluation; if neutralized it becomes
  "at least 40 people killed" (already claim 2); the evaluation itself is dropped
  with a recorded change.

## Agreement procedure (solo reviewer, see DECISIONS.md)

Two blind passes (A and B) over the same gold set, at least days apart, without
looking at the previous pass. Report per-field agreement and Cohen's kappa for
article type, passage type, and claim-boundary F1. Treat results as an upper bound;
a second human can re-run pass B from this guide alone.
