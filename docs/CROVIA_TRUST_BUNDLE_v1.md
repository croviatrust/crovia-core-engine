# CROVIA – `trust_bundle.v1` Profile Specification

This document defines the **`trust_bundle.v1`** JSON profile used by CROVIA to
collect all evidence produced during a period run (trust, payouts, floors,
compliance, hashchain/Merkle proofs).

A *Trust Bundle* is a compact, hash-addressable, sign-ready JSON object that
allows any third party (auditor, regulator, partner) to verify the correctness
and integrity of a full CROVIA settlement run **offline**.

---

## 1. Purpose

A `trust_bundle.v1` is designed to provide:

- a reproducible and tamper-evident record of:
  - attribution logs (`royalty_receipt.v1`),
  - payouts (`payouts.v1`),
  - trust metrics,
  - floors,
  - compliance artefacts,
  - cryptographic integrity proofs;
- a single, portable JSON that can be archived or attached to governance,
  AI-Act documentation, DPIA, internal reports, or external audits.

---

## 2. Top-level structure

A typical `trust_bundle.v1` has the following structure:

    {
      "schema": "trust_bundle.v1",
      "period": "2025-11",
      "profile_id": "CROVIA_FAISS_DEMO_v1",
      "model_id": "crovia-dpi-demo",
      "created_at": "2025-11-28T12:00:00Z",

      "engine": {
        "implementation": "crovia-core-engine",
        "version": "2025.11"
      },

      "inputs": {
        "royalty_receipts": { /* see §3 */ }
      },

      "artifacts": {
        "payouts_ndjson": { /* see §4 */ },
        "merkle_payouts": { /* see §4 */ },
        "trust_providers_csv": { /* see §4 */ },
        "trust_summary_md": { /* see §4 */ }
      },

      "stats": {
        "total_outputs": 200,
        "providers": 4,
        "budget_eur": 1000000.00,
        "paid_out_eur": 1000000.00
      },

      "attestations": [
        /* optional digital signatures or external anchors */
      ]
    }

Only fields under **`artifacts`** and **`inputs`** are hash-checked by
`trust_bundle_validator.py`.

---

## 3. `inputs.royalty_receipts`

This section records the attribution log used for the period:

    "inputs": {
      "royalty_receipts": {
        "path": "data/royalty_from_faiss.ndjson",
        "bytes": 792921,
        "sha256": "9d481b8f38f58be7eafeb49b10f20d2521b0c9a4edd74d0dfab2bcb0b578a79c",
        "schema": "royalty_receipt.v1"
      }
    }

Rules:

- `path` is relative to the bundle root.
- `bytes` is the exact size of the file.
- `sha256` is computed over the raw file bytes (hex, lowercase).
- `schema` MUST be `royalty_receipt.v1`.

---

## 4. `artifacts.*`

Every artifact referenced in the bundle has the same canonical structure:

    "payouts_ndjson": {
      "path": "data/dpi_payouts_2025-11.ndjson",
      "bytes": 792921,
      "sha256": "9d481b8f38f58be7eafeb49b10f20d2521b0c9a4edd74d0dfab2bcb0b578a79c",
      "schema": "payouts.v1"
    }

Other artifacts follow the same pattern, for example:

- `merkle_payouts`
- `trust_providers_csv`
- `trust_summary_md`
- additional compliance or floors artifacts (if included in that edition)

Notes:

- `schema` identifies machine-readable formats (e.g. `payouts.v1`).
- Human-readable reports may include a `kind` field
  (e.g. `"trust_report"`, `"validation_report"`).
- All `path` values MUST be relative and must match both size and SHA-256
  when checked by the validator.

---

## 5. `stats`

The `stats` section summarizes the period settlement:

    "stats": {
      "total_outputs": 200,
      "providers": 4,
      "budget_eur": 1000000.00,
      "paid_out_eur": 1000000.00
    }

This enables quick inspection of the core settlement state.

---

## 6. `attestations`

`attestations` allows optional anchoring or digital signatures:

    "attestations": [
      {
        "type": "pgp-signature.v1",
        "key_id": "....",
        "created_at": "2025-11-28T12:30:00Z",
        "signature": "base64-encoded-signature"
      }
    ]

CROVIA does not enforce a specific signature scheme.

Examples include:

- PGP / OpenPGP signatures
- X.509 / PKI signatures
- blockchain-anchored proofs referenced via an external ID

---

## 7. CROVIA Settlement Identifier (CROVIA-ID)

Each settlement state is assigned a compact identifier:

    CROVIA-ID: CTB-<PERIOD>-<OPERATOR:8><RUN:4> sha256=<SHA16>

Example from the FAISS/DPI demo:

    CROVIA-ID: CTB-2025-11-HF------8559 sha256=9d481b8f38f58be7

This identifier:

- appears at the top of the bundle,
- is derived from the payouts NDJSON,
- can be safely included in contracts, DPIA, AI-Act documentation,
- serves as a stable anchor for legal clauses (CROVIA Floor Clause).

---

## 8. Verification

A bundle is validated by:

    python3 trust_bundle_validator.py \
      --bundle demo_dpi_2025-11/output/trust_bundle_2025-11.json

If all artifact paths exist and match expected byte sizes and SHA-256 digests,
the validator outputs:

    [RESULT] Bundle OK: all declared artifacts match size and sha256.

This allows offline, reproducible verification of the entire settlement state.

---

## 9. Extensibility

`trust_bundle.v1` is intentionally minimal and future-proof.

New fields may be added under:

- `artifacts.*`
- `engine.*`
- `attestations[]`

…as long as the core verification rules remain unchanged:

- `inputs.*` and `artifacts.*` must remain hash-checked.
- Paths must stay relative and byte-accurate.
- Stats must reflect the declared settlement state.

---

_End of specification._
