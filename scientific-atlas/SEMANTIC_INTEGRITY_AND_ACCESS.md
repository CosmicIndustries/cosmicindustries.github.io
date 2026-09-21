# Scientific Data Atlas — Semantic Integrity, Narrative & Access Protocol

Version: 0.1
Established: 2026-09-21

## Purpose

A long-lived archive can preserve every byte and still corrupt history if it:
- mistakes a flattering story for evidence
- mistakes condemnation for evidence
- silently modernizes historical identities
- repeats propaganda without context
- turns villains into heroes
- turns imperfect people into saints
- erases morally relevant context because it is uncomfortable
- hides contested evidence rather than preserving it

The Atlas therefore treats **semantics, narrative, evidence, and moral interpretation as separate but connected layers**.

## 1. Core rule

**Preserve the person, preserve the claim, preserve the evidence, preserve the narrative, preserve the correction.**

Do not preserve a narrative as though it were automatically the truth.

A historical account may say:

> "He was a gentle and generous man."

The archive may preserve that statement exactly.

It may also preserve:
- who made the statement
- when it was made
- what evidence the author cited
- independent evidence
- contradictory testimony
- later scholarship
- documented actions
- uncertainty
- provenance

The archive should never silently transform a statement of praise into an established fact.

## 2. No glorification / no demonology

The Atlas must not function as a memorial cult or a condemnation engine.

Do not:
- celebrate atrocities
- romanticize perpetrators
- create heroic mythology around abusive or destructive conduct
- erase crimes because a person had admirable traits
- erase admirable or humane actions because a person also committed serious wrongdoing
- flatten complex historical actors into cartoon saints or monsters

This is not moral relativism.

It is an epistemic rule:

**describe the evidence first; characterize the morality through documented actions and consequences rather than propaganda language.**

## 3. Identity disambiguation

Names are not identities.

Every important person/entity record should distinguish:

- canonical identity
- aliases
- transliterations
- titles
- pseudonyms
- mistaken identities
- historical names
- later names
- organization affiliations
- dates
- locations
- source confidence

Example structure:

PERSON_A
  ├── canonical identity
  ├── historical names
  ├── aliases
  ├── disputed attribution
  ├── actions
  ├── claims about person
  └── evidence for each claim

Never merge two people solely because their names resemble one another.

Never infer guilt or innocence from an alias.

## 4. Claim/evidence separation

Every narrative assertion should ideally resolve to:

CLAIM
  ↓
CLAIMANT
  ↓
DATE
  ↓
SOURCE
  ↓
EVIDENCE
  ↓
COUNTEREVIDENCE
  ↓
CURRENT ASSESSMENT

The assessment must retain uncertainty.

Suggested states:

- DOCUMENTED
- WELL_SUPPORTED
- SUPPORTED
- DISPUTED
- WEAKLY_SUPPORTED
- UNCORROBORATED
- CONTRADICTED
- DISCONFIRMED
- FABRICATED
- UNKNOWN

These are evidence states, not moral scores.

## 5. Narrative as a data object

Stories are important because they are memorable.

The Atlas should preserve narrative forms because they are powerful mnemonic containers.

But every story receives explicit metadata:

- narrative_id
- source
- author
- date
- audience
- genre
- purpose when documented
- historical context
- claims extracted
- evidence links
- rhetorical devices
- known distortions
- later corrections

A story can be retained for its mnemonic value without being elevated to historical fact.

## 6. Mnemonic preservation

For difficult scientific or historical material, the Atlas may deliberately create:

- stories
- metaphors
- diagrams
- visual mnemonics
- songs/poems where appropriate
- timelines
- analogies
- symbolic narratives

Each mnemonic is labeled:

MNEMONIC_DERIVATIVE

and links back to:

CANONICAL_EVIDENCE

A mnemonic must never silently replace the canonical representation.

## 7. "Beautiful but wrong"

A persuasive story can be false.

The Atlas should explicitly preserve examples where:
- an elegant theory failed
- a famous account was exaggerated
- a charismatic authority was wrong
- a compelling narrative hid contradictory measurements
- a later correction changed interpretation

This is valuable because future readers need protection against the same cognitive failure.

## 8. "Ugly but true"

The reverse is equally important.

The Atlas should not suppress reliable evidence because it is:
- unpleasant
- embarrassing
- politically inconvenient
- culturally uncomfortable
- morally disturbing

The standard is evidence and lawful preservation, not aesthetic comfort.

## 9. Moral context layer

Moral interpretation should be represented explicitly rather than embedded invisibly in prose.

For documented harmful conduct, record:

- action
- victim/affected population
- date/time
- location
- mechanism
- evidence
- consequences
- legal finding when applicable
- historical interpretation
- disputed elements
- uncertainty

This produces stronger semantics than simply attaching labels such as "evil."

The archive may preserve historical descriptions such as "hero," "monster," "saint," or "tyrant" as source language, but should not silently adopt them as neutral metadata.

## 10. Just vs wicked

The archive should not attempt to compute a universal moral score for every historical person.

