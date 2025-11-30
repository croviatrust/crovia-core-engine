# CROVIA – AI Training Data Trust Profile M0 (Open Profile)

This document describes the **CROVIA Open Profile (M0)** for AI training data.
The profile defines:

- a minimal, machine-readable format for **attribution logs** (“royalty receipts”);
- how to derive **payout tables** from those logs;
- how to package evidence into a sign-ready **Trust Bundle JSON**.

The goal of M0 is to be **open and portable**: any organisation can emit or consume
objects following this profile, independently of the internal engine used.

All examples in this document are synthetic and for illustration only.

---

## 1. Roles and scope

The profile is designed for three main roles:

- **Data providers** – organisations contributing data (datasets, corpora, streams).
- **Model operators** – organisations training / evaluating AI models on that data.
- **Auditors & regulators** – parties that need verifiable evidence of
  training-data usage and payouts.

M0 covers **record-keeping and traceability**, not payment rails.  
How money actually moves (bank transfers, crypto, internal ledger) is out of scope.

---

## 2. Royalty receipts (`royalty_receipt.v1`)

### 2.1. Format

Royalty receipts are written as **newline-delimited JSON (NDJSON)**:

- one JSON object per line;
- UTF-8 encoded;
- each object declares itself with `"schema": "royalty_receipt.v1"`.

Files can be sharded or chunked arbitrarily, as long as **order is stable**
inside each file (for hash-chaining).

### 2.2. Required fields

A minimal `royalty_receipt.v1` object MUST contain:

- `schema` (string) – must be `"royalty_receipt.v1"`.
- `timestamp` (string) – ISO-8601 UTC timestamp of the event.
- `period` (string) – aggregation period, typically `"YYYY-MM"`.
- `model_id` (string) – identifier of the model or run.
- `segment` (string) – `"train"`, `"eval"` or `"inference"` (profile-level).
- `providers` (array of objects) – list of contributors to this output:
  - `provider_id` (string) – id of the data provider.
  - `weight` (number, >= 0) – contribution weight for this provider.
- `weight_total` (number, > 0) – sum of all `providers[*].weight` for the event.

The following fields are **RECOMMENDED** but optional for M0:

- `shard_id` (string) – logical shard or log source.
- `output_id` (string) – identifier of the model output.
- `tags` (object) – free-form key/value annotations (e.g. dataset labels, license).

Additional fields MAY be added as long as they do not change the meaning of
the required fields.

### 2.3. Example receipt (single line)

```json
{
  "schema": "royalty_receipt.v1",
  "timestamp": "2025-11-05T12:34:56Z",
  "period": "2025-11",
  "model_id": "news_summariser_v4",
  "segment": "train",
  "providers": [
    {"provider_id": "news_corp", "weight": 0.7},
    {"provider_id": "research_lab", "weight": 0.3}
  ],
  "weight_total": 1.0,
  "shard_id": "train_shard_01"
}
```

---

## 3. Payout tables (`payouts.v1`)

Payouts describe how a fixed budget is allocated to providers for a given
period, based on the royalty receipts and the active policy.

### 3.1. Format

Payouts MAY be represented as:

- **CSV** (human-friendly, tabular), and/or  
- **NDJSON** (with `"schema": "payouts.v1"`).

The semantics are identical; only the encoding changes.

### 3.2. Required columns / fields

For each `(period, provider_id)` pair, a payout record MUST contain:

- `schema` (string, NDJSON only) – `"payouts.v1"`.
- `period` (string) – same `"YYYY-MM"` period used in receipts.
- `provider_id` (string).
- `amount` (number, >= 0) – payout in the configured currency.
- `currency` (string, ISO-4217, e.g. `"EUR"`).
- `share` (number, 0–1) – provider share of the total period budget.
- `eligible` (boolean) – whether the provider is eligible for payment under
  the active policy.

**RECOMMENDED** extra fields:

- `band` (string) – trust / risk band, e.g. `"LOW"`, `"MED"`, `"HIGH"`.
- `notes` (string) – short free-form explanation (caps, exclusions, etc.).

### 3.3. Example payout row (CSV)

```csv
period,provider_id,amount,currency,share,eligible,band
2025-11,news_corp,483000.00,EUR,0.483,true,MED
```

---

## 4. Trust Bundle (`trust_bundle.v1`)

