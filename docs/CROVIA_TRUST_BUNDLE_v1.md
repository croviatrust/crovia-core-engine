# CROVIA – `trust_bundle.v1`

This note defines the **`trust_bundle.v1`** JSON profile.

A *Trust Bundle* is a compact, hash-addressable evidence pack that ties together:

- the **attribution logs** (`royalty_receipt.v1`),
- the resulting **payouts** (`payouts.v1`),
- **trust / priority metrics** per provider,
- **validation and compliance reports** (e.g. EU AI Act),
- and the **hashes** of all these artifacts.

The goal is to produce **one sign-ready JSON object** that an auditor, regulator or partner can verify offline.

---

## 1. Top-level shape

A `trust_bundle.v1` JSON has the following top-level fields:

```jsonc
{
  "schema": "trust_bundle.v1",
  "profile_id": "CROVIA_M0_DPI_DEMO_v1",
  "period": "2025-11",
  "model_id": "crovia-dpi-demo-v1",

  "created_at": "2025-11-22T10:00:00Z",
  "engine": {
    "implementation": "crovia-trust-demo",
    "version": "2025-11.dpi.v1"
  },

  "jurisdictions": ["EU", "EU AI Act"],

  "inputs": {
    "royalty_receipts": { ... }
  },

  "artifacts": {
    "payouts_ndjson": { ... },
    "payouts_csv": { ... },
    "trust_providers_csv": { ... },
    "trust_summary_md": { ... },
    "validate_report_md": { ... },
    "ai_act_summary_md": { ... },
    "ai_act_pack_json": { ... },
    "compliance_gaps_csv": { ... }
  },

  "stats": {
    "total_outputs": 3718,
    "providers": 3717,
    "budget_eur": 1000000.00,
    "paid_out_eur": 999999.99
  },

  "attestations": [
    // optional digital signatures, PGP, notary anchors, etc.
  ]
}
```

---

## 2. `inputs.royalty_receipts`

The `inputs` section points to the attribution logs that drive the whole bundle.

```jsonc
"inputs": {
  "royalty_receipts": {
    "path": "data/dpi_royalty_receipts.ndjson",
    "bytes": 123456,
    "sha256": "…",
    "total_outputs": 3718,
    "schema": "royalty_receipt.v1"
  }
}
```

Requirements:

- `path` is relative to the bundle root.  
- `bytes` is the exact byte size of the file.  
- `sha256` is computed on the raw bytes of the file.  
- `schema` MUST be `royalty_receipt.v1`.

---

## 3. `artifacts.*`

Each artifact referenced in the bundle has the same core shape:

```jsonc
"artifacts": {
  "payouts_ndjson": {
    "path": "data/dpi_payouts_2025-11.ndjson",
    "bytes": 12345,
    "sha256": "…",
    "schema": "payouts.v1"
  },

  "payouts_csv": {
    "path": "data/dpi_payouts_2025-11.csv",
    "bytes": 23456,
    "sha256": "…",
    "schema": "payouts.v1",
    "providers": 3717,
    "total_amount": 1000000.00,
    "gross_revenue": 1000000.00,
    "currency": "EUR"
  },

  "trust_providers_csv": {
    "path": "data/dpi_trust_providers_2025-11.csv",
    "bytes": 34567,
    "sha256": "…",
    "kind": "trust_providers"
  },

  "trust_summary_md": {
    "path": "docs/DPI_TRUST_2025-11.md",
    "bytes": 4567,
    "sha256": "…",
    "kind": "trust_report"
  },

  "validate_report_md": {
    "path": "docs/DPI_VALIDATE.md",
    "bytes": 5678,
    "sha256": "…",
    "kind": "validation_report"
  },

  "ai_act_summary_md": {
    "path": "docs/DPI_AI_ACT_2025-11.md",
    "bytes": 6789,
    "sha256": "…",
    "kind": "ai_act_summary"
  },

  "ai_act_pack_json": {
    "path": "data/dpi_compliance_pack_2025-11.json",
    "bytes": 7890,
    "sha256": "…",
    "kind": "ai_act_pack"
  },

  "compliance_gaps_csv": {
    "path": "compliance_gaps.csv",
    "bytes": 8901,
    "sha256": "…",
    "kind": "compliance_gaps"
  }
}
```

Notes:

- `schema` is used for machine-readable objects (`payouts.v1`, etc.).  
- `kind` is used for human-oriented reports (`*_report`, `*_summary`, gaps CSV).  
- All paths are relative; hashes are computed on the referenced files.

---

## 4. `stats`

The `stats` section summarizes the run:

```jsonc
"stats": {
  "total_outputs": 3718,
  "providers": 3717,
  "budget_eur": 1000000.00,
  "paid_out_eur": 999999.99
}
```

Typical fields:

- `total_outputs` – number of attribution records (rows in `royalty_receipt.v1`).  
- `providers` – distinct `provider_id` that received a payout.  
- `budget_eur` – total EUR budget configured for the period.  
- `paid_out_eur` – sum of all `amount` in the payout CSV.

---

## 5. `attestations`

`attestations` is an extensible list intended for digital signatures and external notaries:

```jsonc
"attestations": [
  {
    "type": "pgp-signature.v1",
    "key_id": "…",
    "created_at": "2025-11-22T11:00:00Z",
    "signature": "base64-encoded-signature"
  }
]
```

The `trust_bundle.v1` profile does not mandate a specific signature scheme: PGP, X.509, or blockchain-anchored proofs can all be referenced here.

---

## 6. DPI demo: example instantiation

In the CROVIA DPI demo (2025-11), the bundle ties together:

- 3718 real finetuning datasets from the Data Provenance Initiative,  
- a €1M budget simulation over those datasets (`payouts.v1`),  
- per-dataset trust / priority bands,  
- an AI Act-style compliance pack with coverage & gaps,  
- and a single `trust_bundle.v1` JSON with SHA-256 hashes for each artifact.

This provides a single, sign-ready object that lets any third party recompute and verify:

> “Given these attribution logs and this policy, who was paid what, and which datasets were covered?”

---

## 1.x CROVIA settlement identifiers

A 
