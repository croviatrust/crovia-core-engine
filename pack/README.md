# Crovia Evidence Pack

A **Crovia Evidence Pack** is a deterministic, verifiable bundle of artifacts produced from declared inputs.

It is designed to be:
- reproducible
- auditable
- hash-verifiable
- independent from proprietary engines

## What this pack may contain
- validation reports
- signed receipts (NDJSON)
- hash-chain proofs
- payout views (derived)
- CEP capsules
- declared system state (derived)

## What this pack does NOT do
- no legal judgement
- no intent attribution
- no compliance guarantee
- no disclosure of proprietary engine internals

## Verification
Every artifact included in the pack is:
- referenced in the manifest
- hash-anchored (SHA256)
- independently verifiable
