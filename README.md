# CROVIA Core Engine

**CROVIA Core Engine** is an open, verifiable **trust & payout layer for AI training data**.

It turns attribution logs (e.g. FAISS-based similarity logs, MIT-style valuation outputs, etc.) into:

- monthly **payouts per provider**
- **floors** (governance knobs on minimum compensation)
- a sign-ready **Trust Bundle JSON** (`crovia_trust_bundle.v1`)
- supporting evidence: Merkle summary, hashchain, trust reports

This repo ships the **same engine** currently running at:

> https://croviatrust.com/faiss-demo

for a FAISS-based demo run over a real attribution log.

---

## 1. Repository layout

Key directories and files:

- `crovia_app.py` – FastAPI app (dashboard, sandbox, FAISS demo page).
- `run_period.py` – end–to–end monthly run:
  - read receipts
  - compute payouts
  - generate charts + README
  - write Trust Bundle JSON
- `crovia_trust.py` – trust metrics per provider.
- `crovia_floor.py` – floor checks vs payouts.
- `tools/build_merkle_payouts.py` – build `merkle_payouts.v1` + `crovia_trust_bundle.v1` (with CROVIA-ID).
- `trust_bundle_validator.py` – offline validator for Trust Bundles.
- `verify_hashchain.py`, `hashchain_writer.py` – append-only hashchain over NDJSON payouts.
- `model_side/` – FAISS-based attribution toy pipeline (for demos and tests).
- `docs/` – specs & guides:
  - `CROVIA_TRUST_BUNDLE_v1.md`
  - `CROVIA_FLOOR_STANDARD_v1.1.md`
  - `CROVIA_PROFILE_M0.md`
  - `CROVIA_AI_Training_Data_Trust_Profile_v1.0.md`
  - web docs for dashboard / sandbox / FAISS demo
- `templates/`, `static/` – web UI for dashboard + sandbox + FAISS demo.
- `data/schema/crovia_trust_bundle.v1.json` – JSON schema for Trust Bundles.

The engine is designed to be:

- **verifiable** – every declared artifact is checked for size + SHA-256
- **profiled** – explicit schema/profile IDs (`CROVIA_PROFILE_M0`, etc.)
- **contract-ready** – each run is bound to a **CROVIA-ID** and a standard **Floor Clause**.

---

## 2. Quickstart – FAISS DPI demo (2025-11)

This repository includes a reproducible FAISS-based demo run for period **2025-11**, using a real attribution log (providers and weights are not synthetic labels).

⚠️ The demo uses **local paths** and is meant to be run on a Linux box (or WSL) with Python 3.11+.

### 2.1 Install

From the repo root:

    python3 -m venv .venv
    source .venv/bin/activate

    pip install -r requirements.txt

---

### 2.2 Run the full pipeline

From the repo root:

1. **QA on receipts (FAISS-based log)**

    python3 qa_receipts.py data/royalty_from_faiss.ndjson

2. **Compute trust metrics & provider CSV + summary MD**

    python3 crovia_trust.py \
      --input data/royalty_from_faiss.ndjson \
      --min-appear 1 \
      --out-provider data/trust_providers.csv \
      --out-report docs/trust_summary.md

3. **Charts over payouts CSV**

    python3 make_payout_charts.py \
      --period 2025-11 \
      --csv data/dpi_payouts_2025-11.csv \
      --readme docs/README_PAYOUT_2025-11.md

4. **Hashchain over payouts NDJSON**

    python3 hashchain_writer.py \
      --source data/dpi_payouts_2025-11.ndjson \
      --chunk 1000 \
      --out proofs/hashchain_dpi_payouts_2025-11__chunk1000.txt

    python3 verify_hashchain.py \
      --source data/dpi_payouts_2025-11.ndjson \
      --chain proofs/hashchain_dpi_payouts_2025-11__chunk1000.txt \
      --chunk 1000

5. **Merkle summary + Trust Bundle with CROVIA-ID**

    python3 tools/build_merkle_payouts.py \
      --source data/dpi_payouts_2025-11.ndjson \
      --out proofs/merkle_payouts_2025-11.json \
      --period 2025-11 \
      --operator HF \
      --model-id crovia-dpi-demo \
      --profile-id CROVIA_DPI_FAISS_DEMO_v1 \
      --bundle-out demo_dpi_2025-11/output/trust_bundle_2025-11.json

