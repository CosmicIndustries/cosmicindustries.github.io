# Scientific Data Atlas — Language Drift & Semantic Longevity Protocol

Version: 0.1
Established: 2026-09-21

## Purpose

The archive must survive not only storage and software change, but changes in human language.

A document can remain perfectly intact while becoming functionally unreadable because:
- words change meaning
- technical terminology changes
- grammar changes
- spelling changes
- scripts change
- place names change
- institutions change names
- scientific taxonomies are revised
- units and calendars change
- translations acquire different interpretations
- concepts disappear from common knowledge

Therefore language preservation is treated as a **scientific preservation problem**, not merely a text-encoding problem.

## Fundamental rule

**Never replace historical language with modern language.**

The original representation is immutable evidence.

Modern transcriptions, normalizations, translations, glosses, definitions, entity mappings, and machine interpretations are separate derived objects.

Historical text -> transcription -> linguistic annotation -> dated gloss -> semantic concept mapping -> modern interpretation

Every layer must remain reversible.

## 1. Five preservation layers

### Layer 0 — Original representation

Preserve the exact source whenever possible:
- scan
- photograph
- audio
- video
- manuscript
- inscription
- original digital text
- original encoding
- original punctuation
- original capitalization
- original spelling
- marginalia
- corrections
- layout when semantically relevant

Never discard illegible or uncertain characters. Mark uncertainty explicitly.

### Layer 1 — Diplomatic transcription

Create a transcription intended to reproduce the source rather than modernize it.

Preserve:
- original spelling
- word breaks when known
- abbreviations
- punctuation
- capitalization
- deletions
- insertions
- supplied characters
- uncertain readings
- editorial interventions

Every transcription unit should point back to a source location when possible.

### Layer 2 — Linguistic normalization

Create an explicitly labeled normalized representation.

Possible fields:
- normalized spelling
- expanded abbreviation
- morphological analysis
- part of speech
- lemma
- historical dictionary reference
- language/sub-language
- script
- writing system variant
- date/period of usage

Normalization is a derivative, never a replacement.

### Layer 3 — Sense mapping

Words do not equal concepts.

Create stable concept nodes with:
- concept_id
- historical term
- language
- date range
- definition at that date
- source definition
- domain
- narrower/broader relationships
- related modern terms
- confidence
- interpreter/source

The same spelling may point to different concepts at different times.

Conversely, different historical words may point to approximately the same concept.

Therefore mappings must be time-aware.

### Layer 4 — Modern interpretation

A modern-language explanation may be generated.

It must record:
- interpreter
- interpretation date
- source language
- target language
- translation method
- model/tool and version when machine-assisted
- model hash when available
- prompt/instructions when materially relevant
- supporting references
- confidence
- unresolved ambiguity

A modern translation is evidence about an interpretation, not evidence that the original author meant exactly that modern wording.

## 2. Language identity

Use persistent standards-based language identifiers rather than relying on names.

Use BCP 47/IETF language tags where applicable and ISO 639 identifiers where appropriate. ISO 639 explicitly covers living, extinct, and ancient languages in its language-code system, while BCP 47 provides structured, backward-compatible language tags. citeturn881415search1turn881415search2

Store the exact language tag used at ingest.

Do not silently replace an older or deprecated language tag. Instead record:
- original_tag
- current_preferred_tag
- tag_registry_version
- mapping_event

BCP 47 explicitly provides mechanisms for deprecated values and preferred values while preserving interoperability. citeturn881415search2

## 3. Unicode and character preservation

Store source text in Unicode while preserving the original representation.

For normalized processing, record:
- normalization_form
- Unicode_version
- normalization_timestamp

Do not apply compatibility normalization destructively to archival text.

Unicode's stability policies are specifically designed so encoded characters are not removed or reassigned, and normalized strings have long-term stability guarantees. citeturn750253search1turn750253search4

For maximum preservation:
- original_bytes
- decoded_text
- NFC_derivative
- optional NFD_derivative
- original_encoding
- decoder/software version

remain distinguishable.

## 4. Diachronic lexicon

Maintain a versioned historical lexicon rather than a single dictionary.

Lexical record:

term_id
surface_form
lemma
language
script
region
first_attested
last_attested
sense_id
definition
definition_source
usage_examples
etymology
modern_equivalents
related_terms
status

Meaning relationships:

