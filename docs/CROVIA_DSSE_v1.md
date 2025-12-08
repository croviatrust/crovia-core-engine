# CROVIA – DSSE v1 (Directional Semantic Summarization Engine)

`DSSE` (Directional Semantic Summarization Engine) is an **experimental semantic layer**
designed to compress large attribution logs into **small, directional summaries** that
remain useful for:

- provenance & evidence (Crovia-style receipts),
- model / dataset debugging,
- high-level analytics on provider impact.

The core ideas:

## 1. Directional summarization

Instead of storing raw rows, DSSE tracks how a provider *moves* the semantic space via:

- forward projections  
- backward projections  
- deltas  
- echo-residuals  

These describe the “directional force” a provider contributes to a dataset.

## 2. Round-trip friendliness

DSSE summaries are designed so that a downstream PRO engine can **reconstruct**
fine-grained semantic behavior within a controlled error bound.

## 3. Stream-aware operation

DSSE can operate incrementally:

- read chunk  
- update semantic accumulators  
- update forward/backward deltas  
- update echo  
- write summary  

This makes it viable for TB-scale logs.

## 4. Open-core vs PRO boundary

This open-core version provides:

- clean data structures  
- deterministic behavior  
- safe hooks for external tools  

BUT **never exposes**:

- advanced scoring  
- proprietary mixture formulas  
- reconstruction methods  
- weight inference  
- trust or DPI transformations  

Those live **only inside the PRO engine**.

---

This file documents the *shape* of DSSE for open-core users without revealing any PRO-only logic.
