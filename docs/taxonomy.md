# TAXONOMY (M0)

Definitions with examples and edge cases. These are normative: the labeling guide
(`docs/labeling-guide.md`) and every automated stage must implement exactly these.
Goal is transparency, not a claim of perfect neutrality.

---

## 1. Fact

A statement that can, in principle, be checked against observable reality: an event
that happened, a quantity, an official record, or a verifiable attributed statement.

- Factual: "The committee voted 6–3 to approve the measure."
- Factual: "According to the interior ministry, 42 people were arrested."
- Not factual: "The committee shamefully caved." (evaluation, not checkable)
- Not factual: "The measure will devastate the economy." (prediction)

A fact may still be *wrong*; falsity does not make something non-factual. "The ministry
said 42" can be false as an event claim and still be a fact that *it was said*.

## 2. Claim

One atomic, verifiable proposition, extracted from a passage, anchored to an exact
character span of that passage. A claim is the unit the ledger matches across sources.

- Atomic = one proposition. "Police arrested 42 protesters after the march turned
  violent" is **two** claims (arrest with quantity; violence of the march), because each
  can be independently true or false.
- If a candidate claim cannot be anchored to an exact span, it is **rejected**, not fixed
  by inference (spec §10: never invent or fill in).

Claim types:

| Type | Definition | Example |
| --- | --- | --- |
| event | something happened / an action occurred | "The central bank raised rates on Tuesday." |
| quantity | a countable or measurable amount | "Unemployment rose to 4.3%." |
| statement | words publicly uttered/written by an identifiable party | "The minister said the report was flawed." |
| causal | asserts one thing caused another | "The strike caused fuel shortages." |

Causal claims are held to the highest corroboration bar: they require either a primary
record or independent secondary confirmation, never a single paraphrased wire.

## 3. Attribution layer

Every attributed statement is stored as **two separate claims** (spec §3.2):

1. **Assertion layer** — that the statement was made: "The minister said X." (event type)
2. **Content layer** — what was actually said: "X." (type depends on X)

"A meteorologist said the storm will make landfall Friday" produces:
- L1 (event/statement): a meteorologist publicly said [content].
- L2 (prediction): the storm will make landfall Friday.

The content layer of an attributed claim is never promoted to fact without independent
confirmation. Anonymous attribution ("sources said", "critics argue") keeps layer 1 with
attribution marked `anonymous`.

## 4. Opinion, analysis, sponsored

- **Opinion**: evaluates, prescribes, or judges. First-person or attributed to a
  commentator's own view. Signal words: should, must, shameful, thankfully, "in my view".
- **Analysis**: explains or interprets facts, stops short of prescription. Uses reported
  material but its load-bearing content is interpretation ("the move signals…",
  "the timing suggests…"). Analysis is factual in *parts*; those parts are labeled at
  passage level (§6), the article as a whole is still `analysis`.
- **Sponsored**: paid placement, "sponsored", "paid content", partner content, brand
  studio labels — regardless of how factual it reads.
- **Satire**: labeled, excluded from everything except a note.

Rule (spec §6 triage): opinion, analysis, and sponsored articles are excluded from the
fact base. Only their **observed-event / quantitative / attributed-statement passages**
may feed claims — and only when a passage is factual on its own terms; the article label
controls default routing, passage label controls exceptions.

## 5. Loaded language and neutralization

**Loaded language** is wording whose emotional or evaluative charge is not itself
checkable: intensifiers ("crushing", "massive" — unless the scale is the fact),
emotive adjectives ("brazen", "tragic"), charged verbs ("seized" vs "took office",
"slammed" vs "criticized"), scare quotes, loaded labels ("regime", "freedom fighter"),
insinuation by juxtaposition.

**Neutralization** rewrites a claim into plain, measurable wording and records
`list_of_changes` (original span → replacement → category → rationale).

Hard rules (spec §6):

- **Emotion that is itself the fact stays.** "Three protesters were hospitalized"
  remains: hospitalization is checkable. "Grieving families gathered" keeps "grieving"
  only if emotional state is documented, else it is flagged/removed.
- Never change meaning; run a meaning-preservation check; on failure keep the original
  and flag it (`neutralization_status: flagged`).
- Neutralized wording is **never shown without** the original wording and change list.

## 6. Passage types

| Type | Definition | Feeds fact base? |
| --- | --- | --- |
| observed event | directly reported occurrence | yes |
| quantitative | numbers, measurements, dates, tallies | yes |
| attributed statement | quote or paraphrase of identifiable speech/writing | yes (two layers) |
| interpretation | analysis, motive, significance | no — labeled, held separately |
| prediction | future assertion, incl. attributed ones | no — labeled, held separately |
| rhetoric | questions to the reader, exclamations, calls to action | no |

## 7. Core fact

A claim selected for the event brief because it answers one of: what, who, when,
where, how many, what is officially confirmed. Selection ranks by corroboration
(independent origins) and centrality to the event — **never by emotional pull**
(spec §6). Before output, an omission audit checks that dropped candidate core facts
were excluded by rule, not by salience.

## 8. Independent origin

Two sources count as independent only if neither traces its report to the other
(same wire copy, same press release, same interview). Republishing is recorded in
`links to duplicates or republished-from` and contributes **zero** to the
independent-origin count (spec §3.5: independence is counted, not volume).

## 9. Contradiction and omission

- **Contradiction**: equivalent claims disagreeing on number, time, actor, or outcome.
  Both versions are shown side by side; tier 4 (disputed).
- **Omission**: a fact present in some sources' coverage and absent in others'.
  Omissions are recorded in the ledger; absence of coverage is not itself evidence.

## 10. Confidence tiers

| Tier | Name | Bar |
| --- | --- | --- |
| 1 | primary-confirmed | confirmed by a primary source (official record, filing, transcript) |
| 2 | independently corroborated | ≥2 independent origins, no unresolved contradiction |
| 3 | single-source | exactly one independent origin, no contradiction |
| 4 | disputed | equivalent claims contradict; both versions shown |
| 5 | unverified / retracted | separate section only, never mixed into core facts |

Corrections and retractions by a source lower that source's claims pending re-evaluation;
a correction history is part of every Source record.

## 11. Article types

reporting / analysis / opinion / sponsored / satire — as in §4, assigned at item level
with the labeler's evidence noted (signal phrases, section, byline role).

---

Worked example end-to-end (one sentence): *"In a bombshell move, the 'so-called
independent' regulator fined the tech giant a staggering $2 billion, which experts
say will cripple it," the minister triumphantly announced.*

- Article type depends on the whole item; this sentence contains:
  - observed event: regulator fined company $2bn ✓
  - attributed statement (two layers): minister announced the fine / minister's framing
  - interpretation: "experts say will cripple it" → held, not a fact
  - rhetoric/loaded: "bombshell", "so-called", "staggering", "triumphantly" →
    neutralized with change list; "fined … $2 billion" survives unchanged
