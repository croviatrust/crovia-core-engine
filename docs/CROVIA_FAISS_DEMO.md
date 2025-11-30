# CROVIA – FAISS Attribution Evidence Demo (real log)

This page documents a full CROVIA run on a **FAISS-based attribution log** derived from a real dataset.

The goal is simple:

> Show how a real attribution log can be turned into  
> payouts, floors and a cryptographically verifiable evidence pack  
> that anyone can check offline.

---

## 0. Quick links

- **Trust Bundle JSON (public):** [`trust_bundle_2025-11.json`](/bundle/2025-11)
- **Payout charts (public previews):**
  - `/charts/payout_top10_2025-11.png`
  - `/charts/payout_cumulative_2025-11.png`

### Charts preview

Top-10 providers (share of budget):

![Top-10 providers](/charts/payout_top10_2025-11.png)

Cumulative distribution of payouts:

![Cumulative distribution](/charts/payout_cumulative_2025-11.png)

---

## 1. Base log (FAISS attribution)

**Working directory:**

    /opt/crovia

The demo uses a FAISS-based attribution log:

    data/royalty_from_faiss.ndjson

**Key properties:**

- format: `royalty_receipt.v1` (CROVIA Profile M0)
- generated from a real corpus (providers + weights are not synthetic labels)
- suitable for:
  - trust & payouts
  - floors (governance layer)
  - AI Act–style record-keeping
  - hashchain + bundle verification

For this run:

- **Period:** 2025-11
- **Total budget:** 1,000,000 EUR
- **Outputs considered:** see `validate_report.md`
- **Providers:** see `data/trust_providers.csv`

---

## 2. Evidence pack files

The FAISS-based run produces:

### Receipts (NDJSON)

- `data/royalty_from_faiss.ndjson`

### Trust report (Markdown)

- `trust_summary.md`

### Validation report + bad samples

- `validate_report.md`
- `validate_sample_bad.jsonl` (should be empty or very small)

### AI Act compliance helper

- `compliance_summary.md`
- `data/compliance_gaps.csv`
- `data/compliance_pack.json`

### Payouts per provider

- `data/payouts_2025-11.csv`
- `data/payouts_2025-11.ndjson`
- `README_PAYOUT_2025-11.md`

### Floors (governance layer)

- `data/floors_2025-11.json`

### Charts (distribution & concentration)

**File paths:**

- `charts/payout_top10_2025-11.png`
- `charts/payout_cumulative_2025-11.png`

**Embedded previews:**

Top-10 providers:  
![Top-10 providers](/charts/payout_top10_2025-11.png)

Cumulative distribution:  
![Cumulative distribution](/charts/payout_cumulative_2025-11.png)

### Hashchain over the receipts log

- `proofs/hashchain_royalty_from_faiss.ndjson__F7108871DE44__chunk1000.txt`  
  (or equivalent path produced by the run)

### Trust Bundle JSON (sign-ready)

- `trust_bundle_2025-11.json`

All file paths and SHA-256 hashes are recorded inside the Trust Bundle.

---

## 3. Verifying the Trust Bundle offline

On the host that produced the run:

    cd /opt/crovia
    source .venv/bin/activate

Run:

    python3 trust_bundle_validator.py \
      --bundle trust_bundle_2025-11.json

What it does:

- loads the bundle (`crovia_trust_bundle.v1`);
- for each declared artifact:
  - checks that the file exists;
  - compares size in bytes;
  - recomputes SHA-256 and compares with the recorded digest.

If everything matches, you should see:

    [RESULT] Bundle OK: all declared artifacts match size and sha256.

This is the single JSON you can hand to:

- auditors,
- regulators,
- internal risk teams,

together with the scripts, so they can tell you if the evidence is honest.

---

## 4. Verifying the hashchain on the FAISS log

To verify the integrity of the FAISS-based log itself:

    cd /opt/crovia
    source .venv/bin/activate

    python3 verify_hashchain.py \
      --source data/royalty_from_faiss.ndjson \
      --chain proofs/hashchain_royalty_from_faiss.ndjson__F7108871DE44__chunk1000.txt \
      --chunk 1000

