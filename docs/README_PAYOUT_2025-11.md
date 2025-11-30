# CROVIA – Enterprise engine demo (period 2025-11)

This note documents the public CROVIA demo for period **2025-11**.  
All values are computed from **synthetic royalty receipts** and do not
represent real contracts or real providers.

The goal is to show how the **CROVIA enterprise engine** turns attribution
logs (“royalty receipts”) into:

- monthly **payouts per provider**  
- **concentration metrics** (how the budget is distributed)  
- a signable **Trust Bundle JSON** suitable for audit and governance  

---

## 1. Executive summary

For this synthetic demo run:

- **Period:** 2025-11  
- **Total outputs (receipts) considered:** 3000  
- **Unique providers paid:** 4  
- **Total budget (EUR):** 1,000,000.00  
- **Sum of payouts:** 1,000,000.00  

Concentration metrics (synthetic run):

- **HHI ≈ 0.3792**  
- **Gini ≈ 0.3992**  

These values indicate a **moderately concentrated** distribution:  
not “winner-takes-all”, but not fully egalitarian either.

---

## 2. How to read the charts

For period **2025-11** the engine produces two reference charts:

1. **Top-10 providers by payout**  
   Shows how much each provider receives in absolute EUR from the
   configured budget.

2. **Cumulative payout curve**  
   Shows how quickly the budget accumulates as you add providers in
   order of payout (from highest to lowest).

### Interpretation (governance view)

- A **very steep** curve and very high HHI / Gini means that a tiny
  number of providers captures almost all the budget.
- A **smoother** curve and moderate concentration metrics means that
  the budget is more evenly distributed across providers.

In this synthetic profile (2025-11):

- the curve is not perfectly flat (some providers are clearly ahead);  
- but it is not extremely steep either, which is often desirable in
  negotiated data ecosystems.

---

## 3. What the public charts represent

On this page you see the same two charts that are also shipped inside
the Trust Bundle for this period:

- **“Top-10 providers by payout – period 2025-11”**  
- **“Cumulative payout – quota cumulativa vs provider”**

Both charts are derived from the same payout table used for the demo
run. They allow governance, audit and risk teams to:

- check how concentrated the budget is;  
- compare different trust profiles or different periods at a glance;  
- spot potential outliers (providers that capture a very large share).  

The **HHI ≈ 0.3792** and **Gini ≈ 0.3992** values shown on this page
are computed directly from the payout distribution for this demo.

---

## 4. Reproducing this demo from the CLI

An engineer can reproduce the **2025-11** demo on any server that has
the CROVIA engine installed.

```bash
cd /opt/crovia
source .venv/bin/activate

python3 run_period.py \
  --period 2025-11 \
  --eur-total 1000000 \
  --receipts data/royalty_synthetic_2025-11.ndjson \
  --min-appear 1
```

This command regenerates all artifacts for the demo period:

- **Payout files**
  - `data/payouts_2025-11.csv`
  - `data/payouts_2025-11.ndjson`

- **Floor and assumptions files**
  - `data/floors_2025-11.json`
  - `data/assumptions_2025-11.json`

- **Charts**
  - `charts/payout_top10_2025-11.png`
  - `charts/payout_cumulative_2025-11.png`

- **Trust Bundle JSON**
  - `trust_bundle_2025-11.json`

From there, governance and audit teams can:

- inspect the payout distribution;  
- verify that totals match the configured EUR budget;  
- review assumptions, coverage bounds and compliance evidence.  


## Charts (2025-11)

![Top10](charts/payout_top10_2025-11.png)
![Cumulative](charts/payout_cumulative_2025-11.png)

**Concentration**
- HHI: 0.0003
- Gini: 0.0003

