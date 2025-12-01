# CROVIA Core Engine

CROVIA is a **settlement and evidence engine** for AI data attribution.

This repository contains an **open-core demo** that shows how to turn
attribution logs into:

- per-provider **trust / priority metrics**
- monthly **payouts** (`payouts.v1`)
- **Crovian Floors v1.1** (coverage-based minimums)
- a **hash-chain** over the logs (receipts, payouts, etc.)
- a sign-ready **Trust Bundle JSON** suitable for audit and governance

The demo uses:

- a **FAISS-based attribution log** (open-core, synthetic / demo-grade), and
- a **DPI payout example** with a `crovia_trust_bundle.v1` JSON.

> All numbers in this repository are **demo-only** and do *not* represent
> real commercial contracts or real providers.

---

## 1. FAISS open-core demo (period 2025-11)

The FAISS open-core demo is wired to:

- `../data/royalty_from_faiss.ndjson`  
  (`royalty_receipt.v1`, attribution log with 200 outputs and 4 providers)

The main scripts involved are:

- `qa_receipts.py` – quick QA over `royalty_receipt.v1` NDJSON
- `crovia_trust.py` – trust / priority aggregation per provider
- `payouts_from_royalties.py` – monthly payouts (`payouts.v1`)
- `crovia_floor.py` – Crovian Floors v1.1 from `trust_providers.csv`
- `hashchain_writer.py` / `verify_hashchain.py` – SHA-256 hash-chain over NDJSON
- `run_period.py` – orchestrates a full period run (trust + payouts + floors + proofs)
- `trust_bundle_validator.py` – standalone validator for `crovia_trust_bundle.v1` JSON

Key documentation for this demo:

- `docs/CROVIA_FAISS_DEMO.md`  
  FAISS attribution evidence demo (FAISS log → payouts → bundle).

- `docs/README_PAYOUT_2025-11.md`  
  Payout / concentration charts for the 2025-11 demo.

- `docs/CROVIA_WEB_TRUST_PAYOUT_2025-11.md`  
  Web-oriented summary of trust & payouts for 2025-11.

- `docs/CROVIA_OPEN_CORE_FAISS_2025-11_OVERVIEW.md`  
  Operator / auditor overview for the FAISS open-core demo.

---

## 2. Quickstart – re-running the FAISS demo

### 2.1 Environment

You need Python 3.10+ and a virtualenv. Typical setup:

    cd /opt/crovia_staging/open_core
    python -m venv ../.venv
    source ../.venv/bin/activate
    pip install -r requirements.txt    # if provided

Make sure the FAISS attribution log is present at:

    ../data/royalty_from_faiss.ndjson

### 2.2 Run the full period (2025-11)

    cd /opt/crovia_staging/open_core
    source ../.venv/bin/activate

    python run_period.py \
      --period 2025-11 \
      --eur-total 1000000 \
      --receipts ../data/royalty_from_faiss.ndjson \
      --min-appear 1

This will:

- QA the receipts (`qa_receipts.py`)
- Aggregate trust / priority metrics (`crovia_trust.py`)
- Optionally run schema / business validation (`crovia_validate.py` if present)
- Optionally run AI Act helpers (`compliance_ai_act.py` if present)
- Compute payouts (`payouts_from_royalties.py`)
- Generate payout charts (`make_payout_charts.py`, if present)
- Build a hash-chain over the receipts (`hashchain_writer.py`)
- Verify the hash-chain (`verify_hashchain.py`)
- Optionally build a Trust Bundle (`make_trust_bundle.py`, if present)
- Compute Crovian Floors v1.1 (`crovia_floor.py`)
- Optionally augment the bundle (`augment_trust_bundle.py`, if present)

On success you should see something like:

    === CROVIA PERIOD RUN COMPLETED ===

and the following artifacts (among others):

- `data/trust_providers.csv`
- `docs/trust_summary.md`
- `data/payouts_2025-11.csv`
- `data/payouts_2025-11.ndjson`
- `data/floors_2025-11.json`
- `charts/payout_top10_2025-11.png`
- `charts/payout_cumulative_2025-11.png`
- `proofs/hashchain_royalty_from_faiss.ndjson__*.txt`

For a more detailed operator view, see:  
`docs/CROVIA_OPEN_CORE_FAISS_2025-11_OVERVIEW.md`.

---

## 3. DPI demo – Trust Bundle example

The repository also ships a **Data Provenance Initiative (DPI)** payout demo,
including a `crovia_trust_bundle.v1` JSON that ties together:

- DPI-based `royalty_receipt.v1` logs
- `payouts.v1` per provider
- trust / priority CSVs
- AI-Act-style compliance artefacts
- SHA-256 digests for all referenced files

You can validate the demo bundle as follows:

    cd /opt/crovia_staging/open_core
    source ../.venv/bin/activate

    python trust_bundle_validator.py \
      --bundle demo_dpi_2025-11/output/trust_bundle_2025-11.json \
      --base-dir /opt/crovia

Expected output (abridged):

    [*] Loading bundle: .../trust_bundle_2025-11.json
        schema=crovia_trust_bundle.v1  period=2025-11

    === Artifact verification ===
    - payouts_ndjson
      ...
    [RESULT] Bundle OK: all declared artifacts match size and sha256.

This shows how a single Trust Bundle can act as a **hash-addressable evidence pack**
for auditors, regulators and partners.

For a full profile of `trust_bundle.v1`, see:  
`docs/CROVIA_TRUST_BUNDLE_v1.md`.

---

## 4. Status and scope

This repository is:

- **Open-core** – focused on the core attribution → payouts → floors → proofs pipeline.
- **Demo-grade** – data and identifiers are synthetic or anonymized.
- **Engine-first** – the goal is to provide a transparent, testable engine
  that others can integrate into their own AI data pipelines.

Governance / contract layers (e.g. Crovian Floor Clause, provider registries,
KYC tiers) may live in separate, closed or hybrid components and are
out of scope for this repository.

---

 ## 5.Licensing

This project is released under the Apache License, Version 2.0.

You are free to:

use the code in commercial or academic environments

modify and redistribute it

build closed-source or open-source derivatives

integrate the engine into external pipelines

as long as you comply with the terms of the Apache-2.0 license.

The full license text is included in the LICENSE file.

## Copyright
Copyright 2025 Tarik En Nakhai


Crovia Core Engine and all original contributions are copyrighted by
Tarik En Nakhai, the original author and maintainer.

## NOTICE

This repository includes a NOTICE file, which must be preserved
in any source or binary redistribution as required by Apache-2.0.

The NOTICE currently states:

Crovia Core Engine
Copyright 2025 Tarik En Nakhai

This product includes components developed by Crovia Trust.
Website: https://croviatrust.com

First canonical trust bundle:
CTB-2025-11-HF------8559

Warranty disclaimer

Software is provided “as is”, without warranties or conditions
of any kind, as described in the license.

For details, see the full Apache License 2.0 text.

## 6. Contact

For questions, integration discussions or to run a **CROVIA-style settlement**
on your own attribution logs, you can reach:

    info@croviatrust.com

[![License: Apache-2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
    
    

