# Crovia Core Engine (Open Core)

**If AI is trained on your data, there should be a receipt.**

Crovia Core Engine is the **open, verifiable trust and payout layer** for AI training data.
It produces **deterministic, offline-verifiable evidence artifacts** from declared inputs.

This project:
- does NOT accuse anyone
- does NOT make legal judgments
- only produces verifiable technical evidence

---

## Quickstart (30 seconds)

The following commands run a minimal end-to-end open-core pipeline.
Everything below is intentionally shown as a **single executable flow**.

1) Validate NDJSON receipts (structure + business rules)

python3 validate/validate.py \
  --in examples/minimal_royalty_receipts.ndjson \
  --out report.md

2) Build an integrity proof (rolling hash-chain)

python3 proofs/hashchain_writer.py \
  --source examples/minimal_royalty_receipts.ndjson \
  --chunk 2

3) Verify the proof offline

If you change even 1 byte in the NDJSON file, this MUST fail.

python3 proofs/verify_hashchain.py \
  --source examples/minimal_royalty_receipts.ndjson \
  --chain proofs/hashchain_minimal_royalty_receipts.ndjson.txt \
  --chunk 2

---

## Notes

- No network access required
- Verification is deterministic and reproducible
- Integrity checks fail on any tampering

---

## What the Open Core Provides

Crovia open-core focuses strictly on verifiable outputs:

- JSON schemas for receipts and bundles (schemas/)
- Streaming validators with health-style reporting (validate/)
- Cryptographic integrity proofs (hash-chains) (proofs/)
- Deterministic Evidence Pack format (pack/)
- Thin CLI entrypoints (cli/)

---

## Evidence Pack

An Evidence Pack is a reproducible, hash-verifiable bundle produced from declared inputs.

It may contain:
- validation reports
- signed receipts (NDJSON)
- hash-chain proofs
- derived payout views
- CEP capsules

See pack/README.md for the formal definition.

---

## Open vs PRO

Open Core is for:
- structure validation
- integrity proofs
- deterministic packaging
- offline verification

PRO (private repository) is for:
- settlement engines
- contract registries
- DPI and policy calibration
- enterprise-grade audits

Open Core verifies.
PRO settles.

---

## Evidence & Reproducible Proofs

The **Crovia Evidence Lab** contains *public, reproducible outputs* generated using
the Open Core primitives defined in this repository.

This repository provides **the tools and verification primitives**.
The Evidence Lab provides **the publicly verifiable proofs** produced with them.

Public, reproducible evidence produced by Crovia is available here:

👉 https://github.com/croviatrust/crovia-evidence-lab

This repository contains:
- DSSE open proofs on public datasets (LAION, C4, DSSE-1M)
- Presence / absence observations (Spider)
- Drift snapshots and hash-anchored artifacts

The Open Core focuses strictly on **verification primitives**.
