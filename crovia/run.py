#!/usr/bin/env python3
"""
crovia.run — CRC-1 Reference Orchestrator (Open Core)

This command produces a deterministic, offline-verifiable
set of Crovia artifacts from declared receipts.

It does NOT infer.
It does NOT optimize.
It does NOT hide steps.

Artifacts produced follow CRC-1 contract.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="crovia-run",
        description="Crovia Open-Core deterministic artifact generator (CRC-1)",
    )

    parser.add_argument(
        "--receipts",
        required=True,
        help="Input receipts NDJSON (declared source)",
    )
    parser.add_argument(
        "--period",
        required=True,
        help="Accounting period (e.g. 2025-11)",
    )
    parser.add_argument(
        "--out",
        required=True,
        help="Output directory for CRC-1 artifacts",
    )

    args = parser.parse_args(argv)

    receipts = Path(args.receipts).resolve()
    out_dir = Path(args.out).resolve()

    if not receipts.exists():
        print(f"[crovia-run] ERROR: receipts not found: {receipts}", file=sys.stderr)
        return 2

    out_dir.mkdir(parents=True, exist_ok=True)

    print("[crovia-run] CRC-1 artifact generation started")
    print(f"  receipts : {receipts}")
    print(f"  period   : {args.period}")
    print(f"  out      : {out_dir}")
    print()

    # ------------------------------------------------------------
    # 1) Copy receipts (declared input snapshot)
    # ------------------------------------------------------------
    receipts_copy = out_dir / "receipts.ndjson"
    shutil.copyfile(receipts, receipts_copy)
    print("[1/4] receipts snapshot written")

    # ------------------------------------------------------------
    # 2) Validate receipts
    # ------------------------------------------------------------
    validate_md = out_dir / "validate_report.md"
    subprocess.run(
        [
            sys.executable,
            "validate/validate.py",
            str(receipts_copy),
            "--out-md",
            str(validate_md),
        ],
        check=True,
    )
    print("[2/4] validation report written")

    # ------------------------------------------------------------
    # 3) Hashchain
    # ------------------------------------------------------------
    hashchain = out_dir / "hashchain.txt"
    subprocess.run(
        [
            sys.executable,
            "proofs/hashchain_writer.py",
            "--source",
            str(receipts_copy),
            "--out",
            str(hashchain),
        ],
        check=True,
    )
    print("[3/4] hashchain generated")

    # ------------------------------------------------------------
    # 4) Trust bundle (minimal, open-core)
    # ------------------------------------------------------------
    bundle = out_dir / "trust_bundle.json"
    bundle_data = {
        "schema": "crovia.trust_bundle.v1",
        "period": args.period,
        "artifacts": {
            "receipts": receipts_copy.name,
            "validate_report": validate_md.name,
            "hashchain": hashchain.name,
        },
    }
    bundle.write_text(json.dumps(bundle_data, indent=2), encoding="utf-8")
    print("[4/4] trust bundle written")

    # ------------------------------------------------------------
    # Manifest (CRC-1)
    # ------------------------------------------------------------
    manifest = out_dir / "MANIFEST.json"
    manifest_data = {
        "schema": "crovia.manifest.v1",
        "contract": "CRC-1",
        "period": args.period,
        "artifacts": {
            "receipts": receipts_copy.name,
            "validate_report": validate_md.name,
            "hashchain": hashchain.name,
            "trust_bundle": bundle.name,
        },
    }
    manifest.write_text(json.dumps(manifest_data, indent=2), encoding="utf-8")

    print()
    print("[OK] CRC-1 artifacts completed")
    print(f"Inspect: {out_dir}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
