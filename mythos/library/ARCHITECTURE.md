# MYTHOS Virtual Library Architecture

## Purpose
MYTHOS is evolving from a static evidence atlas into a layered historical memory system.

The architecture deliberately separates:
1. Human-readable transcript — the archival record.
2. Structured evidence object — claims, dates, provenance, relationships.
3. Associative index — HRR/VSA-compatible vectors for approximate retrieval and relationship discovery.
4. Visual projection — maps, timelines, motif graphs and confidence layers.
5. Source graph — the provenance network connecting records to primary and secondary evidence.

## The two-generation idea

### Generation A — Library civilization
Humans can browse, read, compare and audit records without understanding the machine representation.

### Generation B — Associative civilization
The corpus can be queried by concepts, motifs, chronology and relationships even when the exact words differ. The machine representation becomes a navigational substrate rather than the authoritative record.

The machine layer never silently overwrites the archival layer.

## HRR role

Holographic Reduced Representations encode structured relationships in fixed-width distributed vectors using operations such as binding and circular convolution, bundling, and approximate recovery.

MYTHOS uses the HRR layer as an index, not as a source of truth.

A useful conceptual encoding is:

MEMORY = SUM bind(ROLE_r, VALUE_r)

Roles can include:
TITLE, ERA, CULTURE, STATUS, MOTIF, CLAIM, EVIDENCE, LOCATION, TECHNOLOGY

Similarity provides candidate associations. A candidate association must return to the transcript/source graph for verification.

## Visual cognition rule

The interface should reveal complexity progressively:

Level 1: one-line result
Level 2: summary + evidence state
Level 3: transcript + source chain
Level 4: relationships / nearest neighbors
Level 5: full historical graph

This is intentional. The corpus can become enormous without forcing every reader to see the entire graph simultaneously.

## Transcript rule

Every durable record should answer:
- What is the claim?
- Who/what is the source?
- When was it attested?
- What independent evidence exists?
- What contradicts it?
- What remains unknown?
- What later interpretations were added?
- What other records might be related?
- What changed in the revision history?

## Provenance hierarchy

Primary physical/documentary evidence > direct scholarly analysis > comparative synthesis > hypothesis.

A vector similarity score never outranks documentary provenance.

## Planned corpus hierarchy

deep-time/
prehistoric/
ancient/
late-antique/
medieval/
early-modern/
industrial/
modern/
archives/
technology/
mythology/
religion/
folklore/
fabrication/
memory/
environment/
migration/

These are overlapping indexes, not mutually exclusive folders. A Roman concrete record belongs simultaneously to ancient history, technology, materials science and recovered knowledge.

## Current status

Corpus Pack 01 provides the first scalable test dataset.

The browser prototype currently performs deterministic 256-dimensional HRR-style encoding over role/value tokens and displays nearest associative neighbors.

This is intentionally a small prototype. Production HolographicVDB should move vector generation, cleanup memory, provenance graphing and indexing into a dedicated persistent service.