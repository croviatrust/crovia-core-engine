# CROVIA — Quickstart Proof (60 seconds)

This is a real, verifiable end-to-end proof using only the open-core CLI.

No SaaS.
No credentials.
No hidden services.

---

## What this proves

In less than one minute, you will see that Crovia can:

1) validate attribution receipts
2) generate AI Act–style compliance artifacts
3) compute payouts
4) build a trust bundle
5) cryptographically sign it
6) bind it to a hash-chain
7) explain the evidence structure

---

## Prerequisites

python3 --version   # Python ≥ 3.10  
pip install crovia  # or editable install from repo

---

## Step 1 — Validate receipts

crovia check data/royalty_demo_2025-11.ndjson

Expected output:

- Health = A
- compliance summary (.md)
- compliance gaps (.csv)
- compliance pack (.json)

---

## Step 2 — Refine (optional cleanup)

crovia refine data/royalty_demo_2025-11.ndjson \
  --out data/royalty_demo_2025-11.refined.ndjson

---

## Step 3 — Compute payouts

crovia pay data/royalty_demo_2025-11.refined.ndjson \
  --period 2025-11 \
  --budget 1000

Artifacts generated:

- payouts_2025-11.ndjson
- payouts_2025-11.csv
- charts/ (ignored by git)

---

## Step 4 — Build trust bundle

crovia bundle \
  --receipts data/royalty_demo_2025-11.refined.ndjson \
  --payouts payouts_2025-11.ndjson

Output:

- crovia_trust_bundle.json

---

## Step 5 — Generate hashchain

crovia trace data/royalty_demo_2025-11.refined.ndjson \
  --out proofs/hashchain_demo.txt

---

## Step 6 — Attach hashchain to bundle

python3 tools/attach_hashchain_to_bundle.py \
  --bundle crovia_trust_bundle.json \
  --hashchain proofs/hashchain_demo.txt \
  --out crovia_trust_bundle.with_hashchain.json

---

## Step 7 — Sign the bundle

export CROVIA_HMAC_KEY="demo-key"  
crovia sign crovia_trust_bundle.with_hashchain.json

---

## Step 8 — Explain the evidence

crovia explain crovia_trust_bundle.with_hashchain.signed.json

Expected signals:

- signature present
- hashchain bound
- artifacts linked
- schema: crovia_trust_bundle.v1

---

## What you are looking at

You are not seeing:

- a dashboard
- a promise
- a PDF

You are seeing machine-verifiable evidence.

Crovia is not a product.
It is a receipt engine.
