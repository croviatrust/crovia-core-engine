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
- [Offline verifier](https://croviatrust.com/registry/verify/) — independently inspect artifacts

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

---

## Try it (single command)

### Generate CRC-1 Evidence Packs

```bash
# Full pipeline — receipts in, evidence pack out
crovia run --receipts examples/minimal_royalty_receipts.ndjson --period 2025-11 --budget 1000000 --out out_crc1
```

This creates a fully self-contained evidence capsule in `out_crc1/`.

### Disclosure Scanner — check a model's disclosure gaps

```bash
# Scan a HuggingFace model for missing training data declarations
crovia oracle scan meta-llama/Llama-3-8B
crovia oracle scan mistralai/Mistral-7B-v0.1
```

### Evidence Wedge — check a directory for evidence artifacts

```bash
crovia wedge scan              # scan current directory
crovia wedge scan --path ./my-project
crovia wedge status            # one-line status
crovia wedge explain           # what artifacts Crovia looks for
```

### Other commands

```bash
crovia check   <receipts.ndjson>   # validate receipts (real)
crovia refine  <receipts.ndjson>   # fix share_sum / rank issues
crovia pay     <receipts.ndjson> --period YYYY-MM --budget N  # compute payouts
crovia bundle  --receipts X --payouts Y  # assemble trust bundle
crovia sign    <file>              # HMAC-sign any artifact
crovia trace   <file>              # generate / verify hashchain
crovia explain <file>              # inspect any Crovia JSON/NDJSON
crovia license status              # check tier (OPEN / PRO)
crovia bridge  preview <model>     # PRO capability preview
crovia mode    show                # show CLI config
crovia legend                      # full command reference
```

> `crovia scan` (attribution spider) requires the FAISS corpus index — not yet in open core.  
> Run `crovia scan <file>` for details.

- No network  
- No secrets  
- Fully deterministic  

---

## Inspect the artifacts

```bash
# Linux / macOS
ls out_crc1
cat out_crc1/MANIFEST.json

# Windows
dir out_crc1
type out_crc1\MANIFEST.json
```

`MANIFEST.json` defines exactly which files must exist.

Nothing implicit.  
Nothing hidden.

---

## Verify evidence (offline, by anyone)

Verification requires **only the files themselves**.

Example:

```bash
crovia-verify out_crc1
```

Expected result:

```
[OK] All artifacts present
[OK] trust_bundle JSON valid
[OK] Hashchain verified

[OK] CRC-1 VERIFIED
```

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

Crovia produces **verifiable artifacts**, not judgments.

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

## Source

https://github.com/croviatrust/crovia-core-engine

---

## License

Apache-2.0  
CroviaTrust