You should see a line like:

    [CROVIA-ID] CROVIA-ID: CTB-2025-11-HF------8559 sha256=9d481b8f38f58be7

and a final validator result:

    python3 trust_bundle_validator.py \
      --bundle demo_dpi_2025-11/output/trust_bundle_2025-11.json

    [RESULT] Bundle OK: all declared artifacts match size and sha256.

---

## 3. CROVIA-ID – global settlement identifier

Each Trust Bundle run is associated with a CROVIA-ID, a compact, human-readable identifier for the settlement state of a given period/model/operator.

Example (current FAISS demo):

    CROVIA-ID: CTB-2025-11-HF------8559 sha256=9d481b8f38f58be7

**Structure:**

- `CROVIA-ID:` – fixed prefix (machine-parseable, grep-friendly).
- `CTB` – Crovia Trust Bundle.
- `2025-11` – settlement period.
- `HF------` – operator / tenant / model family (padded with `-` to a fixed width).
- `8559` – run index (derived from an internal sequence).
- `sha256=…` – first 16 hex chars of the SHA-256 over the payouts NDJSON.

The same line is:

- embedded in the Trust Bundle JSON (`crovia_id`, `crovia_id_line`)
- printed in logs
- intended to be quoted in contracts, invoices, DPIA / AI Act documentation, model cards, and any compliance artifacts.

The idea is similar to SPDX IDs for software licenses or ISIN for securities, but applied to AI data settlement states.

---

## 4. Crovia Floor Clause (contract snippet)

CROVIA introduces the concept of a **floor**: a governance constraint ensuring that no eligible data provider is paid less than a minimum amount defined in the bundle.

A minimal contractual clause, to be included in data/provider agreements, is:

> **Crovia Floor Clause (short form)**  
> For the period identified by the CROVIA-ID stated below, the parties agree that:  
> (i) the calculation of royalties owed to data providers shall follow the method implemented by the Crovia Core Engine for the Trust Bundle identified by such CROVIA-ID;  
> (ii) no eligible data provider shall receive a payment below the Crovia Floor defined in that bundle; and  
> (iii) in case of dispute, the values and evidence contained in the referenced Trust Bundle (including payouts, floors, Merkle summary and hashchain) shall prevail.

In practical use, the clause is coupled with a concrete ID, e.g.:

    CROVIA-ID: CTB-2025-11-HF------8559 sha256=9d481b8f38f58be7

---

## 5. Web dashboard & FAISS demo

The FastAPI app (`crovia_app.py`) exposes:

- `/` – main dashboard (payout tables, trust summary, charts).
- `/sandbox` – interactive sandbox (upload synthetic receipts, run engine).
- `/faiss-demo` – FAISS Attribution Evidence Demo (real-log DPI run).
- `/health` – simple healthcheck.

To run locally:

    uvicorn crovia_app:app --host 127.0.0.1 --port 8000

Then visit:

    http://127.0.0.1:8000/

in your browser.

The production deployment at `https://croviatrust.com` uses the same app, fronted by Nginx.

---

## 6. Profiles, docs and extensions

Core docs live in `docs/`:

- `CROVIA_PROFILE_M0.md` – base profile for `royalty_receipt.v1`.
- `CROVIA_AI_Training_Data_Trust_Profile_v1.0.md` – how to use Crovia for AI training datasets.
- `CROVIA_TRUST_BUNDLE_v1.md` – Trust Bundle JSON profile.
- `CROVIA_FLOOR_STANDARD_v1.1.md` – definition of floors and constraints.
- `DPI_*` docs – example of AI Act–style DPI / DPIA documentation for the 2025-11 run.
- `CROVIA_FAISS_DEMO.md` and `CROVIA_FAISS_DEMO_REAL.md` – offline versions of the FAISS demo pages.

Future work (tracked via issues) includes:

- adapters for MIT-style data valuation outputs
- additional profiles for different types of logs
- reference integrations with model hosting platforms

---

## 7. License

CROVIA Core Engine is released under the **Apache License, Version 2.0**.

See the `LICENSE` file for details.

