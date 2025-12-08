# CROVIA – DSSE v1 (Directional Semantic Summarization Engine)

`DSSE` (Directional Semantic Summarization Engine) is an **experimental semantic layer**
designed to compress large attribution logs into **small, directional summaries** that
remain useful for:

- provenance & evidence (Crovia-style receipts),
- model / dataset debugging,
- high-level analytics on provider impact.

The core ideas:

- **Directional summarization**:
  - instead of storing every raw row, DSSE tracks how a provider “moves” the
    semantic space (forward / backward projections, deltas, echoes).
- **Round-trip friendly**:
  - summaries are designed so that a downstream PRO engine can reconstruct
    fine-grained views (within a controlled error bound) if needed.
- **Stream-aware**:
  - DSSE can operate in streaming mode, consuming chunks of data and
    updating the semantic state incrementally.

This open-core implementation focuses on:

- clean, auditable data structures,
- deterministic behaviour for the same input,
- hooks that can be called from:
  - CLI tools,
  - the core engine,
  - external analysis scripts.

> NOTE (important):
> - The **open-core DSSE** provides a transparent, inspectable semantic layer.
> - Any advanced / proprietary scoring or compression logic belongs to the
>   private **Crovia PRO** engine and is **not** implemented here.
