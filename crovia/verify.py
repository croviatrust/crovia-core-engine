#!/usr/bin/env python3
"""
crovia.verify — CRC-1 offline verifier (audit-first)
usage:
  crovia-verify <CRC-1 directory>
"""

from __future__ import annotations
import json
import sys
import subprocess
from pathlib import Path

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

def _fail(msg: str) -> "None":
    print(f"[FAIL] CRC-1 INVALID: {msg}")
    raise SystemExit(1)

def _ok(msg: str) -> None:
    print(f"[OK] {msg}")

def _find_hashchain_verifier(repo_root: Path) -> Path:
    # We do NOT guess names; we check the repo for known verifier scripts.
    candidates = [
        repo_root / "proofs" / "verify_hashchain.py",
        repo_root / "proofs" / "hashchain_verify.py",
        repo_root / "proofs" / "verify.py",
    ]
    for c in candidates:
        if c.exists():
            return c
    _fail(f"No hashchain verifier script found under {repo_root/'proofs'}")

def main() -> None:
    if len(sys.argv) != 2:
        print("usage: crovia-verify <CRC-1 directory>")
        raise SystemExit(1)

    crc_dir = Path(sys.argv[1]).resolve()
    if not crc_dir.exists() or not crc_dir.is_dir():
        _fail("Provided path is not a directory")

    manifest_path = crc_dir / "MANIFEST.json"
    if not manifest_path.exists():
        _fail("MANIFEST.json missing")

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception as e:
        _fail(f"MANIFEST.json invalid JSON: {e}")

    if manifest.get("schema") != "crovia.manifest.v1":
        _fail("MANIFEST schema must be crovia.manifest.v1")
    if manifest.get("contract") != "CRC-1":
        _fail("MANIFEST contract must be CRC-1")

    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, dict):
        _fail("MANIFEST artifacts must be an object")

    # required keys for CRC-1
    required = ["receipts", "validate_report", "hashchain", "trust_bundle"]
    for k in required:
        if k not in artifacts:
            _fail(f"MANIFEST missing artifacts.{k}")

    # existence checks + path traversal guard
    safe_paths: dict = {}
    for k, rel in artifacts.items():
        if not isinstance(rel, str) or not rel.strip():
            _fail(f"artifacts.{k} must be a non-empty string, got {rel!r}")
        resolved = (crc_dir / rel).resolve()
        try:
            resolved.relative_to(crc_dir)
        except ValueError:
            _fail(
                f"artifacts.{k} path {rel!r} escapes the bundle directory "
                f"(path traversal rejected)"
            )
        if not resolved.exists():
            _fail(f"Missing artifact file: {rel} (from artifacts.{k})")
        safe_paths[k] = resolved
    _ok("All artifacts present")

    # Validate JSON of trust bundle (use already-resolved safe path)
    try:
        json.loads(safe_paths["trust_bundle"].read_text(encoding="utf-8"))
    except Exception as e:
        _fail(f"trust_bundle invalid JSON: {e}")
    _ok("trust_bundle JSON valid")

    # Verify hashchain using the REAL verifier present in this repo
    repo_root = Path(__file__).resolve().parents[1]  # .../crovia-core-engine (repo root)
    verifier = _find_hashchain_verifier(repo_root)

    receipts = safe_paths["receipts"]
    chain = safe_paths["hashchain"]

    cmd = [
        sys.executable,
        str(verifier),
        "--source", str(receipts),
        "--chain", str(chain),
    ]

    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        # print the verifier output to help debugging (offline, deterministic)
        sys.stdout.write(r.stdout)
        sys.stderr.write(r.stderr)
        _fail("Hashchain verification failed")

    _ok("Hashchain verified")
    print("\n[OK] CRC-1 VERIFIED")
    raise SystemExit(0)

if __name__ == "__main__":
    main()
