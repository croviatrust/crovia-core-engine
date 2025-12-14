# CroviaTrust

Open-core evidence & payout engine for AI training data.

Crovia turns dataset usage into:
- cryptographic receipts,
- verifiable payouts,
- and audit-ready trust bundles.

If an AI model makes money using data,
there should be a receipt.

Crovia enforces that — with boring, verifiable artifacts.

---

## What Crovia Is (and Is Not)

Crovia is not:
- a blockchain,
- a token,
- a SaaS dashboard,
- a policy document.

Crovia is:
- a CLI-first evidence engine,
- a receipt generator for AI training,
- a trust layer you can audit offline.

Everything Crovia produces is:
- JSON / NDJSON
- hash-chained
- signature-verifiable
- reproducible

---

## Canonical Demo (8 commands)

This repository contains a real, end-to-end demo.

You start with a receipts file
and end with a signed, hash-bound trust bundle.

1) Validate receipts + AI Act readiness

crovia check data/royalty_demo_2025-11.ndjson

2) Normalize / clean (demo heuristics)

crovia refine data/royalty_demo_2025-11.ndjson \
  --out data/demo.refined.ndjson

3) Compute payouts for a given period

crovia pay data/demo.refined.ndjson \
  --period 2025-11 \
  --budget 1000

4) Build a trust bundle

crovia bundle \
  --receipts data/demo.refined.ndjson \
  --payouts payouts_2025-11.ndjson

5) Sign the bundle

export CROVIA_HMAC_KEY="demo-key"
crovia sign crovia_trust_bundle.json

6) Generate a hashchain over receipts

crovia trace data/demo.refined.ndjson

7) Attach hashchain to the bundle

python3 tools/attach_hashchain_to_bundle.py \
  --bundle crovia_trust_bundle.json \
  --hashchain proofs/hashchain_demo.refined.ndjson.txt \
  --out crovia_trust_bundle.with_hashchain.json

8) Inspect evidence integrity

crovia explain crovia_trust_bundle.with_hashchain.signed.json

---

## What You Get

After these steps you have:

- validated receipts
- AI Act compliance summary
- payout computation
- cryptographically signed trust bundle
- hashchain bound to receipts
- offline-verifiable evidence

No dashboards.
No servers.
No black boxes.

---

## Why This Matters

Most AI governance talks about:

- policies,
- disclosures,
- promises.

Crovia deals in:

- receipts,
- hashes,
- signatures.

Boring systems scale.
Auditable systems become law.

---

## Open vs PRO

This repository is open-core.

Open:
- receipt schemas
- validation
- payout logic
- hashchains
- trust bundles

PRO (not in this repo):
- semantic audit (DSSE)
- Sentinel risk engine
- training-loop instrumentation (Autolog)
- trust scoring & enforcement

You can verify Crovia without trusting Crovia.

That is the point.

---

## License

Apache-2.0
