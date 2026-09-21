# FORT KNOWLEDGE — 500-LANGUAGE NEXUS

Version: 0.1
Snapshot: 2026-09-21

## Goal

Create at least 500 independently identified language pathways into the same underlying knowledge graph.

The number 500 is a minimum cohort target, not a ranking of languages and not a claim that 500 is sufficient.

Glottolog 5.3 currently catalogs 7,674 spoken L1 languages, 227 sign languages, and additional languoid categories. The project therefore treats 500 as the first operational cohort within a much larger linguistic universe. citeturn180083search5

## Identity stack

Each language pathway uses the strongest available identifiers:

1. ISO 639-3 where applicable
2. Glottocode where mapped
3. BCP 47 language tag where applicable
4. CLDR locale data where available
5. community/autonym information
6. historical identifiers and retired codes

BCP 47/CLDR are used for software and locale identity; Glottolog provides linguistic classification and persistent Glottocodes. Unicode explicitly recommends documenting language identifiers with BCP 47 and related source evidence. citeturn483042search1turn483042search2

## Canonical semantics

No language is canonical.

The canonical object is the concept, observation, relation, entity, event, or measurement.

Example:

CONCEPT_0002
  ├── English: two
  ├── German: zwei
  ├── Cherokee: [source-backed rendering]
  ├── Japanese: [source-backed rendering]
  └── future language: [future rendering]

The bracketed entries are placeholders only until verified sources are attached.

## Language record requirements

A language record may contain:

- persistent identifier
- ISO 639-3
- Glottocode
- BCP 47 / CLDR identifiers
- autonym
- exonym
- script(s)
- orthographic variants
- historical stages
- dialect/variety relations
- geographic provenance
- speaker/community context
- pronunciation evidence
- source-backed concept renderings
- translations
- semantic ambiguities
- historical terminology
- rights/restrictions
- last verification date

## Rendering states

METADATA_ONLY
SOURCE_BACKED
COMMUNITY_REVIEWED
HISTORICAL_ATTESTATION
MULTIPLE_VALID_FORMS
DISPUTED
ENDANGERED_DOCUMENTATION
RETIRED_IDENTIFIER
UNATTESTED
PENDING_REVIEW

A registered language with no translation is still a valid registry record.

A generated translation without evidence is not a valid rendering.

## Concept rendering

Every rendering must identify:

- concept_id
- language
- exact form
- sense
- grammatical category
- script
- pronunciation where documented
- historical date/range where relevant
- source
- source date
- confidence
- reviewer
- alternatives

## Historical language

Never overwrite historical forms.

Instead:

historical_form
    -> dated sense
    -> concept_id
    -> later form
    -> modern form

This allows semantic drift to remain visible.

## Ambiguity

The system must support:

one form -> multiple concepts
one concept -> multiple forms
one sound -> multiple spellings
multiple sounds -> one historical orthography

The archive must never resolve an ambiguity silently when the competing readings materially affect meaning.

## Culture graph

Every language can connect to:

- people
- places
- historical periods
- artifacts
- work
- technology
- institutions
- literature
- science
- migration
- neighboring languages
- contact zones
- semantic borrowing

The point is not to reduce culture to vocabulary.

It is to make the historical world around the language discoverable.

## Coverage

The 500-language cohort should deliberately expand across:
- language families
- isolates
- macroareas
- sign languages
- endangered languages
- historical languages
- major modern languages
- languages with rich archival documentation
- languages with sparse documentation

Coverage decisions must be documented instead of implied.

## No machine-generated authority

Machine translation may produce a candidate rendering.

It cannot promote itself to authoritative status.

Promotion requires:
- source evidence
- linguistic validation where appropriate
- attribution
- uncertainty state

## Long-term preservation

Language metadata must remain useful even when:
- a code is retired
- a script changes
- a language splits/merges in classification
- a community adopts another name
- a locale changes
- CLDR changes inheritance/canonicalization
- a dictionary disappears
- a recording repository moves

Retain old identifiers and old source states.

## Bootstrap role

The language nexus sits above the invariant layer:

MATHEMATICS
    ↓
PHYSICAL RELATIONS
    ↓
SYMBOLS
    ↓
CONCEPTS
    ↓
LANGUAGE
    ↓
CULTURE / HISTORY

English is one leaf in the tree, not the trunk.

## Public access

The registry and ordinary educational renderings are public by default where rights permit.

Sensitive recordings, culturally restricted material, or protected personal data follow the applicable rights and community rules without destroying the existence of their provenance record.

## Source datasets

Primary federated references:
- Glottolog 5.3
- ISO 639
- Unicode CLDR
- BCP 47
- community-authored dictionaries/grammars
- archival recordings
- historical manuscripts
- linguistic corpora

Glottolog 5.3 is available in downloadable CSV/CLDF forms and is archived with a DOI. citeturn180083search0turn180083search2turn180083search6

## Principle

**500 languages are not 500 translations. They are 500 doors into the same evidence graph.**

Each door keeps its own history, sound, script, culture, uncertainty, and provenance.
