# CROVIA AUTOLOG / TRAINING TAP — Concept (Open-safe)

**Crovia inside the training loop.**

Autolog is a tiny instrumentation layer that lives *next to* your training code
(PyTorch / HF Trainer / JAX / Lightning) and emits **raw evidence events**
while batches flow through training.

Crovia stops being “post-processing”.
Crovia becomes **training-time governance instrumentation**.

> Think: TensorBoard, but for provenance + evidence + payout receipts.

---

## What Autolog Emits (open-core concept)

Autolog does **not** need your raw dataset.
It observes training *execution* and emits **evidence events**:

- `period` (YYYY-MM)
- `run_id` (unique training run id)
- `batch_id` (monotonic / deterministic)
- `provider_id` (who the data belongs to)
- `shard_id` (dataset partition / source handle)
- `licensing_hints` (if available from metadata)
- `usage` (token counts, sample counts, weights)
- `fast_hashes` (fast batch fingerprints, not raw samples)
- `risk_signals` (policy flags / missing provenance / unknown license)
- `semantic_cluster_hint` (optional, coarse, non-reversible)

These events can be converted into **receipt NDJSON** and then:
- validated (`crovia check`)
- refined (`crovia refine`)
- paid (`crovia pay`)
- bundled (`crovia bundle`)
- signed (`crovia sign`)
- hash-chained (`crovia trace`)

---

## Why This Is Different

Most systems do:
1) train first
2) “declare” later

Autolog makes evidence **native** to training:

- no retroactive narratives
- no “trust me, we complied”
- no black-box SaaS required

Crovia evidence becomes:
- deterministic
- reproducible
- auditable offline

---

## Integration Philosophy

Autolog is intentionally minimal:

- one import
- one context / callback
- one NDJSON output stream

It must not slow training.
It must not leak raw data.
It must output boring evidence artifacts.

---

## Status

This document is open-safe.
Implementation may exist in PRO as a plug-in module.

