# MATERIA corpus architecture

MATERIA is an open ethnobotanical research atlas built as a **provenance-preserving biological knowledge graph**. It is no longer limited to the seed corpus: the live explorer connects global taxonomy to curated evidence, natural products, morphology, development, preparation, safety and ethnographic context.

## Global taxonomy

The atlas is connected to the **Catalogue of Life / ChecklistBank** latest public release endpoint (`3LR`). The September 2026 COL26.9 release contains 2,709,610 accepted/provisionally accepted taxa, 2,722,834 synonyms and 5,432,444 total usages. MATERIA's live explorer filters this corpus to **Plantae** and **Fungi** and supports search, pagination and full taxon inspection.

Source: Catalogue of Life / ChecklistBank, COL26.9 (dataset 316321).

## Natural products

MATERIA links the taxonomic corpus to:

- Natural Products Atlas — downloadable TSV/JSON/SDF and REST API.
- LOTUS — natural-product structures, organism relationships and downloadable datasets.
- COCONUT — planned large-scale natural-product cross-reference.
- PubChem — chemical identity/cross-reference layer.

A compound relationship is never inferred solely from taxonomic association. The source must support the organism/material → compound edge.

## Morphology, architecture and development

MATERIA now treats **plant architecture as first-class evidence**, alongside taxonomy and chemistry.

```text
taxon
  ├── morphology
  │     ├── phyllotaxis
  │     │     ├── organ arrangement
  │     │     ├── divergence angle
  │     │     ├── plastochron
  │     │     ├── spiral / whorl pattern
  │     │     ├── chirality
  │     │     └── pattern transition
  │     ├── leaf morphology
  │     ├── stem / internode geometry
  │     ├── branching architecture
  │     ├── inflorescence architecture
  │     ├── root architecture
  │     └── diagnostic characters
  │
  ├── development
  │     ├── developmental stage
  │     ├── phenology
  │     ├── meristem state
  │     ├── harvest timing
  │     └── temporal phenotype
  │
  └── environment
        ├── water status
        ├── nutrients
        ├── temperature
        ├── light
        ├── stress
        └── cultivation treatment
```

### Why this is part of pharmacognosy

Morphology is not decorative metadata. It can participate in:

- **taxonomic authentication**
- species/subspecies discrimination
- detection of substitution/adulteration
- specimen provenance
- developmental-state normalization
- harvest optimization
- interpretation of tissue-specific chemistry
- linking genotype/environment to phenotype and secondary metabolism.

MATERIA therefore preserves the chain:

```text
taxon
  ↓
genotype / provenance
  ↓
development + environment
  ↓
morphology / architecture
  ↓
tissue / harvest state
  ↓
preparation / extraction
  ↓
chemical profile
  ↓
bioactivity / toxicity
  ↓
clinical or ethnographic observation
```

The graph must not imply that morphology causes a chemical effect unless the cited evidence demonstrates that relationship.

## Evidence model

Evidence is explicitly stratified:

| Level | Meaning | Treatment |
|---|---|---|
| **L0** | Primary scientific evidence: analytical chemistry, experimental biology, genomics, metabolomics, toxicology, controlled assays | Direct scientific evidence |
| **L1** | Peer-reviewed reviews / systematic reviews / syntheses | Secondary evidence; trace to primary studies |
| **L2** | Ethnobotany / ethnomycology / ethnobiology / historical-use datasets | Evidence of human cultural use, not efficacy |
| **L3** | Human clinical observations, case reports, pharmacovigilance, poisoning records | Human observation; preserve dose/exposure/outcome context |
| **L4** | Community phenomenology and first-hand community observations | Preserve as situated knowledge; do not promote to efficacy |
| **L5** | Anecdotal / unsourced reports | Quarantine; never promote automatically |

Computational predictions, docking, ML associations and inferred mechanisms receive a **separate prediction provenance** and are never silently promoted to L0 experimental evidence.

## Core evidence graph

```text
taxon
  ├── synonym
  ├── vernacular_name
  ├── specimen / voucher
  ├── morphology
  │     ├── phyllotaxis
  │     ├── architecture
  │     └── diagnostic_character
  ├── development / phenology
  ├── environment / cultivation
  ├── tissue
  ├── preparation
  │     ├── extraction
  │     ├── formulation
  │     └── processing
  ├── traditional_use
  ├── natural_product
  │     ├── structure
  │     ├── occurrence
  │     ├── biosource
  │     ├── target
  │     ├── mechanism
  │     └── study
  ├── interaction
  ├── adverse_event
  ├── toxicity
  └── clinical_observation
```

## Provenance and authenticity

Every substantive relationship should retain:

- source
- evidence level
- observation/assay type
- organism/material identity
- geographic provenance where available
- tissue/material
- preparation or processing
- analytical method
- developmental/harvest state
- environmental conditions where relevant
- uncertainty
- whether the edge is observed, inferred or computationally predicted.

MATERIA explicitly supports:

```text
labeled_taxon ≠ authenticated_taxon
claimed_compound ≠ measured_compound
predicted_interaction ≠ demonstrated_interaction
traditional_use ≠ clinical_efficacy
```

## Reproducibility

For publication-grade analyses, pin a dated Catalogue of Life release instead of relying only on `3LR`, because monthly releases can change and identifiers can churn. The September 2026 release is recorded in `manifest.json`.

## Current expansion

The morphology layer is designed to absorb high-value plant-phenotyping resources such as:

- Sugar4D-style 4D LiDAR plant architecture datasets
- phyllotaxis/developmental genetics datasets
- TRY plant-trait data
- genome/phenotype resources
- taxonomic authentication studies

These are external evidence sources, not claims that every trait or dataset has already been ingested locally.
