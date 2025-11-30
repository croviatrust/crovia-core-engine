# CROVIA – Sandbox preview

Upload a small royalty receipts NDJSON file (demo limit ≈ 2 MB) and see a **payout preview** computed by the CROVIA engine.

All sandbox runs use the same trust & payout logic as the main engine, but results are temporary and meant for experimentation only.

---

## 1. What you need

You need an **NDJSON** file where each line is a `royalty_receipt.v1` record.

Each record should at least contain:

- a timestamp  
- a model identifier  
- a segment (e.g. `train`, `eval`, `inference`)  
- a list of provider IDs  
- a numeric score or weight  

Example (one line, tutto su una riga nel file reale):

{"timestamp":"2025-11-01T00:00:00","model_id":"demo-llm","segment":"train","providers":["provider_A","provider_B"],"score":0.81}

If the format is wrong, the sandbox will return a QA error instead of payouts.

---

## 2. How the sandbox works

You upload your NDJSON file and choose:

- a budget in EUR  
- a period label (e.g. `2025-11`)  

CROVIA runs a light version of the engine:

- schema & business QA checks  
- aggregation of receipts by provider  
- computation of provisional trust metrics  
- payout preview from the budget you specified  

You receive:

- a table with providers and their preview payouts  
- a short QA status (OK / warnings / errors)  
- links to download the preview as CSV / JSON (where available)  

Some heavy steps (full hashchain, full AI-Act pack) may be disabled in the sandbox to keep runs fast.

---

## 3. Try it with a sample file

If you want to see the engine in action before using your own data, you can start with a small synthetic file:

- **Sample file**: `royalty_demo_sandbox_300.ndjson`  
- **Public URL**: `https://croviatrust.com/static/royalty_demo_sandbox_300.ndjson`  
- **Size**: ~300 receipts, 4 synthetic providers  

Suggested steps:

1. Download the sample file from the URL above.  
2. Upload it as-is in the sandbox form.  
3. Use a budget of `1,000,000` EUR and period `2025-11`.  

You should see:

- payouts split across four demo providers  
- reasonable concentration metrics  
- QA status = OK  

This is the same configuration used in the public 2025-11 demo period.

---

## 4. Limits of the public sandbox

- File size is capped (≈ 2 MB, a few thousand receipts).  
- Runs are not stored long-term and do not represent real payouts.  
- The sandbox is not a contractual or financial commitment.  
- Configuration may change over time as we evolve the profile.  

For production use, CROVIA can be integrated directly into your training and serving pipelines, with dedicated Trust Bundles and signed governance reports per period.
