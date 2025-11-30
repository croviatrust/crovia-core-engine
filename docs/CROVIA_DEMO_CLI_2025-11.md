# CROVIA demo run – Period 2025-11 (synthetic)

This document describes how to reproduce the public demo period 2025-11
on the CROVIA server.

All paths are relative to `/opt/crovia`.

---

## 1. Environment

Commands to activate the virtualenv:

    cd /opt/crovia
    source .venv/bin/activate

---

## 2. Generate synthetic receipts

Input events (synthetic log) are stored in:

- data/events_synthetic_2025-11.ndjson

Convert them to royalty_receipt.v1 records:

    python3 events_to_royalty.py \
      --input data/events_synthetic_2025-11.ndjson \
      --out   data/royalty_synthetic_2025-11.ndjson

Expected log:

- "Read 3000 events, wrote 3000 royalty_receipt.v1 records".

---

## 3. Full CROVIA engine run for 2025-11

Run the full period pipeline on the synthetic receipts:

    python3 run_period.py \
      --period 2025-11 \
      --eur-total 1000000 \
      --receipts data/royalty_synthetic_2025-11.ndjson \
      --min-appear 1

This step performs:

- schema & business QA (qa_receipts.py, crovia_validate.py)
- trust & attribution (crovia_trust.py)
- payouts + charts (payouts_from_royalties.py, make_payout_charts.py)
- AI-Act compliance pack (compliance_ai_act.py)
- hashchain proof (hashchain_writer.py, verify_hashchain.py)
- trust bundle and floors (make_trust_bundle.py, crovia_floor.py, augment_trust_bundle.py)

---

## 4. Demo coverage bounds (optional override)

For the public demo we use explicit coverage bounds
for the four synthetic providers.

Create the CSV:

    cat > data/coverage_bounds_2025-11.csv << 'CSV'
    provider_id,coverage_bound
    news_corp,0.70
    research_lab,0.50
    community_forum,0.25
    open_web,0.05
    CSV

Recompute floors and update the trust bundle:

    python3 crovia_floor.py \
      --period 2025-11 \
      --eur-total 1000000 \
      --coverage-csv data/coverage_bounds_2025-11.csv

    python3 augment_trust_bundle.py --period 2025-11

Expected:

- floors_2025-11.json with a max floor around 200k EUR.
- trust_bundle_2025-11.json updated with coverage & floor info.

---

## 5. Sanity check: floors vs payouts

Verify that demo payouts respect the floors:

    python3 check_floors_vs_payouts.py --period 2025-11
    cat data/check_floors_vs_payouts_2025-11.csv

Expected:

- All providers have status = OK or NO_PAYOUT.
- No provider with BELOW_FLOOR or BELOW_FLOOR_NOPAYOUT.

---

## 6. Public artifacts used by croviatrust.com

Main outputs for period 2025-11:

- trust_summary.md
- README_PAYOUT_2025-11.md
- charts/payout_top10_2025-11.png
- charts/payout_cumulative_2025-11.png
- data/floors_2025-11.json
- trust_bundle_2025-11.json

These files are read by the dashboard and documentation pages
on croviatrust.com to show:

- top providers by trust,
- payouts & concentration charts,
- the signable Trust Bundle JSON for the demo period.
