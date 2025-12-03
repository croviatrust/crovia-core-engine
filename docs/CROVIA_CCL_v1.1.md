# CROVIA – CCL v1.1 (Crovian Compatibility Layer)

`CCL` (Crovian Compatibility Layer) is a tiny JSON schema designed to:

- describe an AI artifact (model, dataset, RAG index, API, tool) in a **minimal** way  
- let anyone declare the **role** and **provenance** of their artifacts  
- be readable by both **humans** and tooling such as **CROVIA Trust / Bundles**

The goal is a small JSON file, easy to generate in 5–10 lines of code,
that can exist even without using CROVIA.

---

## 1. Overall shape

A `*.ccl.json` file has this general structure:

    {
      "ccl_version": "1.1",
      "provider_hint": "mycompany",
      "artifact_type": "model",
      "shard_shape": "embedding",
      "license_scope": "train",
      "usage_scope": "public_api",

      "roles": { ... },        // optional
      "trust_hints": { ... },  // optional
      "links": { ... },        // optional

      "fingerprint": "sha256:..."   // recommended
    }

All fields are meant to be:

- short strings  
- small enums  
- 0–1 numeric values  
- easy to fill by hand or from code  

---

## 2. Core fields (required)

### `ccl_version` (string)

Version of the CCL schema.  
For this spec: `"1.1"`.

Used to handle future extensions without breaking parsing.

---

### `provider_hint` (string)

Short label (snake-case or lowercase) identifying who controls the artifact.

Examples:

- `"openai"`, `"meta"`, `"google"`  
- `"hf_community"`  
- `"mycompany"`  
- `"university_lab"`

This is **not** a legal identifier; it is a human/technical hint.

---

### `artifact_type` (enum string)

Type of artifact described by the CCL.

Suggested values:

- `"model"` – model (LLM, vision, embedding, adapter, LoRA, …)  
- `"dataset"` – dataset or data collection  
- `"rag-index"` – retrieval index (vector index, BM25, hybrid, …)  
- `"api"` – inference endpoint or service  
- `"tool"` – external tool (function, plugin, agent, …)  
- `"other"` – anything else / unclassified  

---

### `shard_shape` (enum string)

Main shape of the internal “units” that contribute to the model or index.

Suggested values:

- `"embedding"` – dense/sparse vectors  
- `"token"` – text tokens  
- `"chunk"` – documents / paragraphs / records  
- `"other"` – other / not relevant  

---

### `license_scope` (enum string)

How the data or model can be used in general, with respect to its main license.

Suggested values:

- `"train"` – allowed for training  
- `"rag"` – allowed for retrieval / context injection  
- `"eval"` – evaluation / benchmarking only  
- `"unknown"` – unclear / mixed / not declared  

This does **not** replace a full license; it is a summary.

---

### `usage_scope` (enum string)

How the artifact is used in practice.

Suggested values:

- `"public_api"` – exposed to third parties (SaaS, public API)  
- `"internal"` – internal use only  
- `"research"` – research / experimental  
- `"unknown"` – not specified  

---

### `fingerprint` (string, recommended)

Stable identifier for the main content (data, weights, config).

Suggested format:

- `"sha256:<hex>"` – SHA256 hash of canonical JSON, model weights, or a bundle.

Example:

    "fingerprint": "sha256:34af8c7b2e0c1b..."

This is not a cryptographic signature. It is a technical anchor
for linking CCLs, bundles, models and datasets.

---

## 3. Optional section: `trust_hints`

A block of quality / governance hints, all optional.

Example:

    "trust_hints": {
      "dp": "yes",
      "stability": 0.91,
      "uncertainty": 0.12
    }

Suggested fields:

- `dp` (string)  
  - `"yes"` | `"no"` | `"unknown"`  
  - Indicates whether Differential Privacy has been applied.

- `stability` (number, 0–1)  
  (Even rough) estimate of how stable the model is under small
  perturbations of data or random seeds.

- `uncertainty` (number, 0–1)  
  Synthetic uncertainty measure (e.g. based on ensemble variance,
  average entropy, etc.).

If not available: omit.

These values are hints: not binding, but useful for audit,
ranking or risk filters.

---

## 4. Optional section: `roles`

Describes the role of the artifact in the value chain.  
This is one of the distinctive parts of CCL.

