# Copyright 2025  Tarik En Nakhai
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


from typing import Dict, Any, List
from jsonschema import Draft202012Validator

# ===========================
# shapley.v1 (rigoroso)
# ===========================
SHAPLEY_SCHEMA_ID = "shapley.v1"
SHAPLEY_SCHEMA: Dict[str, Any] = {
    "$id": f"https://contracts.example/{SHAPLEY_SCHEMA_ID}.schema.json",
    "type": "object",
    "required": ["schema", "request_id", "timestamp", "method", "top_k"],
    "properties": {
        "schema": {"const": SHAPLEY_SCHEMA_ID},
        "request_id": {"type": "string"},
        "timestamp": {"type": "string"},  # ISO8601 atteso (verifica formale opzionale)
        "method": {"type": "string"},
        "method_details": {"type": "object"},
        "k": {"type": "integer"},
        "B": {"type": "integer"},
        "ci_samples": {"type": "integer"},
        "dp_epsilon": {"type": ["number", "integer"]},
        "model_hash": {"type": "string"},
        "pack_hash": {"type": "string"},
        "top_k": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["rank", "index", "label", "score_mean", "share"],
                "properties": {
                    "rank": {"type": "integer"},
                    "index": {"type": "integer"},
                    "label": {"type": "string"},
                    "score_mean": {"type": "number"},
                    "score_lo95": {"type": ["number", "null"]},
                    "score_hi95": {"type": ["number", "null"]},
                    "share": {"type": "number"},
                },
                "additionalProperties": False,
            },
        },
        "signature": {"type": "string"},
    },
    "additionalProperties": True,
}

# ===========================
# payouts.v1 (payout semplice ma estensibile)
# NOTE:
# - Manteniamo i required minimi (compatibile con la tua versione)
# - Aggiungiamo proprietà facoltative usate dal modulo Payout
#   (currency, share_agg, gross_revenue, policies_applied)
# ===========================
PAYOUTS_SCHEMA_ID = "payouts.v1"
PAYOUTS_SCHEMA: Dict[str, Any] = {
    "$id": f"https://contracts.example/{PAYOUTS_SCHEMA_ID}.schema.json",
    "type": "object",
    "required": ["schema", "provider_id", "period", "amount"],
    "properties": {
        "schema": {"const": PAYOUTS_SCHEMA_ID},
        "provider_id": {"type": "string", "minLength": 1},
        "period": {"type": "string", "pattern": r"^\d{4}-\d{2}$"},  # YYYY-MM
        "amount": {"type": "number"},
        # --- opzionali utili ---
        "currency": {"type": "string", "minLength": 3, "maxLength": 3},
        "share_agg": {"type": "number", "minimum": 0},
        "gross_revenue": {"type": "number", "minimum": 0},
        "policies_applied": {"type": "array", "items": {"type": "string"}},
        "meta": {"type": "object"},
    },
    "additionalProperties": True,
}

# ===========================
# royalty_receipt.v1 (ricevuta per-output)
# ===========================
ROYALTY_SCHEMA_ID = "royalty_receipt.v1"
ROYALTY_SCHEMA: Dict[str, Any] = {
    "$id": f"https://contracts.example/{ROYALTY_SCHEMA_ID}.schema.json",
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "CROVIA Royalty Receipt",
    "type": "object",
    "required": [
        "schema",
        "output_id",
        "model_id",
        "timestamp",
        "attribution_scope",
        "top_k",
        "hash_model",
        "hash_data_index",
    ],
    "properties": {
        "schema": {"const": ROYALTY_SCHEMA_ID},
        "output_id": {"type": "string", "minLength": 1},
        "request_id": {"type": "string"},
        "model_id": {"type": "string", "minLength": 1},
        "timestamp": {"type": "string", "format": "date-time"},
        "attribution_scope": {"type": "string", "minLength": 1},
        "usage": {
            "type": "object",
            "properties": {
                "input_tokens": {"type": "integer", "minimum": 0},
                "output_tokens": {"type": "integer", "minimum": 0},
            },
            "additionalProperties": True,
        },
        "top_k": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "required": ["rank", "provider_id", "shard_id", "share"],
                "properties": {
                    "rank": {"type": "integer", "minimum": 1},
                    "provider_id": {"type": "string", "minLength": 1},
                    "shard_id": {"type": "string", "minLength": 1},
                    "share": {"type": "number", "minimum": 0},
                    "share_ci95_low": {"type": "number", "minimum": 0},
                    "share_ci95_high": {"type": "number", "minimum": 0},
                    "raw_score": {"type": "number"},
                    "shapley_value": {"type": "number"},
                    "meta": {"type": "object"},
                },
                "additionalProperties": True,
            },
        },
        "epsilon_dp": {"type": ["number", "integer"], "minimum": 0},
        "hash_model": {"type": "string", "minLength": 8},
        "hash_data_index": {"type": "string", "minLength": 8},
        "signature": {"type": "string", "minLength": 1},
        # --- estensioni opzionali utili a compliance/licensing ---
        "license_refs": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["license_id"],
                "properties": {
                    "license_id": {"type": "string", "minLength": 1},
                    "scope": {
                        "type": "string",
                        "enum": ["train", "rag", "fine-tune", "other"],
                    },
                    "terms": {"type": "string"},
                },
                "additionalProperties": True,
            },
        },
        "policy_applied": {"type": "array", "items": {"type": "string"}},
        "proof_ref": {
            "type": "object",
            "properties": {
                "hashchain_id": {"type": "string"},
                "offset": {"type": "integer", "minimum": 0},
            },
            "additionalProperties": False,
        },
        "meta": {"type": "object"},
    },
    "additionalProperties": True,
}

