# CROVIA
## Evidence & Trust Infrastructure for AI Training Data

Crovia is not a compliance tool.
It is an evidence infrastructure for how AI systems use data.

If an AI model makes money using data,
there should be receipts.
And those receipts should be auditable by anyone.

That is Crovia.

---

## What Crovia Is

Crovia is an open-core infrastructure that turns AI training data signals into:

- verifiable receipts
- trust metrics
- payout simulations
- cryptographic proofs
- audit-ready evidence packs

It is designed to operate globally, across:

- research
- commercial AI
- open datasets
- enterprise pipelines
- regulators and auditors

The EU AI Act is one of many standards Crovia can support —
it is not the reason Crovia exists.

---

## What This Repository Contains (Open Core)

This repository hosts the public, auditable core of Crovia.

It allows anyone to:

- inspect how receipts are structured
- verify schemas and invariants
- reproduce trust and payout calculations
- generate cryptographic evidence
- audit outputs without trusting a black box

### Included in the Open Core

Receipts & Schemas
- spider_receipt.v1
- royalty_receipt.v1
- payouts.v1
- trust_bundle.v1

Validation & QA
- crovia_validate.py
- schema correctness
- share ≈ 1.0 checks
- rank & consistency checks

Trust & Payout Engine (Deterministic)
- trust aggregation
- payout simulation
- Crovian Floors v1.1

Evidence & Proofs
- SHA-256 hash-chains
- Merkle payout trees
- Trust Bundles
- CEP (CROVIA Evidence Protocol)

CLI
- crovia (open CLI)
- c-line (demo orchestrator)

Everything here is transparent, reproducible, and auditable by design.

---

## What This Repository Does NOT Contain

This repository intentionally does not include:

- real attribution algorithms
- settlement logic
- billing & contracts
- enterprise integrations
- private scoring models
- DSSE-Pro or Sentinel-Pro engines

Those components live in the Crovia PRO Engine, which is private.

This separation is deliberate:

Open Core → trust & verification  
PRO Engine → business & settlement  

---

## Crovia Spider

Crovia Spider extracts forensic evidence from datasets that are already known
to be used in AI training.

“If it’s already in open training datasets,
it already has a Crovia receipt.”

Crovia Spider:
- does not crawl the web
- does not ingest new content
- only structures existing metadata into verifiable receipts

Artifacts produced:
- spider_receipt.v1 NDJSON logs
- provenance hints
- coverage reports

Specification:
docs/CROVIA_SPIDER_RECEIPT_v1.md

---

## C-LINE (Demo Orchestrator)

C-LINE is the open demo CLI that runs the entire Crovia evidence pipeline.

Command:

python tools/c_line.py demo

It automatically:
- validates receipts
- computes trust metrics
- simulates payouts
- computes Crovian Floors
- generates charts
- builds hash-chains
- generates AI-style documentation
- packages everything into a single evidence ZIP

This is a reproducible evidence pipeline, not a SaaS demo.

---

## CEP — CROVIA Evidence Protocol

CEP.v1 is a compact, verifiable evidence block designed for:
- model cards
- research papers
- audit packs
- dataset documentation

It includes:
- cryptographic hashes
- trust metrics
- payout summaries
- hash-chain roots
- provenance metadata

Specification:
docs/CROVIA_CEP_v1.md

---

## Global Scope

Crovia is not limited to:
- the European Union
- the AI Act
- compliance-only workflows

It is built for:
- global AI training pipelines
- open science
- enterprise governance
- cross-border audits

Regulatory frameworks consume Crovia evidence —
they do not define it.

---

## Project Status

Open Core — stable, auditable, reproducible  
Demo-grade data — synthetic or partial  
Evidence-first — infrastructure, not a product  

Crovia is a foundation layer.

---

## Licensing

Apache License 2.0

You may:
- use Crovia commercially or academically
- modify and redistribute it
- integrate it into closed or open systems

See the LICENSE and NOTICE files for details.

[![License: Apache-2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)


