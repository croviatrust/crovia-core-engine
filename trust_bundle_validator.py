#!/usr/bin/env python3
"""
CROVIA – Trust Bundle validator (stand-alone)

Usage examples:

  # Validate a standard period bundle from /opt/crovia
  python3 trust_bundle_validator.py \
    --bundle trust_bundle_2025-11.json \
    --base-dir /opt/crovia

  # Validate the FAISS/DPI demo bundle
  python3 trust_bundle_validator.py \
    --bundle demo_dpi_2025-11/output/trust_bundle_2025-11.json \
    --base-dir /opt/crovia

Exit codes:
  0 = everything OK
  1 = validation error (missing file, hash mismatch, parse error, etc.)
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Dict, Any


def sha256_hex(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def validate_bundle(bundle_path: Path, base_dir: Path) -> int:
    print(f"[*] Loading bundle: {bundle_path}")
    try:
        raw = bundle_path.read_text(encoding="utf-8")
        bundle: Dict[str, Any] = json.loads(raw)
    except Exception as e:
        print(f"[ERROR] Cannot read/parse bundle JSON: {e}")
        return 1

    schema = bundle.get("schema", "<missing>")
    period = bundle.get("period", "<missing>")
    print(f"    schema={schema}  period={period}")

    artifacts = bundle.get("artifacts", {})
    if not isinstance(artifacts, dict) or not artifacts:
        print("[ERROR] No 'artifacts' section found in bundle.")
        return 1

    errors = 0
    print("\n=== Artifact verification ===")
    for name, meta in artifacts.items():
        meta = meta or {}
        path_str = meta.get("path")
        expected_bytes = meta.get("bytes")
        expected_sha256 = meta.get("sha256")

        if not path_str:
            print(f"[WARN] {name}: missing 'path' – skipping")
            continue

        # 1) Try path relative to the bundle file
        file_path = (bundle_path.parent / path_str).resolve()
        # 2) If not found, try base_dir (e.g. /opt/crovia)
        if not file_path.exists():
            alt = (base_dir / path_str).resolve()
            if alt.exists():
                file_path = alt
            else:
                print(
                    f"[ERROR] {name}: file not found at '{path_str}' "
                    f"(checked {file_path} and {alt})"
                )
                errors += 1
                continue

        size = file_path.stat().st_size
        sha = sha256_hex(file_path)

        status = "OK"
        if expected_bytes is not None and size != expected_bytes:
            status = "SIZE_MISMATCH"
            errors += 1
        if expected_sha256 and sha != expected_sha256:
            status = "HASH_MISMATCH"
            errors += 1

        print(f"- {name}")
        print(f"    path: {path_str}")
        print(
            f"    size: {size} bytes"
            + (f" (expected {expected_bytes})" if expected_bytes is not None else "")
        )
        print(
            f"    sha256: {sha}"
            + (f" (expected {expected_sha256})" if expected_sha256 else "")
        )
        print(f"    status: {status}\n")

    if errors:
        print(f"[RESULT] Bundle NOT valid: {errors} error(s) detected.")
        return 1

    print("[RESULT] Bundle OK: all declared artifacts match size and sha256.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="CROVIA Trust Bundle validator (stand-alone)"
    )
    parser.add_argument(
        "--bundle",
        required=True,
        help="Path to trust_bundle_YYYY-MM.json (or FAISS/DPI demo bundle).",
    )
    parser.add_argument(
        "--base-dir",
        default=".",
        help="Base directory for artifacts (default: current dir, e.g. /opt/crovia).",
    )
    args = parser.parse_args(argv)

    bundle_path = Path(args.bundle).expanduser().resolve()
    base_dir = Path(args.base_dir).expanduser().resolve()

    if not bundle_path.exists():
        print(f"[ERROR] Bundle file not found: {bundle_path}")
        return 1

    return validate_bundle(bundle_path, base_dir)


if __name__ == "__main__":
    raise SystemExit(main())
