# Crovia Core Engine (Open Core)
**Verifiable Evidence Packs for AI training transparency**

Crovia is an **open-core evidence pipeline** that produces **audit-ready, offline-verifiable artifacts** from NDJSON receipts/logs.

Crovia does **not** accuse anyone.
Crovia records **verifiable structure + integrity** — and makes it possible for third parties to verify the output **without** trusting a dashboard.

---

## What this repo contains

This repository is **Open Core** only:

- Schemas (contracts)
- Structural validation with Health grading (A/B/C/D)
- Cryptographic hash-chain proofs over NDJSON
- Evidence Pack manifest schema
- Offline verification tools

It intentionally does **not** include proprietary settlement logic.

---

## Core concept: Evidence Pack

An **Evidence Pack** is a deterministic container that can be verified offline:

- declared `inputs`
- produced `artifacts`
- `hashes` (SHA256 keyed by artifact path)
- a `manifest.json` (validated by the manifest schema)

See:
- `pack/manifest.schema.json`

---

## Directory map (Open Core)

- `schemas/registry.py`
  - Contract registry (e.g. `royalty_receipt.v1`, `payouts.v1`, `crovia_trust_bundle.v1`, `trust_drift.v1`)
- `validate/validate.py`
  - Streaming NDJSON validator + business rules + Health grade (A/B/C/D)
- `proofs/hashchain_writer.py`
  - Rolling SHA-256 hash-chain over NDJSON (chunked)
- `proofs/verify_hashchain.py`
  - Verifies a hash-chain against the original NDJSON
- `pack/manifest.schema.json`
  - Evidence Pack manifest schema
- `cli/pack.py`, `cli/verify.py`
  - CLI entrypoints (contract declared; orchestration implementation may be staged)

---

## Quickstart (Open Core)

### 1) Validate NDJSON
Run validation on receipts/logs:

~~bash
python3 validate/validate.py --help
python3 validate/validate.py --in data/royalty_receipts.ndjson --out report.md
~~

Expected behavior:
- produces a Markdown report with Health grade
- emits a sample of problematic lines (if any)
- exit codes encode severity (OK / partial / fail)

### 2) Build a hash-chain proof over NDJSON
~~bash
python3 proofs/hashchain_writer.py --source data/royalty_receipts.ndjson --chunk 10000
~~

Default output:
- `proofs/hashchain_royalty_receipts.ndjson.txt`

### 3) Verify the proof (offline / third-party)
~~bash
python3 proofs/verify_hashchain.py \
  --source data/royalty_receipts.ndjson \
  --chain proofs/hashchain_royalty_receipts.ndjson.txt \
  --chunk 10000
~~

If the source NDJSON changes by even 1 byte, verification fails.

---

## Open vs PRO (monetization boundary)

Open Core provides:
- structure validation + Health grading
- receipts/payout schema contracts
- immutable proofs (hash-chain)
- offline verification

Crovia PRO adds (not in this repo):
- final settlement (contract-aware payouts)
- DPI calibration
- DP noise policy enforcement
- DSSE semantic weighting
- risk-adjusted trust scoring
- policy application that **changes outcomes**, not just structure

**Open proves what exists. PRO determines what it means.**

---

## License

Apache-2.0 (enterprise-friendly).
