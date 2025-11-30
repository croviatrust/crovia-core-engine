# CROVIA – AI Training Data Trust & Payout Engine

CROVIA turns raw attribution logs (“royalty receipts”) into:

- monthly payouts per provider from a fixed EUR budget  
- trust and priority scores per provider  
- a signable Trust Bundle aligned with EU AI Act record-keeping principles and compatible with major AI governance frameworks  

All demo data exposed on croviatrust.com are synthetic and do **not** represent real payments.

---

## 1. Problem CROVIA solves

Modern AI models are trained on data coming from many providers and sources.  
Companies need to:

- track who contributed what to a model  
- calculate fair payouts from a fixed budget  
- assign trust / risk bands per provider  
- keep audit-ready evidence for regulators, partners and internal governance  

Spreadsheets and ad-hoc scripts do not scale and are hard to audit.

CROVIA provides a structured, machine-readable contract between:

- the engine that trains and serves models, and  
- the ecosystem of data providers, regulators and auditors.

---

## 2. Core concepts

### 2.1 Royalty receipts (attribution logs)

A *royalty receipt* is a compact JSON record saying, in essence:

> “this model output was influenced by these providers, with these weights.”

Receipts are written as newline-delimited JSON (NDJSON) so they can be streamed, sharded and stored efficiently.

Typical fields include:

- timestamp  
- model identifier  
- segment (train / eval / inference)  
- list of provider IDs  
- contribution weight or score  

### 2.2 Trust and priority

From all receipts in a given period (for example `2025-11`), CROVIA computes:

- how often each provider appears in **high-value outputs**  
- a **trust score** per provider (0–1)  
- a **risk profile** and a **priority band** (HIGH / MED / LOW) combining contribution and risk  

These signals drive both payouts and future negotiation priorities.

### 2.3 Payouts

Given a fixed monthly EUR budget, CROVIA allocates payouts per provider according to:

- observed contribution in the receipts  
- policy parameters (caps, thresholds, exclusions)  
- concentration targets and governance constraints  

The result is a payout table that can be exported as CSV / NDJSON and linked to downstream payment systems.

### 2.4 Crovian Floors and coverage

A distinctive feature of CROVIA is the concept of **Crovian Floor**.

For each provider the engine estimates a **coverage bound**: a conservative lower bound of

> “how much this provider really covers the model behaviour”.

Using this bound, policy parameters and the total budget, CROVIA derives a **minimum payout floor** for eligible providers.  
Floors can then be used in contracts, revenue-sharing agreements and compliance reviews.

### 2.5 Trust Bundle

For each period, CROVIA emits a signed **Trust Bundle JSON** that includes:

- pointers and checksums for main artifacts (payout tables, charts, hashchain)  
- trust / priority tables and coverage bounds  
- assumptions and notes (coverage limits, known gaps, excluded providers)  
- governance metadata (who ran the engine, when, with which profile)  

The bundle is designed to be archived, shared with providers, or attached to internal model cards as evidence.

---

## 3. What you see on croviatrust.com

The public website currently exposes a **demo configuration**.

### 3.1 Dashboard – period view

The dashboard shows, for the latest available period:

- top providers by payout and share of budget  
- payout charts (Top-10 providers, cumulative payout curve)  
- basic concentration metrics (for example HHI and Gini)  
- a button to download the Trust Bundle JSON for that period  

All numbers are synthetic and for illustration only.

### 3.2 Sandbox – upload your own receipts

The **Sandbox** lets you upload a small NDJSON file with your own receipts (demo limit ≈ 2 MB) and get:

- a temporary **payout preview** per provider  
- basic QA feedback if the format is wrong  
- a view of how the CROVIA pipeline behaves on a private sample  

Sandbox runs are meant for experimentation only; they are not stored long-term and do not create contractual obligations.

### 3.3 CLI reproducibility

The same demo period exposed on the website can be reproduced from the CLI using the open profile and tools described in the internal documentation.  
This makes it possible to verify the pipeline end-to-end on a private environment.

---

## 4. CROVIA profile and implementation layers

CROVIA is split into three layers:

- **M0 – Open Profile**  
  The data profile and examples (receipts, payouts, Trust Bundles).  
  Anyone can emit or consume objects that follow this profile.

- **M1 – Lite tools**  
  Simple validators and integrity checkers that help partners adopt the profile and verify basic properties.

- **M2 – Enterprise Engine**  
  The full CROVIA engine (trust, payouts, floors, compliance pack, charts, hashchain, signatures), offered under commercial terms or as a managed service.

Public documentation focuses on M0 (profile) and on the observable behaviour of the system.  
The internal implementation of M2 can evolve without breaking the contract with data providers.

---

## 5. How to start a pilot

A typical pilot path is:

1. Define a test period and total EUR budget.  
2. Export a sample of royalty receipts in the CROVIA profile.  
3. Run a sandbox or private instance of the engine.  
4. Review payouts, trust bands, floors and the Trust Bundle with:  
   - internal stakeholders  
   - selected data providers  
   - legal / compliance teams  
5. If results are acceptable, move to regular periodic runs and connect the outputs to real payment systems.

CROVIA is designed to keep the **profile open** and the **engine evolvable**, so organisations can adopt a transparent, auditable standard for AI-training data payouts while retaining flexibility in their internal implementations.

---

## 6. Contact

For enterprise or partnership enquiries you can reach us at  
**info@croviatrust.com**
