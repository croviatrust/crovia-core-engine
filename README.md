# Crovia Spider

**“If it’s already in the open training datasets of 2025–2026, it already has a Crovia receipt.”**

Crovia Spider turns existing open training corpora (e.g. LAION, C4, The Stack) into
standardized `spider_receipt.v1` NDJSON logs.

A `spider_receipt.v1` is the minimal unit of Crovia's awareness of a content item
in the training data ecosystem.

This repository contains:

- the formal spec: `docs/CROVIA_SPIDER_RECEIPT_v1.md`
- a reference implementation to generate receipts from LAION-style metadata
- a CLI: `crovia-spider from-laion ...`

## Quick start

Clone and install:

    git clone https://github.com/croviatrust/crovia-spider.git
    cd crovia-spider

    python -m venv .venv
    source .venv/bin/activate  # On Windows: .venv\Scripts\activate

    pip install -U pip
    pip install .

    crovia-spider --help

Example (LAION-style Parquet → spider_receipt NDJSON):

    crovia-spider from-laion \
      --metadata-path /data/laion/laion2B-en-meta.parquet \
      --out data/receipts_laion_sample.ndjson \
      --period 2025-12 \
      --sample 100000

This will produce an NDJSON file where each line is a valid `spider_receipt.v1`.

See `docs/CROVIA_SPIDER_RECEIPT_v1.md` for the full specification.

---

## CROVIA Spider – Real evidence runs

- **GSM8K (OpenAI math word problems, HF mirror `oieieio/gsm8k`)**  
  - Period: 2025-12  
  - Receipts: 7,473 `spider_receipt.v1` entries  
  - Docs: [docs/README_SPIDER_GSM8K_2025-12.md](docs/README_SPIDER_GSM8K_2025-12.md)

HEAD
```bash
cd /opt/crovia
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 2.2 Full period run

```bash
python run_period.py \
  --period 2025-11 \
  --eur-total 1000000 \
  --receipts data/royalty_from_faiss.ndjson \
  --min-appear 1
```

This will:

* Run QA
* Compute trust metrics
* (Optional) run schema validation (`crovia_validate.py`)
* (Optional) run AI-Act helpers (`compliance_ai_act.py`)
* Compute payouts
* Generate charts
* Build & verify a hash-chain
* Compute Crovian Floors
* (Optional) build a Trust Bundle

Artifacts generated:

```text
data/trust_providers.csv
docs/trust_summary.md
data/payouts_2025-11.csv
data/payouts_2025-11.ndjson
data/floors_2025-11.json
charts/payout_top10_2025-11.png
charts/payout_cumulative_2025-11.png
proofs/hashchain_*.txt
```

For a detailed operator view, see:

```text
docs/CROVIA_OPEN_CORE_FAISS_2025-11_OVERVIEW.md
```

---

## 2.3 Running the entire demo via C-LINE (recommended)

C-LINE is the unified command-line interface for the CROVIA Core Engine.
It wraps all internal scripts (validation, trust, payouts, floors, hash-chain,
AI Act helpers, ZIP evidence builder) into a single, user-friendly CLI.

Run the full 2025-11 demo with one command:

```bash
python tools/c_line.py demo
# future installation:
#   c-line demo
```

This will automatically:

* validate the receipts NDJSON
* run trust aggregation
* compute payouts (`payouts.v1`)
* generate payout charts
* compute **Crovian Floors v1.1**
* run **AI Act Annex-IV documentation** helpers
* write a **SHA-256 hash-chain** and verify it
* collect all artifacts into a **ZIP evidence pack**
* generate a **QR code** pointing to the pack

Artifacts produced:

```text
evidence/CROVIA_evidence_2025-11.zip
proofs/QR_evidence_2025-11.png
docs/VALIDATE_report_2025-11.md
docs/AI_ACT_summary_2025-11.md
data/payouts_2025-11.csv
data/floors_2025-11.json
# plus ~30 additional files: charts, logs, packs, proofs
```

**C-LINE v1.0** turns the CROVIA demo into a *single-shot reproducible evidence pipeline*.

# 2.4 Install as a CLI (C-LINE)

You can also install the CROVIA Core Engine as a local CLI inside a virtualenv:

```bash
pip install -e .
c-line demo
```
This will install the c-line entrypoint in your environment and run the full
CROVIA demo pipeline (validation → trust → payouts → floors → hash-chain →
AI Act helpers → ZIP + QR evidence pack) with a single command.

# 3. DPI demo – Trust Bundle example

The repository includes a small DPI demo showing:

* DPI-based `royalty_receipt.v1` logs
* payouts, floors, trust CSVs
* AI Act-style documentation
* SHA-256 evidence digests consolidated in `trust_bundle.v1`

Validate the bundle:

```bash
python trust_bundle_validator.py \
  --bundle demo_dpi_2025-11/output/trust_bundle_2025-11.json \
  --base-dir /opt/crovia
