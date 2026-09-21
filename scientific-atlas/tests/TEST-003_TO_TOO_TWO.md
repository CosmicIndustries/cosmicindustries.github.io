# FORT KNOWLEDGE — TEST-003
## TO / TOO / TWO Semantic Disambiguation

Status: FOUNDATIONAL PASS CONDITION
Test date: 2026-09-21
Test class: homophone / orthography / semantics / non-linguistic grounding

## Why this test exists

"to", "too", and "two" are close in sound but differ in:
- orthographic form
- grammatical function
- semantic content
- historical development
- external grounding

A preservation or learning system that cannot distinguish these reliably cannot claim robust semantic recovery.

## 1. The three forms

### TO

Primary modern functions:
- preposition
- infinitival marker

Examples:
- "go to the archive"
- "to preserve"

Semantic roles:
- direction / relation
- grammatical infinitive marking

### TOO

Primary modern functions:
- additive meaning: "also"
- excess/intensity meaning: "more than desirable or necessary"

Examples:
- "the second copy is available too"
- "too much uncertainty"

Semantic roles:
- addition
- excess

### TWO

Primary modern function:
- cardinal numeral

Example:
- "two independent copies"

Semantic role:
- quantity = 2

## 2. The crucial distinction

In speech, the three forms can be homophonous in ordinary modern English.

Therefore:

SOUND
  ≠
MEANING

The system must use additional signals:
- orthography
- syntax
- context
- morphology
- semantic relations
- world knowledge
- numerical grounding

## 3. External grounding

"TWO" can be grounded without English.

For example:

● ●

and then:

●
●

Establish:
- one object
- another object
- total = two

Then connect the quantity to a symbol:

2

Then connect:
2 -> numeral concept -> word "two"

This makes "two" recoverable even if the English word disappears.

"TO" and "TOO" require linguistic/contextual grounding because their meanings are relational or grammatical rather than directly represented by a single natural number.

## 4. Adversarial sentences

### A

"I went to the archive."

Expected:
TO = relation/direction

### B

"I went too."

Expected:
TOO = addition

### C

"I went two times."

Expected:
TWO = quantity

### D

"To preserve two copies is useful too."

Expected:
- TO = infinitive marker
- TWO = quantity
- TOO = addition

### E

"Put two records to the left; keep one too."

Expected:
- TWO = quantity
- TO = spatial relation
- TOO = addition

## 5. Semantic corruption tests

The system must reject these silent substitutions:

"two" -> "to" because pronunciation matches

"too" -> "to" because sentence still looks plausible

"to" -> "two" because a numeral might fit semantically

Instead it should preserve:
- source spelling
- grammatical role
- semantic interpretation
- confidence
- source context

## 6. Historical drift test

The system must recognize that orthographic distinctions can encode information that pronunciation does not.

Preserve:
- historical spellings
- historical pronunciations when documented
- grammatical functions
- etymological relationships
- modern usage

Do not retroactively normalize all three into a single token.

## 7. Non-English test

The same concept should be tested in languages where:
- the three English forms do not exist
- the concepts are encoded differently
- grammar makes the distinctions explicit
- quantity is morphologically marked

This prevents the system from treating English structure as universal semantics.

## 8. Future-language test

A future language may have:
- one word for multiple current functions
- several words where English has one
- grammatical marking absent from English
- a different numeral system

The canonical layer must therefore be:

CONCEPT / RELATION
   ↓
LANGUAGE-SPECIFIC REALIZATION

not:

ENGLISH WORD
   ↓
"meaning"

## 9. Litmus pass condition

The learner/system passes when it can correctly explain all three:

TO = relational / infinitival function
TOO = addition or excess
TWO = quantity 2

and can explain why pronunciation alone is insufficient.

## 10. Deeper pass condition

It should then demonstrate:

2
  ↓
quantity concept
  ↓
English "two"
  ↓
other-language realization
  ↓
future-language realization

while retaining the original English form as historical evidence.

## 11. Failure modes this catches

- sound = meaning assumption
- spelling = meaning assumption
- word = concept assumption
- context ignored
- grammar ignored
- numerical concept not externally grounded
- historical form silently normalized
- English treated as universal
- translation mistaken for ontology

## 12. Fort Knowledge principle

**The archive must be able to distinguish the sound of a word from the shape of a word, the grammatical job of a word, and the concept the word points toward.**

The same sound does not imply the same object.

The same object does not require the same word.
