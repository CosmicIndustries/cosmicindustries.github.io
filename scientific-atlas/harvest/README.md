# Scientific Atlas Harvest

The harvest layer expands the Fort Knowledge Scientific Data Atlas from a hand-curated seed into a provenance-preserving discovery index.

## Authoritative sources

The first cohort uses:

- DataCite dataset DOIs
- NASA Earthdata Common Metadata Repository collections
- U.S. Geological Survey ScienceBase data releases
- NOAA National Centers for Environmental Information dataset search

These services expose programmatic catalog metadata. The harvester records discovery metadata and identifiers; it does not copy the source datasets.

## Pipeline

authoritative catalog -> API metadata -> source-specific normalization -> provenance -> deduplication -> JSONL -> Atlas

The original seed remains the curated regression corpus. Harvested records use DISCOVERED status until separately reviewed.

## Preservation rules

- Catalog presence is evidence of discoverability, not scientific validity.
- Preserve source identifiers and source URLs.
- A changed URL is not evidence of suppression.
- API failures are recorded rather than replaced with guessed records.
- Source-specific metadata stays attached to its source provenance.
- Migrations and reinterpretations are additive records/events, never silent overwrites.

## Scale

The first harvest limits intentionally produce thousands rather than millions of records. Scale can be raised after the package format, fixity, rendering, and restore tests are in place.