```

Expected output (abridged):

```text
[*] Loading bundle: .../trust_bundle_2025-11.json
schema=crovia_trust_bundle.v1  period=2025-11

=== Artifact verification ===
[RESULT] Bundle OK: all declared artifacts match size and sha256.
```

A Trust Bundle acts as a **hash-addressable evidence pack** for auditors, regulators and partners.

Full profile:

```text
docs/CROVIA_TRUST_BUNDLE_v1.md
```

---

# 4. Validation, AI Act & Evidence Tools

The open-core engine includes transparent validation and compliance modules for auditors, researchers and model-card workflows.

## 4.1 Schema & QA Validation — `crovia_validate.py`

Validates `royalty_receipt.v1` NDJSON files:

* schema correctness
* share ≈ 1.0 checks
* rank ordering
* malformed / suspicious rows

Produces:

* validation report (Markdown)
* sample failing rows

Example:

```bash
python crovia_validate.py data/royalty.ndjson \
  --out-md docs/VALIDATE_report.md \
  --out-bad data/royalty_bad_sample.ndjson
```

Outputs:

```text
docs/VALIDATE_*.md
data/*_bad_sample.ndjson
```

---

## 4.2 AI Act Annex IV Helpers — `compliance_ai_act.py`

Generates lightweight Annex-IV-style documentation:

* provider & shard distribution
* provenance hints
* concentration & risk signals
* gaps file (`*_gaps.ndjson`)
* JSON compliance pack

Run:

```bash
python compliance_ai_act.py data/royalty.ndjson \
  --out-summary docs/AI_ACT_summary.md \
  --out-gaps data/AI_ACT_gaps.ndjson \
  --out-pack data/AI_ACT_pack.json
```

---

## 4.3 CCL Validation — `tools/ccl_validate.py`

Validates CCL v1.1 JSON descriptors for:

* AI models
* datasets
* RAG indices
* APIs / tools

Run:

```bash
python tools/ccl_validate.py my_model.ccl.json
```

Full CCL spec:

```text
docs/CROVIA_CCL_v1.1.md
```


## 4.4 CEP Evidence Protocol v1 — `crovia_generate_cep.py`

CROVIA CEP.v1 is a compact, verifiable evidence block for:

* Hugging Face model cards
* research papers
* audit packs
* trust bundle metadata

Generated via:

```bash
python tools/crovia_generate_cep.py \
  --trust-bundle trust_bundle.json \
  --period 2025-11 \
  --receipts data/royalty.ndjson \
  --payouts data/payouts.csv \
  --hashchain proofs/hashchain_*.txt \
  --engine-version demo-2025 \
  --output-format yaml
```

The result includes:

* SHA-256 of receipts / payouts / bundle
* hash-chain root
* trust metrics (avg_top1_share, DP epsilon range, CI indicators)
* generation metadata

Full spec:


docs/CROVIA_CEP_v1.md




# 5. Status & scope

This repository is:

* **Open-core** — attribution → trust → payouts → floors → proofs
* **Demo-grade** — synthetic data
* **Evidence-first** — built for transparency, auditability, reproducibility

Business logic, contracts, billing, CCT-attested tokens and settlement overrides live in the **private PRO engine**, not here.



# 6. Licensing

Apache License 2.0

Permitted:

* commercial or academic usage
* modification and redistribution
* closed or open derivatives
* integration into external pipelines

See the `LICENSE` file.



# 7. Copyright

© 2025 — **Tarik En Nakhai**
Crovia Core Engine

This repository includes a `NOTICE` file (Apache-2.0 requirement).



# 8. Contact


info@croviatrust.com

https://croviatrust.com


[![License: Apache-2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
=======
>>>>>>> 394d7a4 (Spider: add real GSM8K evidence run (spider_receipt.v1))
