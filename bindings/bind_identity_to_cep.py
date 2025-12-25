#!/usr/bin/env python3
"""
Bind a CEP capsule to a Crovia Identity (CIDv1)
Non-invasive, deterministic, auditable.
"""

from __future__ import annotations
import json
import hashlib
from datetime import datetime, timezone
from pathlib import Path
import sys


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def bind(cep_id: str, crovia_id: str) -> dict:
    material = f"{cep_id}::{crovia_id}".encode("utf-8")
    return {
        "binding_version": "1.0",
        "cep_id": cep_id,
        "crovia_id": crovia_id,
        "binding_hash": sha256(material),
        "declared_at": datetime.now(timezone.utc).isoformat(),
    }


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("usage: bind_identity_to_cep.py <CEP_ID> <CROVIA_ID>")
        sys.exit(1)

    cep_id = sys.argv[1]
    crovia_id = sys.argv[2]

    out = bind(cep_id, crovia_id)
    print(json.dumps(out, indent=2))
