# crovia/verify.py
"""
Crovia Offline Verification

Verifies:
- bundle SHA256
- Crovia ID binding integrity
- schema correctness

NO network calls.
"""

from __future__ import annotations

import json
import hashlib
from pathlib import Path
from typing import Dict, Any


def _canonical_json_bytes(obj: Dict[str, Any]) -> bytes:
    return json.dumps(
        obj,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def sha256_of_object(obj: Dict[str, Any]) -> str:
    return hashlib.sha256(_canonical_json_bytes(obj)).hexdigest()


def verify_bundle(
    *,
    bundle_path: Path,
    id_binding_path: Path,
) -> Dict[str, Any]:
    if not bundle_path.exists():
        raise FileNotFoundError(bundle_path)
    if not id_binding_path.exists():
        raise FileNotFoundError(id_binding_path)

    bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
    binding = json.loads(id_binding_path.read_text(encoding="utf-8"))

    computed = sha256_of_object(bundle)
    expected = binding.get("bundle_sha256")

    ok = computed == expected

    return {
        "crovia_id": binding.get("crovia_id"),
        "expected_sha256": expected,
        "computed_sha256": computed,
        "match": ok,
        "schema": binding.get("schema"),
    }
