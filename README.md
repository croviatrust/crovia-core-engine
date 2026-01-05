# Crovia Core Engine (Open Core)

**If AI is trained on your data, there should be a receipt.**

Crovia is an **offline-verifiable evidence engine** for declared AI training data.

It does **not** accuse.  
It does **not** infer intent.  
It does **not** enforce compliance.

Crovia produces **deterministic artifacts** that anyone can verify independently.

---

## Read this first (30 seconds)

If you read only one thing, read this:

**Crovia turns a declaration into a closed, verifiable evidence capsule.**  
Nothing more. Nothing less.

No trust required.  
No network required.  
No hidden logic.

---

## What Crovia produces (CRC-1)

Crovia generates a **CRC-1 Evidence Pack** — a closed set of files that fully describe:

- what was declared
- what was produced
- how integrity can be verified

Each CRC-1 pack contains:

- `receipts.ndjson` — declared training receipts  
- `validate_report.md` — deterministic validation result  
- `hashchain.txt` — integrity hash-chain  
- `trust_bundle.json` — normalized trust summary  
- `MANIFEST.json` — authoritative artifact contract  

All files are **offline-verifiable**.

Specification:  
`docs/CROVIA_ARTIFACT_SPEC.md`

---

## Try it (single command)

Generate a complete CRC-1 Evidence Pack, example:

crovia-run \
  --receipts examples/minimal_royalty_receipts.ndjson \
  --period 2025-11 \
  --out out_crc1

This creates a fully self-contained evidence capsule in `out_crc1/`.

- No network  
- No secrets  
- Fully deterministic  

---

## Inspect the artifacts

Example:

ls out_crc1  
cat out_crc1/MANIFEST.json  

`MANIFEST.json` defines exactly which files must exist.

Nothing implicit.  
Nothing hidden.

---

## Verify evidence (offline, by anyone)

Verification requires **only the files themselves**.

Example:

crovia-verify out_crc1

Expected result:

✔ All artifacts present  
✔ trust_bundle JSON valid  
✔ Hashchain verified  

✔ CRC-1 VERIFIED

If verification fails, the evidence is invalid.

No trust assumptions.  
No authority required.

---

## Design principles

- Offline-first  
- Deterministic  
- No attribution claims  
- No enforcement logic  
- Evidence > opinions  

Crovia produces **facts**, not judgments.

---

## Where to see real evidence

Crovia Open Core does not ship conclusions.

All public, inspectable evidence generated with this engine lives here:

https://github.com/croviatrust/crovia-evidence-lab

That repository contains:
- reproducible CRC-1 capsules  
- offline-verifiable artifacts  
- neutral semantic observations (DSSE)  
- presence / absence observations (Spider)  

If you want to see results, go there.  
If you want to reproduce them, stay here.

---

## License

Apache-2.0  
CroviaTrust