# NOTE: vincoli come "somma share ≈ 1.0" non si esprimono bene in JSON Schema puro
#       → saranno verificati a runtime nel validator (ERROR se deviazione > 0.02).

# ===========================
# crovia_trust_bundle.v1 (manifest dei file mensili)
# ===========================
TRUST_BUNDLE_SCHEMA_ID = "crovia_trust_bundle.v1"
TRUST_BUNDLE_SCHEMA: Dict[str, Any] = {
    "$id": f"https://contracts.example/{TRUST_BUNDLE_SCHEMA_ID}.schema.json",
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "CROVIA Trust Bundle Manifest",
    "type": "object",
    "required": [
        "schema",
        "period",
        "created_at",
        "bundle_id",
        "inputs",
        "artifacts",
    ],
    "properties": {
        "schema": {"const": TRUST_BUNDLE_SCHEMA_ID},
        "period": {"type": "string", "pattern": r"^\d{4}-\d{2}$"},  # YYYY-MM
        "created_at": {"type": "string", "format": "date-time"},
        "bundle_id": {"type": "string", "minLength": 1},
        "producer": {"type": "string"},
        "version": {"type": "string"},
        "inputs": {
            "type": "object",
            "minProperties": 1,
            "patternProperties": {
                "^.+$": {"$ref": "#/$defs/file_ref"}
            },
            "additionalProperties": False,
        },
        "artifacts": {
            "type": "object",
            "minProperties": 1,
            "patternProperties": {
                "^.+$": {"$ref": "#/$defs/file_ref"}
            },
            "additionalProperties": False,
        },
        "stats": {"type": "object"},
    },
    "additionalProperties": False,
    "$defs": {
        "file_ref": {
            "type": "object",
            "required": ["path", "bytes", "sha256"],
            "properties": {
                "path": {"type": "string", "minLength": 1},
                "bytes": {"type": "integer", "minimum": 0},
                "sha256": {
                    "type": "string",
                    "pattern": "^[0-9a-f]{64}$",  # SHA256 hex
                },
            },
            "additionalProperties": True,
        }
    },
}

# ===========================
# Registry validatori
# ===========================
_VALIDATORS: Dict[str, Draft202012Validator] = {
    SHAPLEY_SCHEMA_ID: Draft202012Validator(SHAPLEY_SCHEMA),
    PAYOUTS_SCHEMA_ID: Draft202012Validator(PAYOUTS_SCHEMA),
    ROYALTY_SCHEMA_ID: Draft202012Validator(ROYALTY_SCHEMA),
    TRUST_BUNDLE_SCHEMA_ID: Draft202012Validator(TRUST_BUNDLE_SCHEMA),
}


def supported_schemas() -> List[str]:
    return sorted(_VALIDATORS.keys())


def is_schema_compatible(rec: Dict[str, Any]) -> bool:
    """Compatibilità generale: lo 'schema' deve esistere nel registry."""
    s = rec.get("schema")
    return isinstance(s, str) and s in _VALIDATORS


def validate_record(rec: Dict[str, Any]) -> None:
    """Valida in base al registry; se schema ignoto, solleva ValueError."""
    s = rec.get("schema")
    if not isinstance(s, str) or s not in _VALIDATORS:
        raise ValueError(f"Unknown or missing schema: {s!r}")
    _VALIDATORS[s].validate(rec)

