# CROVIA – Lite Tools Pack M1

This document describes the **CROVIA Lite Tools Pack (M1)**.

M1 is for organisations that:

- already have attribution logs compatible with `royalty_receipt.v1` (Profile M0), and  
- want **quality checks, policy validation and hashchain integrity**  
- without deploying the full enterprise engine.

All examples are synthetic and for illustration only.

---

## 1. Scope

The Lite Tools Pack covers:

1. **Receipt QA** – quick checks on sums, negatives, ordering.  
2. **Schema + business validation** – enforcing the `royalty_receipt.v1` contract and basic policy constraints.  
3. **AI Act record-keeping helper** – generating a compliance summary and a “compliance pack”.  
4. **Hashchain integrity** – writing and verifying hashchains over NDJSON logs.

The pack is intentionally **CLI-first** and can be embedded in CI pipelines or batch jobs.

---

## 2. Prerequisites

- Python **3.11+**
- CROVIA repository checked out (or the relevant scripts copied)
- A receipts file in **NDJSON** following `royalty_receipt.v1` (see Profile M0)

We assume a working directory like:

```text
/opt/crovia
  ├── qa_receipts.py
  ├── crovia_validate.py
  ├── compliance_ai_act.py
  ├── hashchain_writer.py
  ├── verify_hashchain.py
  └── data/
       └── your_royalty_logs.ndjson
```

---

## 3. Quickstart with your own receipts

Assume your log is at:

```text
data/royalty_yourlog.ndjson
```

### 3.1. Receipt QA

```bash
python3 qa_receipts.py data/royalty_yourlog.ndjson
```

The script reports:

- `bad_sum` – lines where `providers[*].weight` do not match `weight_total`  
- `bad_neg` – negative weights  
- `bad_order` – timestamp ordering issues  

Exit code `0` means “no hard errors found”.

---

### 3.2. Schema + business validation

```bash
python3 crovia_validate.py \
  --input data/royalty_yourlog.ndjson \
  --out-report validate_report.md \
  --out-bad validate_sample_bad.jsonl
```

Outputs:

- `validate_report.md` – human-readable report (totals, errors, warnings).  
- `validate_sample_bad.jsonl` – sample of failing lines (if any).

You can plug this step in CI and fail a build if:

- there are schema errors, or  
- the health grade drops below an agreed threshold.

---

### 3.3. AI Act compliance helper

```bash
python3 compliance_ai_act.py \
  --input data/royalty_yourlog.ndjson \
  --out-summary compliance_summary.md \
  --out-gaps data/compliance_gaps.csv \
  --out-pack data/compliance_pack.json
```

Outputs:

- `compliance_summary.md` – narrative summary of record-keeping status.  
- `data/compliance_gaps.csv` – machine-readable list of missing fields / gaps.  
- `data/compliance_pack.json` – JSON pack that can be archived with model cards, DPIA, etc.

The pack is meant to support **EU AI Act** record-keeping for training data usage.

---

### 3.4. Hashchain write

```bash
python3 hashchain_writer.py \
  --source data/royalty_yourlog.ndjson \
  --chunk 1000 \
  --out proofs/hashchain_royalty_yourlog__chunk1000.txt
```

This writes a hashchain file with one line per chunk, each line containing:

- chunk index and range  
- SHA-256 of the chunk  
- cumulative hash up to that point  

The exact format is documented in comments inside `hashchain_writer.py`.

---

### 3.5. Hashchain verify

```bash
python3 verify_hashchain.py \
  --source data/royalty_yourlog.ndjson \
  --chain proofs/hashchain_royalty_yourlog__chunk1000.txt \
  --chunk 1000
```

If all chunks match, you should see an **OK** message and exit code `0`.

This allows auditors or regulators to:

- verify that a log was not tampered with,  
- cross-check stored hashchain receipts against the current NDJSON file.

---

## 4. Typical CI pipeline (example)

A minimal CI job for a training run could be:

```bash
set -euo pipefail

RECEIPTS="data/royalty_${RUN_ID}.ndjson"

python3 qa_receipts.py "$RECEIPTS"

python3 crovia_validate.py \
  --input "$RECEIPTS" \
  --out-report "reports/validate_${RUN_ID}.md" \
  --out-bad "reports/validate_${RUN_ID}_bad.jsonl"

python3 compliance_ai_act.py \
  --input "$RECEIPTS" \
  --out-summary "reports/compliance_${RUN_ID}.md" \
  --out-gaps "reports/compliance_${RUN_ID}_gaps.csv" \
  --out-pack "reports/compliance_${RUN_ID}_pack.json"

python3 hashchain_writer.py \
  --source "$RECEIPTS" \
  --chunk 1000 \
  --out "proofs/hashchain_${RUN_ID}__chunk1000.txt"
```

You can then store:

- the receipts NDJSON,  
- the compliance pack JSON,  
- the hashchain file,  

in your long-term evidence archive.

---

## 5. Relation to Profile M0 and Enterprise engine (M2)

Profile **M0** defines the objects:

- `royalty_receipt.v1`  
- payout tables  
- Trust Bundle  

Lite Tools **M1** define a minimal operational layer:

- how to QA and validate receipts,  
- how to generate compliance artefacts,  
- how to protect log integrity via hashchains.

The enterprise engine (**M2**) extends M1 with:

- trust score computation,  
- payouts from a fixed budget,  
- floors, governance and Trust Bundles.

The tools in M1 are deliberately **engine-agnostic**: any implementation that emits
`royalty_receipt.v1` logs can use them.

---

## 6. Version and feedback

This document describes **CROVIA Lite Tools Pack M1 – version 1.0.0**.

Future versions may:

- add more checks or reports,  
- split tools into sub-profiles per regulatory scope,  
- provide containerised distributions.

For questions or proposals you can contact:

`info@croviatrust.com`