same_spelling_different_sense
historical_predecessor
modern_successor
semantic_narrowing
semantic_broadening
semantic_shift
metaphorical_extension
technical_redefinition
obsolete_term
revived_term
loanword
false_friend

A term may have multiple simultaneous senses.

## 5. Time-bounded meanings

Every important definition receives a validity interval when evidence permits.

Example:

term: "planet"

1800s concept
    -> historical scientific definition

1930-2006 concept
    -> another formal classification

2006-present concept
    -> current astronomical classification

The archive preserves all three.

A modern search engine must not rewrite the historical definition to the contemporary one.

## 6. Translation triangulation

For historically important or ambiguous material, prefer multiple independent interpretations.

Example:

Original
   ├── expert translation A
   ├── expert translation B
   ├── machine translation
   └── historical dictionary gloss

Then compare:

agreement
ambiguity
irreducible uncertainty
possible false cognate
conceptual mismatch

Where interpretations disagree, preserve the disagreement.

Do not vote it away into a single "best" translation unless independently justified.

## 7. Semantic checksum

Each major record should have a machine-readable **semantic checksum** made from durable, interpretable components:

- named entities
- quantities
- units
- dates
- geographic references
- measured variables
- relationships
- domain terms
- claims
- negations
- uncertainty expressions

The checksum is not a replacement for the text.

It is a second route for a future researcher to reconstruct what the passage was about.

## 8. Structured scientific meaning

For scientific records, extract concepts into explicit fields.

Example:

Historical text:
"the barometer fell two inches before the great storm"

Preserved interpretation:

variable = atmospheric_pressure
measurement = -2
unit = historical_inch_of_mercury
event = storm
temporal_relation = before
confidence = documented

Then preserve mappings for:
- historical unit
- modern SI equivalent
- conversion source
- uncertainty
- regional conventions

Never silently convert historical measurements and discard the original unit.

## 9. Non-language drift

The same framework applies to things that behave like language:

- units
- currencies
- calendars
- time zones
- place names
- political boundaries
- institutional names
- species names
- chemical nomenclature
- astronomical object classifications
- medical terminology
- engineering standards

Every normalized value should point backward to its historical representation.

## 10. Knowledge graph semantics

Semantic edges must be versioned.

Example:

OLD_TERM
  --used_for--> CONCEPT_123
  --valid_during--> 1880-1912

CONCEPT_123
  --later_redefined_as--> CONCEPT_456

CONCEPT_456
  --modern_related_term--> MODERN_TERM

This avoids the catastrophic archival error:

**old word = current concept**

## 11. Machine interpretation preservation

Language models and translation systems are themselves historical artifacts.

For every important machine-derived interpretation preserve:

- model/provider
- model version
- model identifier
- model hash when available
- system/instruction context when available
- input hash
- output hash
- generation date
- temperature/randomness settings when relevant
- tools/retrieval sources
- evaluator
- human verification status

Never rely on a future model reproducing today's interpretation.

The original output is itself an archival derivative.

## 12. Embeddings are disposable derivatives

Embeddings are useful for discovery and cross-correlation but are not canonical semantic truth.

Preserve:
- embedding model
- model version
- vector dimensions
- vector hash
- generation date
- preprocessing
- normalization
- similarity metric

When models change, regenerate embeddings while retaining old vectors.

The semantic graph survives the embedding model.

## 13. Linguistic drift detection

Run periodic analysis for:
- newly obsolete terms
- changing word frequencies
- changed definitions in authoritative dictionaries
- changing entity names
- changed language tags
- newly preferred terminology
- translation disagreement
- terminology drift between linked datasets
- changed scientific classifications

Drift detection creates a preservation event; it does not rewrite historical content.

## 14. Future-reader bootstrap

Every major collection should include a plain-language glossary explaining:
- language used
- script
- approximate historical period
- common abbreviations
- specialized vocabulary
- obsolete terms
- units
- calendars
- geographic names
- institutional names
- known translation hazards

The glossary itself is versioned and preserved.

## 15. Core rule

**Preserve the words. Preserve the meanings they carried at the time. Preserve later meanings. Preserve the uncertainty between them.**

The archive should allow a researcher in the year 2400 to reconstruct both:

"What did the author actually write?"

and:

"What did those words most likely mean to that author, in that place, at that time?"

without requiring the researcher to trust an undocumented translation layer created centuries earlier.
