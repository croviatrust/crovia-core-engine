# Crovia — DSSE 1M Streaming Proof (2025-12-16)

This is a reproducible evidence run showing bounded-memory DSSE snapshotting and signed trust drift.

## What we did
- Streamed 1,000,000 NDJSON records (~242MB) and generated a DSSE snapshot.
- Re-ran the same 1,000,000 records with added provenance metadata.
- Generated a signed `trust_drift.v1` record showing trust increase driven only by evidence quality.

## Measured (BASE run)
- Records: 1,000,000
- Elapsed: 10.67s
- Max RSS: ~21MB
- Snapshot size: 178 bytes
- Engine: dsse-lite.v1

## Observed effect (BASE → PLUS)
- `legal_ambiguity_level`: 1.0 → 0.0
- Signed trust drift: +0.2

## Artifacts
- data/snapshots/synthetic/snapshot_synth_1M_base.json
- data/snapshots/synthetic/snapshot_synth_1M_plus_evidence.json
- data/drift/synthetic/synth_1M_drift.ndjson
- data/evidence/DSSE_1M_HASHES.txt (sha256 anchors)

## Verification
Hashes are authoritative. Re-run is possible without disclosing private keys or gated datasets.
