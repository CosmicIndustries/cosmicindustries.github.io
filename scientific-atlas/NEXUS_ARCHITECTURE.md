# FORT KNOWLEDGE — NEXUS ARCHITECTURE

Version: 0.2
Snapshot: 2026-09-21

## Preservation baseline

Design targets:
- ISO 14721:2025 (OAIS)
- ISO 16363:2025 (trustworthy digital repository audit)
- PREMIS 3.0
- METS 2
- BagIt 1.0 / RFC 8493
- WARC / ISO 28500:2017
- W3C PROV
- RO-Crate 1.3

These are implementation targets. The project is not certified merely by referencing them.

## Canonical hierarchy

Evidence payload -> persistent identity -> fixity -> provenance -> preservation events -> structure -> semantics -> correlations -> derivatives -> indexes -> interface.

No upper layer may silently replace a lower layer.

## Archive package

A preservation package should be representable as BagIt with bagit.txt, data/, SHA-512 manifests, tag manifest, bag-info.txt, object identifier, rights, provenance, and preservation events.

Complex objects may use METS and PREMIS. Research objects may use RO-Crate. Web captures may use WARC.

## Trust separation

Track independently:
- bit integrity
- provenance integrity
- custody continuity
- scientific validity
- semantic interpretation

## Federation

Fort Knowledge is a nexus, not the owner of the world's archives. Prefer authoritative source -> persistent identifier -> preservation copy/mirror -> relationship graph.

## Replication target

For critical collections:
- >=4 independent custodians
- >=3 geographic regions
- >=2 materially different storage technologies
- >=1 offline or offline-capable copy

These are engineering targets, not certification claims.

## Discovery

FIELD, STREAM, WANDER, TABLE, TIMELINE, CORRELATIONS, RECOVERY.

The interface is a discovery instrument, not the archive.

## Semantic durability

Preserve original language, diplomatic transcription, normalization, historical sense, concept identity, modern rendering, alternative interpretations, and machine-derived interpretation metadata.

Stories and mnemonics remain derivatives linked to evidence.

## YOU ARE HERE

Preserve time scale, epoch, celestial frame, solar-system origin, state vector, terrestrial frame, Earth orientation, geodetic state, vertical datum, uncertainty, and provenance.

A coordinate string alone is never canonical.

## ARRIVAL

Every forecast includes arrival condition, epoch, frame, time scale, model, uncertainty, observations used, and revision history. Physical arrival, detectability, recognition, and intent are separate concepts.

## Access

Ordinary scientific and historical knowledge should be freely discoverable by default. Restrictions are tied to explicit rights, privacy, safety, and integrity requirements.

## References

- ISO 14721:2025: https://www.iso.org/standard/87471.html
- ISO 16363:2025: https://www.iso.org/standard/87472.html
- PREMIS: https://www.loc.gov/standards/premis/v3/
- METS 2: https://www.loc.gov/standards/mets/mets2.html
- BagIt: https://www.rfc-editor.org/rfc/rfc8493.html
- WARC: https://www.iso.org/standard/68004.html
- W3C PROV: https://www.w3.org/TR/prov-overview/
- RO-Crate 1.3: https://www.researchobject.org/ro-crate/specification/1.3/