The Trust Bundle JSON is the main artefact produced at the end of a run.  
It is designed to be sign-ready (for digital signatures) and to aggregate:

- pointers and hashes for all key artefacts;
- summary statistics;
- governance statements and attestations.

### 4.1. Top-level structure

A `trust_bundle.v1` object MUST contain at least:

- `schema` – `"crovia_trust_bundle.v1"`.
- `period` – `"YYYY-MM"`.
- `created_at` – ISO-8601 UTC timestamp (seconds resolution or better).
- `bundle_id` – UUID or equivalent unique identifier.
- `producer` – identifier of the engine instance (e.g. hostname / tenant).
- `version` – semantic version of the bundle format (e.g. `"1.0.0"`).
- `inputs` – description of input logs and their hashes.
- `artifacts` – registry of derived artefacts (payouts, reports, charts, floors).
- `stats` – aggregated statistics for royalties and payouts.
- `governance` – policy, profile label, scope, engine info.
- `attestations` – optional list of signatures or human statements.

### 4.2. Artifact entries

Each entry under `artifacts` MUST be an object with:

- `path` – relative path from the bundle location (POSIX style).
- `bytes` – file size in bytes.
- `sha256` – hex-encoded SHA-256 digest of the file contents.

Example:

```json
"payout_csv": {
  "path": "data/payouts_2025-11.csv",
  "bytes": 300,
  "sha256": "e03954dbab29f0425847e7bb2966b37f27516480444ad60829bb07751fe7b12b"
}
```

The same convention is used for:

- `payout_ndjson`
- `trust_providers_csv`
- `validate_report_md`
- `compliance_pack_json`
- `chart_top10_png`
- `chart_cumulative_png`
- `hashchain_txt`
- `floors_json`

and any additional artefact an implementation may add.

### 4.3. Governance section (M0)

For M0, the `governance` section SHOULD include:

- `profile_label` – human-readable name, e.g.  
  `"CROVIA – AI Training Data Trust Profile v1.0"`.
- `policy_uri` – URL where the applicable profile / policy is documented,  
  e.g. `https://croviatrust.com/standard`.
- `jurisdictions` – list of targeted regulatory scopes  
  (e.g. EU AI Act record-keeping).
- `scope` – object describing:
  - `period` – same as top level.
  - `objects` – list of schema names covered  
    (e.g. `["royalty_receipt.v1", "payouts.v1", "trust_bundle.v1"]`).
  - `engine` – engine name and version.

`attestations` MAY include references to signatures, key IDs or separate signed
envelopes, depending on the deployment.

---

## 5. Conformance to CROVIA Profile M0

An implementation is CROVIA Profile M0-conformant if it satisfies all
the following:

### 5.1. Receipts

Emits training / eval / inference logs as NDJSON where each object
conforms to `royalty_receipt.v1` as defined in §2.

### 5.2. Payouts

Computes payouts per `(period, provider_id)` and exposes them as CSV
and/or NDJSON conforming to §3.

### 5.3. Trust Bundle

Produces a sign-ready JSON manifest conforming to §4, with stable paths
and SHA-256 hashes for all declared artefacts.

### 5.4. Reproducibility

Given the same receipts and the same policy parameters for a period,
the engine can reproduce the same payouts and Trust Bundle, modulo
non-semantic fields (`created_at`, `bundle_id`).

The internal algorithms (how trust is computed, how floors are derived, how
policies are expressed) may evolve over time and do not affect M0
conformance, as long as the external objects respect this profile.

---

## 6. Versioning and evolution

This document describes **Profile M0 – version 1.0.0**.

Future versions MAY:

- add optional fields and artefacts;
- refine recommended practices;
- define higher layers (M1 – lite tools, M2 – enterprise engine).

Any change that would break compatibility for existing logs or bundles will
require a **major version bump** and MUST be clearly documented.

---

---

## 7. Relation to Lite Tools Pack M1

The **CROVIA Lite Tools Pack M1** provides a CLI-first toolkit that can be used
on top of Profile M0:

- receipt QA for `royalty_receipt.v1` logs  
- schema and business validation  
- AI Act record-keeping helper  
- hashchain write & verify tools  

The public documentation for M1 is available at:  
**[/lite-tools](/lite-tools)**.



For questions or proposals regarding the profile, you can contact:

`info@croviatrust.com`
