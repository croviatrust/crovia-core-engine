# Crovia Spider Receipt v1.0

- **Schema:** `spider_receipt.v1`  
- **Version:** `1.0.0`  
- **Status:** Draft  
- **Date:** 2025-12-06  

---

## 1. Overview

A `spider_receipt.v1` is the minimal unit of Crovia's awareness of a content item
that has appeared in open training corpora.

It answers the question:

> “When and how did Crovia first become aware of this content's existence in the training data ecosystem?”

This receipt does **NOT**:

- guarantee copyright status  
- verify license compliance  
- confirm actual usage in training  
- replace `royalty_receipt.v1`  

It **DOES**:

- establish content identity (`content_id`)  
- record a processing timestamp (`retrieved_at`)  
- link to a source corpus (`dataset_origin`)  
- provide licensing hints (when available)  
- connect to Crovia's temporal framework via `period`  

---

## 2. Schema

### 2.1 Full example

    {
      "schema": "spider_receipt.v1",
      "version": "1.0.0",

      "receipt_id": "sr_sha256:8f3b2a1c...",
      "content_id": "cid:url_sha256:abc123def456...",

      "source_url": "https://example.com/image.jpg",
      "retrieved_at": "2025-01-15T12:00:00Z",

      "dataset_origin": "LAION-5B",
      "corpus_hint": "ccid:laion-5b-2024-en-10M",

      "license_hint": "cc-by-2.0",
      "metadata": {
        "nsfw": false,
        "tags": ["sunset", "nature"]
      },

      "links": [
        {
          "type": "cep_block",
          "ref": "cep_sha256:7d9e4f2a..."
        }
      ],

      "period": "2025-01"
    }

### 2.2 Field definitions

Field | Type | Required | Description
----- | ---- | -------- | -----------
`schema` | string | ✅ | Must be `"spider_receipt.v1"`.
`version` | string | ✅ | Schema version, e.g. `"1.0.0"`.
`receipt_id` | string | ✅ | Canonical hash of normalized JSON. Format: `sr_sha256:{hex}`.
`content_id` | string | ✅ | Canonical content ID. Format: `cid:url_sha256:{hex}` or `cid:bytes_sha256:{hex}`.
`source_url` | string | ✅ | Original URL where content was found.
`retrieved_at` | ISO 8601 | ✅ | When Crovia processed this record (UTC).
`dataset_origin` | string | ✅ | Human-readable dataset name (e.g. `LAION-5B`, `C4`, `The Stack`).
`corpus_hint` | string | ⬜️ | Optional CCID if already mapped to a corpus passport (e.g. `ccid:laion-5b-2024-en-10M`).
`license_hint` | string | ⬜️ | Best-guess license from metadata (e.g. `cc-by-2.0`, `unknown`).
`metadata` | object | ⬜️ | Additional content metadata (NSFW flags, tags, etc.).
`links` | array | ✅ | Array of related receipts or artifacts (may be empty).
`period` | string | ✅ | Crovia period when this receipt was created (e.g. `2025-12`).

---

## 2.3 ID semantics

### `receipt_id`

- **Format:** `sr_sha256:{64_hex_chars}`  
- **Generation:** SHA-256 of the normalized JSON (fields sorted, no extra whitespace).  
- **Purpose:** Unique identifier for this specific receipt instance.

### `content_id`

- **Format:** `cid:{method}_sha256:{64_hex_chars}`  

Methods:

- `url_sha256`: hash of canonicalized URL (lowercased, fragment-stripped, etc.)  
- `bytes_sha256`: hash of content bytes (when available)  
- `text_sha256`: hash of normalized text content (for pure text corpora)  

Purpose: stable identifier for the content across different receipts.

Example generation (URL-based):

    # content_id from URL
    url = "https://example.com/image.jpg"
    canonical_url = url.lower().split("#")[0].rstrip("/")
    content_hash = sha256(canonical_url.encode("utf-8")).hexdigest()
    content_id = f"cid:url_sha256:{content_hash}"

    # receipt_id from JSON
    normalized = json.dumps(receipt, sort_keys=True, separators=(",", ":"))
    receipt_hash = sha256(normalized.encode("utf-8")).hexdigest()
    receipt_id = f"sr_sha256:{receipt_hash}"

---

## 3. Temporal framework

### 3.1 The `period` field

The `period` field represents Crovia's **window of observation**, not the content's
creation date or dataset publication date.

- **Format:** `YYYY-MM` (month granularity)  
- **Meaning:** “Crovia became aware of this content during this period.”  
- **Usage:** Enables grouping receipts by observation time and aligning them with C-Line periods.  

Example: a LAION-5B item processed in December 2025 has `"period": "2025-12"`.

### 3.2 `retrieved_at` vs `period`

- `retrieved_at`: precise ISO timestamp (UTC) of processing.  
- `period`: monthly bucket used for aggregation and governance.  

---

## 4. Relationship to other Crovia standards

### 4.1 CEP

A `spider_receipt.v1` can be referenced in a CEP evidence block via `links`:

    {
      "type": "cep_block",
      "ref": "cep_sha256:..."
    }

### 4.2 `provenance_receipt.v1`

A `spider_receipt.v1` is typically the first event in a provenance chain:

> “Crovia observed this content in corpus X at time T.”

### 4.3 `royalty_receipt.v1`

Spider receipts provide a source evidence layer that can be aggregated into
`royalty_receipt.v1` via:

- provider mapping (dataset → provider, domain → provider)  
- value share calculation  
- period alignment  

---

## 5. Phase 1 implementation notes

### 5.1 Required fields (Phase 1)

Initial implementation **must** populate:

- `schema`, `version`  
- `content_id` (URL-based)  
- `source_url`  
- `retrieved_at`  
- `dataset_origin`  
- `links` (empty array allowed)  
- `period`  
- `receipt_id` (derived at the end)  

### 5.2 Optional fields (Phase 1)

May be set to `null` / omitted initially:

- `license_hint` (default: `"unknown"` or omitted)  
- `metadata` (e.g. `{ "nsfw": false }`)  
- `corpus_hint` (to be filled once corpus passports exist)  

### 5.3 Content ID strategy

- **Phase 1:** `cid:url_sha256:{hash}` only.  
- **Phase 2+:** add `cid:bytes_sha256:{hash}` and `cid:text_sha256:{hash}` when appropriate.  

---

## 6. Validation rules

- `schema` must be `"spider_receipt.v1"`.  
- `version` must be `"1.0.0"` for this spec.  
- `receipt_id` must start with `"sr_sha256:"` and contain 64 hex chars.  
- `content_id` must start with `"cid:"` and contain a known method suffix (e.g. `url_sha256:`).  
- `period` must match regex: `^\d{4}-\d{2}$`.  
- `retrieved_at` must be a valid ISO 8601 timestamp (UTC recommended).  
- `source_url` must be a syntactically valid URL.  
- `links` must be an array (possibly empty).  

---

## 7. Next steps

- Implement generator for LAION-style metadata (`from-laion` CLI).  
- Define `spider_corpus.v1` (corpus passports, CCID).  
- Define `provenance_receipt.v1` (event chains).  
- Implement adapter from spider receipts to `royalty_receipt.v1`.  
- Publish sample dataset on HuggingFace (e.g. `crovia/receipts-spider-laion-sample`).  

---

**Status:** This document is a living specification and may evolve based on implementation experience.  
**Authors:** Crovia Trust  
**License:** CC-BY-4.0
