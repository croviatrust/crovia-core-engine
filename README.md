# Crovia Core Engine (Open Core)

**If AI is trained on your data, there should be a receipt.**

Crovia is an **offline-verifiable evidence engine** for AI training data.
It does **not** accuse, infer, or enforce.
It produces **deterministic artifacts** that anyone can verify independently.

---

## What Crovia Produces (CRC-1)

Crovia generates a **CRC-1 Evidence Pack** — a closed set of files
that fully describe *what was declared* and *what was produced*.

Each pack contains:

- `receipts.ndjson` — declared training receipts
- `validate_report.md` — deterministic validation outcome
- `hashchain.txt` — integrity hash-chain
- `trust_bundle.json` — normalized trust summary
- `MANIFEST.json` — authoritative artifact contract

All files are **offline-verifiable**.

See: `docs/CROVIA_ARTIFACT_SPEC.md`

---

## 1) Generate Evidence (single command)

Example:

crovia-run \
  --receipts examples/minimal_royalty_receipts.ndjson \
  --period 2025-11 \
  --out out_crc1

This creates a complete CRC-1 Evidence Pack in `out_crc1/`.

- No network
- No secrets
- Fully deterministic

---

## 2) Inspect the Artifacts

Example:

ls out_crc1
cat out_crc1/MANIFEST.json

The MANIFEST defines exactly which files must exist.
Nothing implicit. Nothing hidden.

---

## 3) Verify Evidence (offline, by anyone)

Example:

crovia-verify out_crc1

Expected output:

✔ All artifacts present  
✔ trust_bundle JSON valid  
✔ Hashchain verified  

✔ CRC-1 VERIFIED

Verification requires **only the files themselves**.

---

## Design Principles

- Offline-first
- Deterministic
- No attribution claims
- No enforcement logic
- Evidence > opinions

Crovia produces **facts**, not judgments.

---

## Repositories

Open Core Engine  
https://github.com/croviatrust/crovia-core-engine

Public Evidence Lab (verifiable demos)  
https://github.com/croviatrust/crovia-evidence-lab

---

## License

Apache-2.0  
CroviaTrust


---

## Public Evidence & Verification

Crovia Open Core does **not ship conclusions**.

All publicly inspectable evidence generated with this engine lives in:

👉 https://github.com/croviatrust/crovia-evidence-lab

That repository contains:
- reproducible CRC-1 capsules
- offline-verifiable artifacts
- neutral semantic observations (DSSE)
- presence / absence observations (Spider)

If you want to **see results**, go there.  
If you want to **reproduce them**, stay here.

