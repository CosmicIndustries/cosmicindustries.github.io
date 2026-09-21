# SYSTOS

**Semantic Atlas of Human Systems**

SYSTOS is a machine-readable atlas of systems created, practiced, imposed, evolved, or imagined by humans.

It covers institutions, organizations, communities, laws, economies, governance structures, knowledge systems, technologies, networks, resource systems, cultural structures, illicit systems, and emergent systems.

## Core principle

A **system** is the primary object.

An institution, organization, community, law, technology, practice, or network can participate in multiple systems and can change meaning across time.

## Corruption is first-class

SYSTOS does not hide corruption behind euphemism or append it as a footnote. Bribery, nepotism, patronage, fraud, embezzlement, extortion, regulatory capture, state capture, conflicts of interest, coercive extraction, information suppression, and institutional self-dealing can be represented as system mechanisms.

At the same time, allegations remain allegations until supported by evidence. Claims, counterclaims, provenance, and uncertainty remain attached to the record.

## Architecture

The intended implementation is a hybrid:

- PostgreSQL for structured records and provenance
- graph relationships for system-to-system semantics
- vector/HRR representations for associative retrieval
- full-text search
- temporal system snapshots
- evidence and source tracking
- interactive web exploration

## Relationship model

Relationships are data objects:

`SYSTEM A --[influenced]--> SYSTEM B`

A relationship may carry its own source, date, context, confidence, and evidence.

## Relationship to the Cosmic Industries knowledge atlas

SYSTOS is intended to operate alongside:

- **MATERIA** — material/natural world
- **FORTKNOWLEDGE** — human knowledge
- **MYTHOS** — stories, memory, and historical narrative
- **SYSTOS** — systems and institutions
- **CULTURA** — cultural expression and practice

The boundaries are semantic projections, not walls.

## Status

v0.1 — ontology and web interface established; seed dataset is intentionally small and designed for continuous expansion.