Instead, preserve:
- documented behavior
- stated beliefs
- consequences
- testimony
- legal records
- independent scholarship
- competing interpretations
- unresolved questions

Where a moral judgment is broadly supported by documented conduct, describe the conduct directly.

For example:

BAD:
  "He was a monster."

BETTER:
  "Records document X, Y, and Z, which caused A and B; sources disagree about C."

The second survives changes in moral vocabulary.

## 11. Semantic warning labels

Records can carry non-ranking warnings such as:

- PROPAGANDA_CONTEXT
- SELF_DESCRIPTION
- HAGIOGRAPHIC_SOURCE
- POLEMICAL_SOURCE
- FICTIONALIZED
- UNRELIABLE_NARRATOR
- POSTHOC_MYTH
- DISPUTED_ATTRIBUTION
- RETRACTED
- DEBUNKED
- HISTORICAL_CONTEXT_REQUIRED
- MINORITY_INTERPRETATION
- CONSENSUS_SUPPORTED

Warnings must point to their evidence and source.

## 12. No retroactive sanitization

Do not rewrite historical records into modern approved language.

Instead:

ORIGINAL
  ↓
TRANSCRIPTION
  ↓
CONTEXTUALIZATION
  ↓
MODERN EXPLANATION

Offensive, obsolete, euphemistic, propagandistic, or archaic wording may need contextual notes, but the original remains preserved where lawful.

## 13. Free public access

The default principle is:

**knowledge should be broadly and freely accessible.**

The Atlas should not require users to adopt a political, religious, cultural, or institutional worldview in order to access ordinary historical and scientific information.

However, public access is bounded by:
- privacy
- intellectual-property law
- human-subject protections
- cultural or indigenous data sovereignty
- legitimate security restrictions
- dangerous operational material where publication creates substantial foreseeable harm

These constraints should be explicit and documented rather than hidden behind vague moral judgments.

## 14. Do not infer intent

A system cannot reliably know a visitor's inner intentions from a request alone.

Therefore access decisions should not depend on a secret "good person" classifier.

Use objective controls instead:
- content classification
- legal restrictions
- safety policy
- authentication for controlled collections
- rate limits
- audit logs
- human review where genuinely required

Ordinary scientific knowledge should remain open by default.

## 15. No retaliation

The Atlas must never retaliate against a user for an allegedly unjust request.

Do not:
- send malware
- send malicious packets
- damage user systems
- deanonymize users
- retaliate against infrastructure
- fabricate evidence
- punish access attempts outside the documented security policy

Security controls should be defensive, transparent, proportionate, and independently auditable.

## 16. "Fort Knox of knowledge"

The metaphor should be interpreted as:

- exceptionally well protected
- redundantly preserved
- difficult to destroy
- difficult to silently alter
- broadly accessible
- independently auditable
- resistant to censorship and historical revisionism

It must NOT mean:
- secret
- owned by one authority
- accessible only to insiders
- controlled by an ideological gatekeeper

The archive's strongest defense is **distributed custody + cryptographic integrity + radical provenance transparency**.

## 17. Intent-preserving access model

Use four independent dimensions:

ACCESS = rights × safety × privacy × integrity

Do not replace this with:

ACCESS = guessed_user_intent

This permits the archive to remain open while still protecting people and critical systems.

## 18. Semantic checksum

For important records preserve a machine-readable semantic representation:

- who/what
- action/state
- time
- place
- measurement
- quantity
- units
- affected entities
- cause/effect claims
- uncertainty
- source
- counterevidence

This gives future languages a stable substrate for translation.

## 19. Example of historical integrity

Suppose a source portrays a political or historical figure as a "kind gentleman."

The Atlas can preserve:

SOURCE CLAIM:
  "kind gentleman"

SEMANTIC TYPE:
  positive_characterization

CLAIMANT:
  source author

DATE:
  source date

EVIDENCE:
  cited examples

COUNTEREVIDENCE:
  independent records

DOCUMENTED ACTIONS:
  event records

LATER INTERPRETATION:
  dated assessment

The system does not erase the flattering description.

It also does not let the flattering description overwrite the evidence.

## 20. Example of harmful actor representation

If substantial evidence establishes atrocities or other serious abuses, the Atlas should preserve:
- the person's self-description
- contemporaneous propaganda
- sympathetic accounts
- documented conduct
- victim testimony
- independent records
- later scholarship

The purpose is not to humanize wrongdoing into innocence.

The purpose is to make the historical record difficult to falsify.

## 21. Moral memory is not moral monarchy

The Atlas should preserve moral lessons without appointing itself humanity's permanent moral sovereign.

A future civilization may have:
- different language
- different institutions
- different philosophical terminology
- different customs

The underlying evidence should remain available so that future people can reason from it.

## 22. Core principle

**Do not glorify the wicked. Do not falsify the record to flatter the just. Do not erase uncomfortable truth. Do not turn stories into evidence. Do not erase stories either. Preserve the evidence, preserve the narrative, connect them, and let future readers understand why the difference matters.**
