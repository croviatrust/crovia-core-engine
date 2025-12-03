# CROVIA Core Engine

CROVIA is a **settlement and evidence engine** for AI data attribution.

This repository contains an **open-core demo** that shows how to turn attribution logs into:

- per-provider trust / priority metrics  
- monthly payouts (payouts.v1)  
- **Crovian Floors v1.1** (coverage-based minimums)  
- a SHA-256 hash-chain over receipts / payouts  
- a sign-ready **Trust Bundle JSON** (trust_bundle.v1) for audit and governance  
- optional **AI Act documentation**, schema validation, **CEP evidence blocks**

All numbers in this repository are demo-only and do not represent real commercial contracts or real providers.

---

# 1. FAISS open-core demo (period 2025-11)

The demo is wired to:

data/royalty_from_faiss.ndjson

A synthetic FAISS attribution log (royalty_receipt.v1) with **200 outputs** and **4 providers**.

## 1.1 Main components

qa_receipts.py — QA checks on receipts  
crovia_trust.py — trust / priority aggregation  
payouts_from_royalties.py — monthly payouts (payouts.v1)  
crovia_floor.py — Crovian Floors v1.1  
hashchain_writer.py / verify_hashchain.py — SHA-256 hash-chain  
run_period.py — orchestrator (trust → payouts → floors → proofs)  
trust_bundle_validator.py — validator for trust_bundle.v1  

## 1.2 Key documentation

docs/CROVIA_FAISS_DEMO.md  
docs/README_PAYOUT_2025-11.md  
docs/CROVIA_WEB_TRUST_PAYOUT_2025-11.md  
docs/CROVIA_OPEN_CORE_FAISS_2025-11_OVERVIEW.md  
docs/CROVIA_TRUST_BUNDLE_v1.md  

---

# 2. Quickstart – running the 2025-11 demo

## 2.1 Environment setup

cd /opt/crovia  
python -m venv .venv  
source .venv/bin/activate  
pip install -r requirements.txt

## 2.2 Full period run

python run_period.py \
  --period 2025-11 \
  --eur-total 1000000 \
  --receipts data/royalty_from_faiss.ndjson \
  --min-appear 1

This will:

- Run QA  
- Compute trust metrics  
- (Optional) run schema validation (crovia_validate.py)  
- (Optional) run AI-Act helpers (compliance_ai_act.py)  
- Compute payouts  
- Generate charts  
- Build & verify a hash-chain  
- Compute Crovian Floors  
- (Optional) build a Trust Bundle  

Artifacts generated:

data/trust_providers.csv  
docs/trust_summary.md  
data/payouts_2025-11.csv  
data/payouts_2025-11.ndjson  
data/floors_2025-11.json  
charts/payout_top10_2025-11.png  
charts/payout_cumulative_2025-11.png  
proofs/hashchain_*.txt  

For a detailed operator view, see:

docs/CROVIA_OPEN_CORE_FAISS_2025-11_OVERVIEW.md

---

# 3. DPI demo – Trust Bundle example

The repository includes a small DPI demo showing:

- DPI-based royalty_receipt.v1 logs  
- payouts, floors, trust CSVs  
- AI Act-style documentation  
- SHA-256 evidence digests consolidated in trust_bundle.v1  

Validate the bundle:

python trust_bundle_validator.py \
  --bundle demo_dpi_2025-11/output/trust_bundle_2025-11.json \
  --base-dir /opt/crovia

Expected output (abridged):

[*] Loading bundle: .../trust_bundle_2025-11.json  
schema=crovia_trust_bundle.v1  period=2025-11  

=== Artifact verification ===  
- payouts_ndjson …  

Result: **Bundle OK: all declared artifacts match size and sha256.**

A Trust Bundle acts as a **hash-addressable evidence pack** for auditors, regulators and partners.

Full profile:

docs/CROVIA_TRUST_BUNDLE_v1.md

---

# 4. Validation, AI Act & Evidence Tools

The open-core engine includes transparent validation and compliance modules for auditors, researchers and model-card workflows.

## 4.1 Schema & QA Validation — crovia_validate.py

Validates royalty_receipt.v1 NDJSON files:

- schema correctness  
- share ≈ 1.0 checks  
- rank ordering  
- malformed/suspicious rows  

Produces:

- validation report (Markdown)  
- sample failing rows  

Example:

python crovia_validate.py data/royalty.ndjson \
  --out-md docs/VALIDATE_report.md \
  --out-bad data/royalty_bad_sample.ndjson

Outputs:

docs/VALIDATE_*.md  
data/*_bad_sample.ndjson  

---

## 4.2 AI Act Annex IV Helpers — compliance_ai_act.py

Generates lightweight Annex-IV-style documentation:

- provider & shard distribution  
- provenance hints  
- concentration & risk signals  
- gaps file (*_gaps.ndjson)  
- JSON compliance pack  

Run:

python compliance_ai_act.py data/royalty.ndjson \
  --out-summary docs/AI_ACT_summary.md \
  --out-gaps data/AI_ACT_gaps.ndjson \
  --out-pack data/AI_ACT_pack.json

---

## 4.3 CCL Validation — tools/ccl_validate.py

Validates CCL v1.1 JSON descriptors for:

- AI models  
- datasets  
- RAG indices  
- APIs / tools  

Run:

python tools/ccl_validate.py my_model.ccl.json

Full CCL spec: docs/CROVIA_CCL_v1.1.md

---

## 4.4 CEP Evidence Protocol v1 — docs/CROVIA_CEP_v1.md

CROVIA CEP.v1 is a compact, verifiable evidence block for:

- Hugging Face model cards  
- research papers  
- audit packs  
- trust bundle metadata  

Generated via:

python tools/crovia_generate_cep.py \
  --trust-bundle trust_bundle.json \
  --period 2025-11 \
  --receipts data/royalty.ndjson \
  --payouts data/payouts.csv \
  --hashchain proofs/hashchain_*.txt \
  --engine-version demo-2025 \
  --output-format yaml

The result includes:

- SHA-256 of receipts / payouts / bundle  
- hash-chain root  
- trust metrics (avg_top1_share, DP epsilon range, CI indicators)  
- generation metadata  

Full spec: docs/CROVIA_CEP_v1.md

---

# 5. Status & scope

This repository is:

- **Open-core** — attribution → trust → payouts → floors → proofs  
- **Demo-grade** — synthetic data  
- **Evidence-first** — built for transparency, auditability, reproducibility  

Business logic, contracts, billing, CCT-attested tokens and settlement overrides live in the **private PRO engine**, not here.

---

# 6. Licensing

Apache License 2.0

Permitted:

- commercial or academic usage  
- modification and redistribution  
- closed or open derivatives  
- integration into external pipelines  

See LICENSE file.

---

# 7. Copyright

© 2025 — **Tarik En Nakhai**  
Crovia Core Engine

This repository includes a NOTICE file (Apache-2.0 requirement).

---

# 8. Contact

info@croviatrust.com  
https://croviatrust.com
