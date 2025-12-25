#!/usr/bin/env python3
"""
Crovia Identity Generator — CIDv1
Deterministic identity for datasets, providers, collections.
OPEN CORE — no secrets, no wallets, no accounts.
"""

from __future__ import annotations
import hashlib
import json
from datetime import datetime, timezone
from typing import Dict, Any


def _stable_json(obj: Dict[str, Any]) -> bytes:
    """
    Canonical JSON encoding for deterministic hashing.
    """
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")


def generate_crovia_id(
    *,
    entity_type: str,
    name: str,
    source: str,
    extra: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """
    Generate a Crovia Identity (CIDv1).

    entity_type: dataset | provider | publisher | collection
    name: human-readable name
    source: canonical source identifier (URL, repo, registry)
    """

    base_fingerprint = {
        "entity_type": entity_type,
        "name": name.strip(),
        "source": source.strip(),
        "extra": extra or {},
    }

    h = hashlib.sha256(_stable_json(base_fingerprint)).hexdigest()

    crovia_id = f"cidv1:{h}"

    return {
        "crovia_id": crovia_id,
        "entity_type": entity_type,
        "declared_at": datetime.now(timezone.utc).isoformat(),
        "fingerprint": {
            "algo": "sha256",
            "value": h,
        },
        "public_keys": [],
        "metadata": {
            "name": name,
            "source": source,
        },
    }


if __name__ == "__main__":
    # demo / smoke test
    demo = generate_crovia_id(
        entity_type="dataset",
        name="Example Dataset",
        source="https://example.org/dataset",
    )
    print(json.dumps(demo, indent=2))
