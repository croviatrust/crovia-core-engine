# Crovia Core Engine (Open Core)

**If AI is trained on your data, there should be a receipt.**

Crovia is an **offline-verifiable evidence engine** for declared AI training data.

It does **not** accuse.  
It does **not** infer intent.  
It does **not** enforce compliance.

Crovia produces **deterministic artifacts** that anyone can verify independently.

## Engine, observatory, and evidence status

This repository contains the open-core engine. The public observatory is a separate evidence surface: it reports scoped observations generated from monitored public sources, not conclusions about intent or legal compliance.

- [Public evidence status](https://croviatrust.com/status/) — freshness and current verification boundaries
- [Machine-readable claims](https://croviatrust.com/data/public_claims.json) — claims paired with evidence and limitations
- [Methodology](https://croviatrust.com/methodology/) — collection and interpretation rules
- [Crovia Seal verifier](https://croviatrust.com/registry/seal/verify/) — client-side verification of Seal receipts

Treat live counters as stale unless both the document timestamp and the underlying evidence timestamp are inside the declared TTL. Signature validity, Merkle inclusion, OpenTimestamps submission, and Bitcoin confirmation are separate states.

Crovia Seal is an experimental receipt format developed alongside the individual Internet-Draft `draft-crovia-seal-01`. An Internet-Draft is not an IETF standard or endorsement.

---

## Install

```bash
pip install crovia
```

Requires Python 3.10+. No external dependencies for the core pipeline.

---

## Read this first (30 seconds)

If you read only one thing, read this:

**Crovia turns a declaration into a closed, verifiable evidence capsule.**  
Nothing more. Nothing less.

No network required.  
No hidden logic.

Verification still requires choosing which issuer key and evidence source you trust.

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

---

## Try it (single command)

### Generate CRC-1 Evidence Packs

```bash
crovia run --receipts examples/minimal_royalty_receipts.ndjson --period 2025-11 --budget 1000000 --out out_crc1
```

This creates a self-contained evidence capsule in `out_crc1/`.

### Disclosure Scanner

```bash
crovia oracle scan meta-llama/Llama-3-8B
crovia oracle scan mistralai/Mistral-7B-v0.1
```

A scanner result is an observation over configured public surfaces, not proof of intent, illegality, or regulatory non-compliance.

### Evidence Wedge

```bash
crovia wedge scan
crovia wedge scan --path ./my-project
crovia wedge status
crovia wedge explain
```

### Other commands

```bash
crovia check   <receipts.ndjson>
crovia refine  <receipts.ndjson>
crovia pay     <receipts.ndjson> --period YYYY-MM --budget N
crovia bundle  --receipts X --payouts Y
crovia sign    <file>
crovia trace   <file>
crovia explain <file>
crovia license status
crovia bridge  preview <model>
crovia mode    show
crovia legend
```

> `crovia scan` requires the FAISS corpus index, which is not shipped in open core.

---

## Verify evidence offline

```bash
crovia-verify out_crc1
```

Expected result:

```text
[OK] All artifacts present
[OK] trust_bundle JSON valid
[OK] Hashchain verified

[OK] CRC-1 VERIFIED
```

A successful result establishes integrity under the verifier's stated profile. It does not independently establish the truth of declarations or the trustworthiness of their issuer.

---

## Design principles

- Offline-first
- Deterministic
- No attribution claims
- No enforcement logic
- Evidence over opinion

Crovia produces **verifiable artifacts**, not judgments.

---

## Reproducible public evidence

Public, inspectable examples generated with this engine live in:

https://github.com/croviatrust/crovia-evidence-lab

Use that repository to inspect artifacts and reproduction instructions. Use this repository to inspect or run the engine.

---

## License

Apache-2.0  
CroviaTrust