Example:

    "roles": {
      "data_role": "producer",
      "model_role": "backbone",
      "gateway_role": "inference"
    }

### `data_role` (enum string)

Role with respect to data:

- `"producer"` – produces original data  
- `"mixer"` – mixes data from multiple sources  
- `"annotator"` – adds labels / annotations  
- `"filter"` – filters / cleans / deduplicates  
- `"unknown"`  

### `model_role` (enum string)

Role of the model in the broader pipeline:

- `"backbone"` – main model  
- `"adapter"` – adapter, head, routing component  
- `"lora"` – LoRA / light fine-tune  
- `"critic"` – evaluation / reward / guardrail model  
- `"tool"` – auxiliary ML tool  
- `"unknown"`  

### `gateway_role` (enum string)

Role in exposure / orchestration:

- `"training"` – primarily used for training  
- `"inference"` – primarily used to produce outputs  
- `"broker"` – gateway to other models / APIs  
- `"cache"` – stores results (e.g. RAG cache)  
- `"unknown"`  

All fields in `roles` are optional.  
You can set only the ones that make sense.

---

## 5. Optional section: `links`

Used to connect multiple CCLs and build a simple provenance graph
independent of any engine.

Example:

    "links": {
      "upstream": [
        "sha256:dataset_ccl_abc123...",
        "sha256:base_model_ccl_def456..."
      ],
      "downstream_hint": null,
      "bundle_ref": null
    }

Fields:

- `upstream` (array of strings)  
  List of fingerprints / IDs of other CCLs this artifact descends from
  (e.g. source datasets, base model, RAG indexes).

- `downstream_hint` (string | null)  
  Generic hint for tools that generate many children  
  (e.g. “this API may produce child CCLs for each fine-tuned model”).

- `bundle_ref` (string | null)  
  Optional.  
  Can be a URL or identifier of a CROVIA Trust Bundle, if one exists.

---

## 6. Examples

### 6.1 Model served as a public API

    {
      "ccl_version": "1.1",
      "provider_hint": "mycompany",
      "artifact_type": "model",
      "shard_shape": "embedding",
      "license_scope": "train",
      "usage_scope": "public_api",

      "roles": {
        "data_role": "mixer",
        "model_role": "backbone",
        "gateway_role": "inference"
      },

      "trust_hints": {
        "dp": "no",
        "stability": 0.87,
        "uncertainty": 0.20
      },

      "links": {
        "upstream": [
          "sha256:dataset_ccl_abc123...",
          "sha256:base_model_ccl_def456..."
        ],
        "downstream_hint": null,
        "bundle_ref": null
      },

      "fingerprint": "sha256:model_weights_789xyz..."
    }

---

### 6.2 Dataset for internal RAG

    {
      "ccl_version": "1.1",
      "provider_hint": "university_lab",
      "artifact_type": "dataset",
      "shard_shape": "chunk",
      "license_scope": "rag",
      "usage_scope": "internal",

      "roles": {
        "data_role": "producer"
      },

      "trust_hints": {
        "dp": "unknown"
      },

      "links": {
        "upstream": [],
        "downstream_hint": "used to build multiple RAG indices for internal agents",
        "bundle_ref": null
      },

      "fingerprint": "sha256:dataset_v3_123abc..."
    }

---

## 7. Implementation guidelines

The CCL file can be:

- stored as `artifact_name.ccl.json`  
- embedded into other JSONs (e.g. in a `crovian_compat` field)  
- served via API (e.g. `GET /ccl`)  

Parsers should:

- accept extra fields (forward–compatible)  
- validate only the main enums  
- treat missing optional fields as null / absent, not as errors  

Simplicity is a core property:

- no mandatory cryptographic signatures  
- no hard dependency on CROVIA  
- no complex log schemas required  

---

## 8. Integration with CROVIA

CROVIA can use a CCL in three main ways:

### 1. Discovery

Quickly identify relevant artifacts (models, datasets, RAG, tools).

### 2. Provenance

Use `roles` + `links.upstream` to build a provenance graph suitable
for bundles, audit and AI Act workflows.

### 3. Bridge to Trust Bundles

Use `fingerprint` and `bundle_ref` to connect:

- CCL → Trust Bundle  
- Trust Bundle → payouts / compliance  

CCL remains an independent layer: providers can adopt it even
without using CROVIA, and still get value for audit and governance.
