# CROVIA – Trust & Payout summary (demo period 2025-11)

This note documents the public CROVIA demo for period **2025-11**.
All values are computed from **synthetic royalty receipts** and do not
represent real contracts or real providers.

The goal of this page is to show, in a readable way, what an
audit / governance view looks like when CROVIA runs on a fixed EUR
budget for a period.

---

## 1. What this demo shows

For the selected period you have:

- a **trust & priority table per provider** derived from royalty receipts;
- a view of **how concentrated the budget is** (Top-10 bar chart and cumulative curve);
- a **signable Trust Bundle JSON** that can be archived or shared with third parties.

Internally all these artefacts come from a single engine run on:

- a fixed **EUR budget**; and
- a receipts file that follows the **CROVIA profile**.

---

## 2. Reading the concentration charts

The Trust Bundle for 2025-11 ships with two reference charts:

1. **Top-10 providers by payout**  
   Shows how much each of the top providers receives in absolute EUR.

2. **Cumulative payout curve**  
   Shows how quickly the budget accumulates as you add providers in order of payout.

Interpretation:

- a **very steep** curve and very high HHI / Gini → a tiny number of providers captures most of the budget;
- a **smoother** curve and moderate concentration metrics → the budget is more evenly distributed.

For this synthetic run:

- **HHI ≈ 0.3792**
- **Gini ≈ 0.3992**

These values indicate a **moderately concentrated** distribution:
not “winner-takes-all”, but not fully egalitarian either.

---

## 3. What is included in `trust_bundle_2025-11.json`

The JSON Trust Bundle for this period contains pointers and checksums for:

- payout files per provider (`data/payouts_2025-11.csv`, `data/payouts_2025-11.ndjson`);
- the **assumptions JSON** (`data/assumptions_2025-11.json`);
- **Crovian Floors & coverage bounds** (`data/floors_2025-11.json`);
- the **AI-Act compliance pack** and related summaries;
- the **hashchain integrity proof** for the receipts file;
- governance metadata (who ran the engine, when, with which profile).

The bundle is designed to be:

- archived as long-term evidence;
- shared with providers, auditors and regulators;
- attached to internal model cards and compliance documentation.

---

## 4. Reproducing the demo

The CLI recipe for reproducing this run is documented in:

- `docs/README_PAYOUT_2025-11.md`

and can be executed on any server where the CROVIA engine is installed.
