# crovia/id.py
"""
Crovia ID — Canonical Bundle Identifier

Purpose:
- Generate a stable, human-readable ID for a Crovia bundle
- Bind the ID to a canonical SHA256 hash
- Enable offline verification, QR linking, and future registry lookup

Format:
CTB-YYYY-MM-SOURCE-XXXX

Example:
CTB-2025-11-HF-8559
"""

from __future__ import annotations

import hashlib
import json
import random
import string
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any


# ----------------------------
# helpers
# ----------------------------

def _canonical_json_bytes(obj: Dict[str, Any]) -> bytes:
    """
    Canonical JSON serialization:
    - sorted keys
    - no whitespace
    - UTF-8
    """
    return json.dumps(
        obj,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def sha256_of_object(obj: Dict[str, Any]) -> str:
    return hashlib.sha256(_canonical_json_bytes(obj)).hexdigest()


def _rand_suffix(n: int = 4) -> str:
    return "".join(random.choices(string.digits, k=n))


# ----------------------------
# public API
# ----------------------------

def generate_crovia_id(
    *,
    period: str,
    source: str,
    suffix: str | None = None,
) -> str:
    """
    Generate a Crovia ID.

    period: YYYY-MM
    source: short uppercase label (HF, LAION, C4, MIX, etc.)
    """
    if not suffix:
        suffix = _rand_suffix()

    return f"CTB-{period}-{source.upper()}-{suffix}"


def bind_id_to_bundle(
    *,
    bundle_path: Path,
    crovia_id: str,
) -> Dict[str, Any]:
    """
    Load a trust bundle JSON, compute canonical hash,
    and return an ID binding structure.
    """
    if not bundle_path.exists():
        raise FileNotFoundError(bundle_path)

    bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
    bundle_hash = sha256_of_object(bundle)

    return {
        "crovia_id": crovia_id,
        "bundle_sha256": bundle_hash,
        "bundle_file": bundle_path.name,
        "generated_at": datetime.now(timezone.utc).isoformat() + "Z",
        "schema": "crovia_id_binding.v1",
    }


def write_id_artifacts(
    *,
    bundle_path: Path,
    period: str,
    source: str,
    out_dir: Path,
) -> Dict[str, Path]:
    """
    Generate Crovia ID + hash binding and write artifacts.

    Outputs:
    - crovia_id.txt
    - crovia_id.json
    """
    out_dir.mkdir(parents=True, exist_ok=True)

    crovia_id = generate_crovia_id(period=period, source=source)
    binding = bind_id_to_bundle(
        bundle_path=bundle_path,
        crovia_id=crovia_id,
    )

    id_txt = out_dir / "crovia_id.txt"
    id_json = out_dir / "crovia_id.json"

    id_txt.write_text(crovia_id + "\n", encoding="utf-8")
    id_json.write_text(
        json.dumps(binding, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    return {
        "crovia_id": id_txt,
        "crovia_binding": id_json,
    }
