# Scientific Data Atlas — Longevity & Succession Protocol

Status: foundational
Established: 2026-09-21
Design horizon: centuries to millennia
Primary goal: preserve scientific evidence, provenance, uncertainty, and relationships across technological and institutional change.

## 1. Foundational rule

The atlas is not the website.

The website is a view of the archive.

The canonical object is the evidence package:
- observations and source files when legally distributable
- complete metadata
- provenance
- version history
- integrity manifests
- scientific claims and counterclaims
- correlation/relationship edges
- uncertainty and validation notes
- documentation needed to interpret the above

A future custodian must be able to reconstruct the atlas without this website, GitHub, this organization, or the original software.

## 2. No single point of survival

Never rely on one:
- company
- person
- Git forge
- cloud provider
- domain
- database engine
- file format
- geographic site
- funding source
- cryptographic service

Public preservation copies should be geographically, organizationally, and technologically independent.

The target is at least four independent preservation copies for the living corpus, with additional copies preferred for exceptional records.

## 3. Open, boring formats

Human-facing records should remain available in:
- UTF-8 plain text
- Markdown
- CSV
- JSON
- JSON Schema

Large scientific arrays should additionally use well-documented open scientific formats appropriate to the measurement type.

Do not make proprietary software required to understand the archive.

## 4. Every object gets an identity

Prefer persistent identifiers when available:
- DOI for citable datasets and releases
- SWHID for software artifacts
- source-provided identifiers such as catalog numbers, station IDs, accession numbers, specimen IDs, plate IDs, or archive identifiers
- local immutable Atlas IDs for records without external identifiers

Never use a mutable URL as the sole identity of an object.

## 5. Every release gets a manifest

Every public corpus release must contain:
- file path
- byte size
- cryptographic digest
- media type
- creation/update time
- source identifier
- license or rights statement
- provenance
- schema version
- atlas release version

A future custodian must be able to determine whether a recovered copy is identical, incomplete, or modified.

## 6. Preserve the history of change

Never silently overwrite scientific evidence.

When a source changes:
1. retain the previous metadata or snapshot when legally possible
2. create a new version
3. record when the change was observed
4. identify the old and new locations
5. describe what changed
6. record evidence for the change
7. distinguish source change from scientific reinterpretation

A dead URL is not equivalent to a lost dataset.

## 7. Preserve disagreement

The archive must preserve:
- supporting evidence
- contradictory evidence
- failed replications
- corrections
- retractions
- alternative interpretations
- unresolved questions

The system must not convert uncertainty into a binary true/false field merely for convenience.

## 8. Cross-correlation is part of the record

Relationships are first-class evidence.

Examples:
- independently_confirms
- contradicts
- same_phenomenon
- same_instrument
- same_method
- same_region
- temporal_overlap
- shared_provenance
- modern_method_unlocks
- historical_predecessor
- methodological_analogue
- shared_data_loss_pattern

Each edge should carry:
- source IDs
- relationship type
- evidence
- confidence
- creation/verification time
- human or algorithmic provenance

A relationship is not a causal claim unless causal evidence exists.

## 9. Human-readable bootstrap

Every preservation package must contain enough documentation for a technically competent stranger to understand:
- what the archive is
- directory structure
- record schema
- controlled vocabularies
- identifiers
- integrity checks
- versioning rules
- how to render the data
- how to migrate obsolete formats
- who currently stewards it
- how succession works

Include a plain-text bootstrap document that does not depend on a web browser.

## 10. Succession

The founder is not a required component.

Stewardship should be transferable through:
- documented governance
- public issue/change records
- multiple maintainers or institutions
- public recovery instructions
- reproducible release tooling
- independent mirrors
- explicit succession procedures

If Cosmic Industries ceases to exist, the archive should remain recoverable.

## 11. Periodic preservation tests

At scheduled intervals:
- restore a complete copy from preservation media
- verify manifests
- test schema validity
- rebuild indexes
- render a sample of records
- validate cross-reference integrity
- test that identifiers still resolve where possible
- record the test result publicly

A backup that has never been restored is an assertion, not evidence.

## 12. Migration

When a format, database, dependency, or service becomes obsolete:
- preserve the original
- create a migrated representation
- validate equivalence
- record conversion software and version
- retain migration logs
- repeat when necessary

Never destroy the old representation merely because a new one is more convenient.

## 13. Legal and ethical durability

Preservation does not override:
- copyright
- privacy
- human-subject protections
- indigenous data sovereignty
- specimen restrictions
- security restrictions
- safety requirements

When the underlying object cannot legally be redistributed, preserve the maximum lawful metadata, provenance, identifier, finding aid, checksum where permitted, and location information.

## 14. The website is disposable

The web interface may be replaced completely.

A future interface should be able to consume the archive from its machine-readable releases without changing the underlying record model.

## 15. The scientific objective

The long-term purpose is not to accumulate mysteries.

It is to make neglected evidence discoverable, testable, reproducible, falsifiable, and connectable across generations.

The archive should help a researcher centuries from now answer:

- What was observed?
- Where did it come from?
- Who measured it?
- What changed?
- What was lost?
- What survived?
- What contradicted it?
- What other evidence connects to it?
- What can be reanalyzed with newer methods?
- How certain are we?
- Can I verify this myself?

If those questions can still be answered, the atlas has survived.
