# CROVIA – FAISS Open-Core Demo (period 2025-11)

This document is a **quick operator overview** for the CROVIA FAISS-based  
open-core demo (period **2025-11**).

It ties together:

- a real **FAISS attribution log** (`data/royalty_from_faiss.ndjson`)
- **trust / priority aggregation** per provider (`crovia_trust.py`)
- **monthly payouts** (`payouts_from_royalties.py`)
- **Crovian Floors v1.1** (`crovia_floor.py`)
- a **hash-chain** over the receipts (`hashchain_writer.py` + `verify_hashchain.py`)
- a **Trust Bundle validator** (`trust_bundle_validator.py`)

All values are computed from **demo-grade synthetic data** and do not  
represent real commercial contracts.

---

## 1. Key files for the FAISS open-core demo

### Core scripts

- `qa_receipts.py`  
  QA on `royalty_receipt.v1` NDJSON (share sum, negative shares, rank order).

- `crovia_trust.py`  
  Aggregates provider-level **trust / priority** metrics and writes:  
  - `data/trust_providers.csv`  
  - `docs/trust_summary.md`

- `payouts_from_royalties.py`  
  Turns FAISS receipts into monthly payouts:  
  - `data/payouts_2025-11.csv`  
  - `data/payouts_2025-11.ndjson`  
  - `data/payouts_2025-11.log`  
  - `data/assumptions_2025-11.json`

- `crovia_floor.py`  
  Computes **Crovian Floors v1.1** and writes:  
  - `data/floors_2025-11.json`

- `hashchain_writer.py` / `verify_hashchain.py`  
  Build and verify a **rolling SHA-256 hash-chain** over NDJSON logs.

- `run_period.py`  
  Orchestration entrypoint:  
  QA → trust → (optional validation / AI-Act helpers) → payouts → charts → hashchain → floors → (optional) trust bundle.

- `trust_bundle_validator.py`  
  Offline validator for `crovia_trust_bundle.v1` JSON (used for DPI bundle and future open-core bundles).

### Documentation relevant to this demo

- `docs/CROVIA_FAISS_DEMO.md` – FAISS attribution evidence narrative  
- `docs/README_PAYOUT_2025-11.md` – payout & concentration charts  
- `docs/CROVIA_WEB_TRUST_PAYOUT_2025-11.md` – web summary for 2025-11  
- `docs/CROVIA_TRUST_BUNDLE_v1.md` – Trust Bundle JSON profile spec

---

## 2. Re-running the FAISS demo (2025-11) from the CLI

From a fresh virtualenv with the repo cloned:

    cd /opt/crovia_staging/open_core
    source ../.venv/bin/activate

Run:

    python run_period.py \
      --period 2025-11 \
      --eur-total 1000000 \
      --receipts ../data/royalty_from_faiss.ndjson \
      --min-appear 1

### What this does (open-core edition)

**QA on receipts**

    qa_receipts.py ../data/royalty_from_faiss.ndjson

On success you should see something like:

    [QA] bad_sum=0  bad_neg=0  bad_order=0

**Trust aggregation**

    crovia_trust.py --input ../data/royalty_from_faiss.ndjson ...

Outputs:

- `data/trust_providers.csv`  
- `docs/trust_summary.md`

**(Optional) Schema + business validation**

If present:

- `crovia_validate.py` – schema / business checks  
- `compliance_ai_act.py` – AI-Act helper reports  

These can be safely skipped in this open-core edition if the scripts are missing.

**Payouts**

    payouts_from_royalties.py \
      --period 2025-11 \
      --eur-total 1000000 \
      ...

Outputs:

- `data/payouts_2025-11.csv`  
- `data/payouts_2025-11.ndjson`  
- `data/payouts_2025-11.log`  
- `data/assumptions_2025-11.json`

**Payout charts (non-blocking)**

If `make_payout_charts.py` is present:

    make_payout_charts.py --period 2025-11 --csv data/payouts_2025-11.csv ...

Refreshes:

- `charts/payout_top10_2025-11.png`  
- `charts/payout_cumulative_2025-11.png`

**Hash-chain over the receipts (non-blocking)**

    hashchain_writer.py \
      --source ../data/royalty_from_faiss.ndjson \
      --chunk 1000 \
      --out proofs/hashchain_royalty_from_faiss.ndjson__<tag>__chunk1000.txt

Verification:

    verify_hashchain.py \
      --source ../data/royalty_from_faiss.ndjson \
      --chain proofs/hashchain_royalty_from_faiss.ndjson__<tag>__chunk1000.txt \
      --chunk 1000

Expected: an OK message if the chain is consistent.

**Crovian Floors v1.1**

    crovia_floor.py \
      --period 2025-11 \
      --eur-total 1000000 \
      --providers data/trust_providers.csv \
      --out data/floors_2025-11.json

Outputs:

- `data/floors_2025-11.json`

**Trust Bundle (optional in open-core)**

If `make_trust_bundle.py` is present, it builds a `crovia_trust_bundle.v1` JSON  
for the period. In this open-core edition, the governance layer can remain  
private, so this step is skipped if the script is missing.

**Augment Trust Bundle (optional)**

If `augment_trust_bundle.py` is present, it may enrich the bundle with additional  
governance metadata. Again, safe to skip in this edition.

At the end you should see something like:

    === CROVIA PERIOD RUN COMPLETED ===

and all expected artifacts in `data/`, `charts/`, `proofs/` and `docs/`.

---

## 3. DPI demo Trust Bundle (reference)

In addition to the FAISS open-core run, this repository ships a DPI payout demo  
with a sign-ready `crovia_trust_bundle.v1` JSON.

Validation example:

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

This shows how a single JSON Trust Bundle can anchor payouts, trust metrics,  
compliance artefacts and proofs in a way that any third party can verify offline.

---

## 4. Further reading

This overview is meant as the entry point for engineers and auditors looking at  
the FAISS open-core demo for the first time. For more details, see:

- `docs/CROVIA_FAISS_DEMO.md`
- `docs/README_PAYOUT_2025-11.md`
- `docs/CROVIA_WEB_TRUST_PAYOUT_2025-11.md`
- `docs/CROVIA_TRUST_BUNDLE_v1.md`