This guarantees that:

- the NDJSON log has not been reordered;
- no chunk has been silently dropped or replaced;
- the cumulative hash matches the chain file.

For this demo you should see an **OK** message from the verifier.

---

## 5. Why this matters (beyond synthetic demos)

Unlike purely synthetic examples, this run is anchored in a real FAISS-based log:

- the distribution of value across providers reflects a real corpus;
- concentration metrics (HHI, Gini) are meaningful;
- floors can be inspected as governance knobs, not as toy numbers.

The message is:

> Once you emit `royalty_receipt.v1` logs from your own data,  
> CROVIA can turn them into payouts, floors and a verifiable evidence pack  
> without touching your training stack.

---

## 6. Extensibility

The same pattern can be applied to:

- open-source datasets (e.g. Dolly, OpenHermes, LAION subsets),
- MIT-style data valuation outputs (via adapters),
- HF-hosted datasets and models.

The steps don’t change:

1. Emit a log in `royalty_receipt.v1`
   (from FAISS, MIT tools, HF pipelines, custom collectors…)
2. Run the CROVIA engine for a period.
3. Produce:
   - payouts,
   - floors,
   - charts & concentration metrics,
   - compliance artefacts.
4. Build a Trust Bundle JSON for the period.
5. Hand the bundle + scripts to whoever needs to verify the run.

---

For questions or to try a similar run on your own dataset:  
**info@croviatrust.com**

---

## 5. Current FAISS DPI run (period 2025-11)

This public demo is currently wired to a single DPI payout run over the FAISS
attribution log.

The CROVIA-ID for this settlement state is:

    CROVIA-ID: CTB-2025-11-HF------8559 sha256=9d481b8f38f58be7

This CROVIA-ID line is:

- embedded in the `crovia_trust_bundle.v1` JSON
- derived from the payouts NDJSON (`data/dpi_payouts_2025-11.ndjson`)
- intended to be copied into contracts, DPIA / AI Act documentation and model cards
- referenced by the **Crovia Floor Clause** in legal text

---

### 5.1 Payout charts (top-10 and cumulative)

These charts are generated from `data/dpi_payouts_2025-11.csv`:

- Top-10 providers:  
  `/charts/payout_top10_2025-11.png`
- Cumulative distribution:  
  `/charts/payout_cumulative_2025-11.png`

They provide a quick visual snapshot of:

- how concentrated the budget is across providers
- how fast the cumulative payout curve grows (long tail vs heavy head)

---

### 5.2 Download the evidence pack

For this FAISS DPI run you can download:

- **Payouts CSV** (local run artifact, not shipped in the repo):  
  `data/dpi_payouts_2025-11.csv`

- **CROVIA Trust Bundle JSON** (sign-ready pack):  
  `/demo_dpi_2025-11/output/trust_bundle_2025-11.json`

- **Merkle summary over payouts** (`merkle_payouts.v1`):  
  `/proofs/merkle_payouts_2025-11.json`

- **Payout hashchain** (`chunk=1000`):  
  `/proofs/hashchain_dpi_payouts_2025-11__chunk1000.txt`

The Trust Bundle declares:

- the payouts NDJSON
- the Merkle summary over payouts
- the trust summary report
- the provider-level trust CSV

all under the CROVIA-ID shown above.

---

### 5.3 Verifying the Trust Bundle offline

From a fresh clone of `crovia-core`:

    cd /opt/crovia
    source .venv/bin/activate

    python3 trust_bundle_validator.py \
      --bundle demo_dpi_2025-11/output/trust_bundle_2025-11.json

You should see a final line similar to:

    [RESULT] Bundle OK: all declared artifacts match size and sha256.

At that point, the CROVIA-ID:

    CROVIA-ID: CTB-2025-11-HF------8559 sha256=9d481b8f38f58be7

is a compact, hash-anchored identifier for this whole settlement state and can
be safely referenced from contracts via the **Crovia Floor Clause**.

