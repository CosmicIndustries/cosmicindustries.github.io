# FORT KNOWLEDGE — LITMUS TEST / EVIDENCE FLUENCY

Version: 0.1
Established: 2026-09-21

## Purpose

This test measures whether a learner can **distinguish evidence from assertion and navigate the archive's reasoning structure**.

It is not a knowledge gate.

A person may continue exploring the entire archive regardless of test result. The result only controls the **pace and scaffolding of explanation**.

The system never uses the test to decide who is worthy of access to ordinary knowledge.

## Core rule

**Claims are free to make. Accepted conclusions require evidence.**

An unsupported claim is not punished, censored, or treated as false merely because evidence is missing.

It is classified as:

- UNVERIFIED
- WEAKLY_SUPPORTED
- SUPPORTED
- STRONGLY_SUPPORTED
- CONTRADICTED
- DISCONFIRMED

A claim can move between states as new evidence arrives.

## 1. What the test checks

The minimum evidence-fluency competencies are:

1. Observation vs interpretation
2. Claim vs evidence
3. Primary vs secondary source
4. Source provenance
5. Correlation vs causation
6. Uncertainty / confidence
7. Contradictory evidence
8. Semantic / language drift
9. Identity and attribution
10. Reference frame / time scale
11. Prediction vs observation
12. Reproducibility / falsifiability

## 2. Diagnostic format

The test should be short and adaptive.

Recommended initial probe: **8 items**.

Each item can be answered in ordinary language.

Do not require domain-specific vocabulary.

### Item A — Observation

Source:
> A sensor recorded 18.4 °C at 14:00 UTC.

Question:
What is the strongest statement?

Expected reasoning:
The sensor recorded 18.4 °C at that time, subject to the instrument's calibration and provenance.

Common failure:
"The environment was exactly 18.4 °C."

This confuses an observation with a claim about the world.

### Item B — Evidence

Claim:
> "This archive proves the phenomenon exists."

Question:
What evidence would you request before accepting that conclusion?

Expected reasoning:
Ask for the primary measurement, provenance, methodology, controls, uncertainty, independent replication, and competing explanations.

Common failure:
"Who published it?" as the only evidence criterion.

### Item C — Correlation

Observation:
Two variables increased together for 30 years.

Question:
Does this establish causation?

Expected reasoning:
No. It establishes an association/correlation; causal inference requires additional design/evidence.

### Item D — Contradiction

Source A:
> The instrument detected X.

Source B:
> An independent instrument at the same time detected no X.

Question:
What happens to the claim?

Expected reasoning:
It becomes contested; investigate calibration, sensitivity, timing, location, method, and provenance rather than selecting a source by authority alone.

### Item E — Semantic drift

Historical record:
> "The planet was discovered in 1800."

Modern astronomy uses a different formal classification.

Question:
Should the historical sentence be rewritten?

Expected reasoning:
No. Preserve the historical wording and add a dated semantic/context layer.

### Item F — Prediction

Forecast:
> Object P has a 95% modeled arrival window in 2040.

Question:
What can be said before 2040?

Expected reasoning:
It is a prediction with a model and uncertainty, not an observed arrival.

### Item G — Identity

Two records use the name "A. Smith."

Question:
Can they be merged?

Expected reasoning:
Not from the name alone. Check dates, locations, affiliations, identifiers, provenance, and independent evidence.

### Item H — Evidence update

A claim begins as UNVERIFIED.

A new reproducible independent study supports it.

Question:
What should happen?

Expected reasoning:
Create a new evidence/provenance event and update the claim state; never rewrite the original history as though the new evidence always existed.

## 3. Scoring model

Do not produce a single intelligence score.

Score each competency independently:

0 = needs scaffolding
1 = partial understanding
2 = operational understanding

Total score is secondary.

The important output is a **reasoning profile**.

Example:

OBSERVATION_VS_INTERPRETATION: 2
CLAIM_EVIDENCE: 2
PROVENANCE: 1
CORRELATION_CAUSATION: 0
UNCERTAINTY: 1
SEMANTIC_DRIFT: 2
IDENTITY: 2
PREDICTION: 1

## 4. Pace adaptation

The learning engine responds to the profile.

### Stable understanding

0–1 weak areas:
- continue normal exploration
- introduce the next concept naturally

### Mixed understanding

2–3 weak areas:
- keep advancing
- add inline reminders
- present more worked examples
- occasionally ask a recall question

### Multiple weak areas

4+ weak areas:
- do not block access
- slow the density of new concepts
- provide shorter evidence chains
- repeat foundational distinctions in different contexts
- use one concept at a time

The learner continues at an **even pace appropriate to their demonstrated reasoning needs**.

## 5. Evidence response rule

When a learner makes an unsupported factual claim:

BAD:
> Wrong.

BETTER:
> Unverified. What source would let us test that?

If a reliable source contradicts the claim:

> Current evidence contradicts this claim. Here is the evidence and what remains uncertain.

The system should encourage revision without humiliating the learner.

## 6. Evidence debt

Every unresolved claim creates **evidence debt**.

Record:

claim_id
claim_text
current_status
missing_evidence
requested_test
supporting_sources
contradicting_sources
last_reviewed

A user can continue exploring while carrying evidence debt.

## 7. No knowledge gate

A person may:
- read advanced material
- inspect raw datasets
- explore graphs
- browse historical sources
- read competing interpretations
- ask questions beyond their current demonstrated understanding

The test only changes how much explanatory scaffolding is provided.

## 8. Claim promotion

A claim is eligible for promotion when the applicable evidence standard is met.

The standard can vary by claim type.

Examples:

Historical identification:
- provenance
- primary records
- independent corroboration where available

Physical claim:
- measurement
- methodology
- uncertainty
- controls
- replication where feasible

Computational claim:
- data
- code/version
- parameters
- reproducibility

Prediction:
- model
- observations
- uncertainty
- retrospective evaluation

Interpretation:
- source
- reasoning chain
- alternatives
- uncertainty

## 9. Automatic checks

The system should detect when a learner's answer:

- states an inference as an observation
- cites a claim as evidence for itself
- relies only on authority
- ignores contradictory evidence
- treats correlation as causation
- treats possibility as probability
- confuses a model with an observation
- merges identities without sufficient evidence
- silently translates historical language
- replaces an old version with a current version

These trigger teaching prompts rather than access denial.

## 10. Re-test behavior

Do not repeatedly ask the same question until the user gets it right.

Instead:
1. identify the weak concept
2. give a compact explanation
3. show a different example
4. ask for active recall
5. return to the original concept later

Use spaced recurrence.

## 11. Litmus-test success condition

The learner demonstrates operational evidence fluency when they can consistently:

- identify what is directly observed
- identify what is inferred
- request appropriate evidence
- express uncertainty
- consider counterevidence
- distinguish source from claim
- distinguish model from observation
- update beliefs when evidence changes
- preserve historical wording without confusing it with current meaning

This is not a final certification.

It is an indication that **less scaffolding is needed right now**.

## 12. Fort Knowledge principle

The purpose of education is not to decide who may know.

The purpose is to help more people **reason from evidence without slowing discovery**.

Everyone keeps access.

The archive simply adapts the explanation layer to the person's demonstrated reasoning state.
