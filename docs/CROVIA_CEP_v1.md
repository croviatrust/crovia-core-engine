# CROVIA Evidence Protocol — `CEP.v1`

The **CROVIA Evidence Protocol (CEP.v1)** defines a compact, verifiable
summary of AI attribution and payout evidence, suitable for embedding
directly in model cards (e.g. on Hugging Face Hub) or technical reports.

A CEP block does **not** contain the full logs; it only carries:

- content-addressable hashes of the underlying artifacts
- minimal trust / DP / CI metrics
- the status of the hash-chain
- engine + version used to generate the evidence

The underlying artifacts are:

- CROVIA **royalty receipts** (`royalty_receipt.v1` NDJSON)  
- CROVIA **payouts** (`payouts.v1` NDJSON / CSV)  
- a sign-ready **Trust Bundle JSON** (`trust_bundle.v1`)  
- a rolling **hash-chain** over the receipts or bundle logs  

CEP.v1 is designed to be:

- **small** (≈ 10–20 lines of YAML/JSON)
- **verifiable** (all references are SHA-256 hashes)
- **engine-agnostic** (anyone can recompute and check it)
- **AI Act–friendly** (Annex IV style documentation)

---

## 1. Top-level shape

A CEP.v1 block is intended to live inside a model card or report under
a dedicated key, typically:

    crovia_evidence:
      protocol: "CEP.v1"
      ...

The full structure is:

    crovia_evidence:
      protocol: "CEP.v1"

      trust_bundle:
        schema: "trust_bundle.v1"
        sha256: "<hex SHA-256 of the bundle file>"
        period: "YYYY-MM"

      receipts:
        count: <integer>               # number of royalty_receipt.v1 records
        sha256: "<hex SHA-256 of NDJSON>"
        schema: "royalty_receipt.v1"

      payouts:
        sha256: "<hex SHA-256 of payouts NDJSON or CSV>"
        schema: "payouts.v1"
        period: "YYYY-MM"

      hash_chain:
        root: "<hex digest of last hash-chain block>"
        verified: true                 # true if verify_hashchain.py passed
        source: "<filename of the hashchain proof>"

      trust_metrics:
        avg_top1_share: <float>        # average top-1 share across receipts
        dp_epsilon:
          min: <float|null>            # min epsilon_dp observed (if any)
          max: <float|null>            # max epsilon_dp observed (if any)
        ci_present: <bool>             # true if any CI95 fields present

      generated_by:
        engine: "Crovia Core Engine"
        version: "<engine version or git short SHA>"
        timestamp: "<ISO8601 UTC generation time>"

---

## 2. Field definitions

### 2.1 `protocol`

    protocol: "CEP.v1"

**Required.**

Identifies the CEP profile version.  
Future profiles (e.g. `CEP.v2`) MUST use a different string.

---

### 2.2 `trust_bundle`

    trust_bundle:
      schema: "trust_bundle.v1"
      sha256: "<hex>"
      period: "2025-11"

**Required.**

- `schema`: MUST be `"trust_bundle.v1"` for this version.  
- `sha256`: SHA-256 over the raw bytes of the trust bundle JSON.  
- `period`: the accounting period of the bundle (`YYYY-MM`).  

The trust bundle itself typically consolidates:

- receipts  
- payouts  
- trust scores  
- validation & compliance reports  

---

### 2.3 `receipts`

    receipts:
      count: 200
      sha256: "<hex>"
      schema: "royalty_receipt.v1"

**Required.**

- `count`: number of records with `schema == "royalty_receipt.v1"` in
  the NDJSON file.
- `sha256`: SHA-256 over the raw bytes of the NDJSON file.
- `schema`: MUST be `"royalty_receipt.v1"` for CEP.v1.

The NDJSON file is expected to be validated by `crovia_validate.py`
prior to CEP generation.

---

### 2.4 `payouts`

    payouts:
      sha256: "<hex>"
      schema: "payouts.v1"
      period: "2025-11"

**Required.**

- `sha256`: SHA-256 over the payouts file (NDJSON or CSV).  
- `schema`: MUST be `"payouts.v1"` for CEP.v1.  
- `period`: MUST match the period encoded in each payouts record
  (`YYYY-MM`).  

---

### 2.5 `hash_chain`

    hash_chain:
      root: "<hex>"
      verified: true
      source: "proofs/hashchain_royalty_from_faiss.ndjson.txt"

**Required.**

- `root`: the hash of the last block computed by
  `hashchain_writer.py` over the receipts file.
- `verified`: boolean, `true` only if `verify_hashchain.py` ran
  successfully on the given source file.
- `source`: filename of the hashchain proof (for human navigation).

---

### 2.6 `trust_metrics`

    trust_metrics:
      avg_top1_share: 0.5623
      dp_epsilon:
        min: 0.5
        max: 1.0
      ci_present: true

**Required**, all fields.

Semantics:

- `avg_top1_share`  
  Average of the highest share value in `top_k` for each
  `royalty_receipt.v1` record, after QA filters.  
  (Numerically consistent with the CIM / alpha calibration approach.)

- `dp_epsilon.min` / `dp_epsilon.max`  
  Minimum and maximum `epsilon_dp` observed across receipts  
  (or `null` if no `epsilon_dp` is present).

- `ci_present`  
  `true` if at least one attribution row carries CI fields
  (`share_ci95_low` or `share_ci95_high`).

These metrics give a compact, human-readable summary of the
attribution engine’s behaviour and robustness.

---

### 2.7 `generated_by`

    generated_by:
      engine: "Crovia Core Engine"
      version: "2025-11-demo-1"
      timestamp: "2025-12-01T12:34:56Z"

**Required.**

- `engine`: free text, SHOULD be `"Crovia Core Engine"` for this project.  
- `version`: git short SHA, tag, or semantic version.  
- `timestamp`: ISO8601 UTC (e.g. `2025-12-01T12:34:56Z`).  

---

## 3. Example CEP.v1 block (Hugging Face model card)

    crovia_evidence:
      protocol: "CEP.v1"

      trust_bundle:
        schema: "trust_bundle.v1"
        sha256: "9d6f0c5f5e1b9c3a7f4b21fd0d3a86a1e8dba4b6a1e317cf4f22b29a6e0d123"
        period: "2025-11"

      receipts:
        count: 200
        sha256: "c5f9b2f8a0d0e4b1c2985a719dbb6d8c1f8a2c58f8a2e1d9b7a1e0f9c3d4e5f"
        schema: "royalty_receipt.v1"

      payouts:
        sha256: "1a2b3c4d5e6f708192a3b4c5d6e7f8091a2b3c4d5e6f708192a3b4c5d6e7f80"
        schema: "payouts.v1"
        period: "2025-11"

      hash_chain:
        root: "ab12cd34ef56ab78cd90ef12ab34cd56ef78ab90cd12ef34ab56cd78ef90ab"
        verified: true
        source: "proofs/hashchain_royalty_from_faiss.ndjson.txt"

      trust_metrics:
        avg_top1_share: 0.5623
        dp_epsilon:
          min: 0.5
          max: 1.0
        ci_present: true

      generated_by:
        engine: "Crovia Core Engine"
        version: "2025-11-demo-1"
        timestamp: "2025-12-01T12:34:56Z"

This block can be pasted as-is into a Hugging Face model card under
the YAML front-matter or inside a dedicated **Evidence** section.
