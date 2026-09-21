# Scientific Data Atlas — Invariant Anchor Protocol

Version: 0.1
Established: 2026-09-21
Purpose: provide a language- and culture-independent bootstrap layer for future readers.

## Principle

A future civilization must not need to understand modern English before it can understand the archive.

The archive therefore carries a set of **invariant or independently recoverable anchors** from which notation, measurement, units, and semantic mappings can be reconstructed.

No single constant is sufficient.

The bootstrap set is deliberately redundant.

## 1. Anchor classes

### A. Mathematical invariants

Use structures that do not depend on a particular physical unit system:

- natural numbers
- integers
- prime numbers
- ratios
- equality
- order
- geometry
- pi (π)
- e
- fundamental mathematical relationships
- simple arithmetic identities
- simple geometric constructions

These are preferable as the first layer because they do not depend on Earth's institutions, language, or physical unit conventions.

### B. Physical invariants and relations

Use independently measurable phenomena:

- speed of light in vacuum, c
- atomic transition frequencies
- Planck relation
- elementary charge
- Boltzmann relation
- Avogadro scale
- characteristic atomic spectra
- dimensionless physical constants where appropriate

Important:

A numerical constant without its unit definition is NOT a universal semantic anchor.

For example, c = 299792458 m/s is exact within the modern SI because the SI defines the metre and second through defining constants. BIPM explicitly defines the metre by fixing c at that value in SI units.

Therefore the archive should preserve both:

1. the physical relationship
2. the unit system used to express it

rather than assuming that the decimal representation itself is universal.

### C. Astronomical anchors

Use independently observable celestial phenomena as additional cross-checks:

- spectral lines
- pulsar periods
- orbital relationships
- planetary periods
- stellar spectra
- hydrogen emission/absorption lines

Astronomical anchors are useful because they provide observations outside the archive's own cultural system.

They are secondary anchors, not assumed eternal numerical constants.

### D. Temporal anchors

Represent time using multiple independent forms:

- elapsed duration
- atomic-frequency definitions where available
- astronomical cycles
- relative sequence/order
- calendar date as a historical representation

Never let a calendar become the canonical definition of an event.

"14 June 1907" is an annotation.

"The observation occurred X seconds after event Y" is a relationship.

The original calendar representation remains preserved.

### E. Spatial anchors

Preserve:

- coordinate systems
- geometric relationships
- relative distances
- surveyed coordinates
- astronomical reference frames
- original place names

Never let a place name become the canonical identity of a location.

### F. Measurement anchors

Every measurement should preserve:

- quantity
- numerical value
- unit
- uncertainty
- measurement procedure
- instrument
- calibration
- reference standard
- transformation history

This lets future readers reinterpret the value under a different unit system without losing the original measurement.

## 2. Anchor ladder

The archive should bootstrap in this order:

MATHEMATICS
    ↓
LOGIC / RELATIONSHIPS
    ↓
GEOMETRY
    ↓
PHYSICAL PHENOMENA
    ↓
MEASUREMENT
    ↓
UNITS
    ↓
SCIENTIFIC CONCEPTS
    ↓
HISTORICAL LANGUAGE
    ↓
MODERN / FUTURE LANGUAGE

The lower layers should not depend upon the higher layers.

## 3. Self-description

The first preservation package should contain a minimal machine-readable and human-readable bootstrap containing:

- integers
- prime sequence
- simple geometric diagrams
- π approximation and construction
- simple mathematical equations
- dimensional relationships
- atomic spectra examples
- defining SI constants and their definitions
- a small collection of physical reference phenomena
- multilingual labels where available
- plain-text explanations
- machine-readable representations of all of the above

The package should contain enough redundancy that loss of one representation does not destroy interpretation.

## 4. Avoid false universality

The following are NOT automatically universal semantic anchors:

- English words
- modern SI unit names
- UTC dates
- country names
- current political boundaries
- modern place names
- current scientific classifications
- current software syntax
- current file formats
- decimal notation alone
- a proprietary identifier
- a URL

They can all be preserved, but none should be a single point of semantic failure.

## 5. Dimensional semantics

Prefer dimensional relations over bare numbers.

Example:

BAD:
    299792458

BETTER:
    c = 299792458 m/s

BETTER STILL:
    invariant physical relation:
    distance / elapsed time = c
    with explicit historical unit representation.

This distinction matters because the numerical value of a dimensional quantity changes when the unit system changes.

Dimensionless quantities such as ratios are often stronger cross-cultural anchors.

## 6. Multiple independent reconstructions

A future reader should be able to recover the same interpretation through multiple paths.

Example:

π
 ├── geometric construction
 ├── numerical series
 ├── circle circumference/diameter measurements
 └── independent mathematical notation

c
 ├── physical definition
 ├── dimensional relation
 ├── historical measurements
 └── modern SI expression

A bootstrap interpretation becomes stronger when independent paths converge.

## 7. Anchor versioning

The archive itself must never imply that the anchor representation is beyond revision.

Record:

- anchor definition
- historical formulation
- current formulation
- version
- source
- derivation
- uncertainty where applicable
- whether value is exact by definition or experimentally estimated

This is especially important for physical constants.

## 8. Exact vs measured

Every numeric anchor must carry one of:

EXACT_BY_DEFINITION
EXACT_MATHEMATICAL
EXPERIMENTAL_ESTIMATE
DERIVED
HISTORICAL_MEASUREMENT
APPROXIMATION

Never present an exact-by-definition value as though it were a measured natural constant.

## 9. Bootstrap language

The archive should maintain a dedicated **Bootstrap Lexicon** mapping:

ANCHOR
→ SYMBOL
→ FORMAL MEANING
→ MATHEMATICAL REPRESENTATION
→ PHYSICAL REALIZATION
→ HISTORICAL TERM
→ MODERN TERM
→ TRANSLATIONS

This makes language a rendering layer instead of a prerequisite for understanding.

## 10. Future-language rendering

Once a future reader has reconstructed the concept graph, the interface can render:

CONCEPT_0001
    → future language term
    → future notation
    → future unit system

without translating the historical source itself.

The original source remains unchanged.

## 11. Long-term test

The anchor system passes its design test if a future reader can:

1. identify mathematical relationships
2. reconstruct basic numerical notation
3. distinguish dimensionless from dimensional quantities
4. recognize physical measurement relationships
5. reconstruct the unit definitions used by the archive
6. identify scientific concepts
7. map those concepts to historical terminology
8. render the result in a language unknown to the original archivists

## 12. Core principle

**Do not preserve only what humans currently say. Preserve enough of mathematics, measurement, observation, and relationships that a future intelligence can independently reconstruct what we meant.**
