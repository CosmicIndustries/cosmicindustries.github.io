# MATERIA corpus architecture

MATERIA is no longer limited to the 59-record seed corpus.

## Global taxonomy

The atlas is connected to the **Catalogue of Life / ChecklistBank** latest public release endpoint (`3LR`). The September 2026 COL26.9 release contains 2,709,610 accepted/provisionally accepted taxa, 2,722,834 synonyms and 5,432,444 total usages. MATERIA's live explorer filters this corpus to **Plantae** and **Fungi** and supports search, pagination and full taxon inspection.

Source: Catalogue of Life / ChecklistBank, COL26.9 (dataset 316321).

## Natural products

MATERIA links the taxonomic corpus to:

- Natural Products Atlas — downloadable TSV/JSON/SDF and REST API.
- LOTUS — natural-product structures, organism relationships and downloadable datasets.
- COCONUT — planned large-scale natural-product cross-reference.
- PubChem — chemical identity/cross-reference layer.

These are deliberately not flattened into the Pages HTML. The browser queries the taxonomy API and links to the chemistry databases, while the curated evidence graph remains versioned in this repository.

## Evidence graph

```text
taxon
  ├── synonym
  ├── vernacular_name
  ├── tradition
  ├── preparation
  └── natural_product
          ├── structure
          ├── biosource
          ├── target
          ├── mechanism
          └── study
```

Every substantive relationship should retain provenance and an evidence level.

## Reproducibility

For publication-grade analyses, pin a dated Catalogue of Life release instead of relying only on `3LR`, because monthly releases can change and identifiers can churn. The September 2026 release is recorded in `manifest.json`.
