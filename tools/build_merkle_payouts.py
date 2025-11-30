#!/usr/bin/env python3
import argparse
import hashlib
import json
import os
from typing import List, Tuple


def file_sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def read_ndjson_lines(path: str) -> List[bytes]:
    lines = []
    with open(path, "rb") as f:
        for raw in f:
            raw = raw.rstrip(b"\r\n")
            if raw:
                lines.append(raw)
    return lines


def merkle_root_from_lines(lines: List[bytes]) -> Tuple[str, int]:
    """
    Build a simple binary Merkle tree over the raw NDJSON lines.
    Leaves are sha256(line_bytes).
    """
    if not lines:
        return "", 0

    layer = [hashlib.sha256(line).digest() for line in lines]
    leaf_count = len(layer)

    while len(layer) > 1:
        nxt = []
        it = iter(layer)
        for left in it:
            try:
                right = next(it)
            except StopIteration:
                right = left
            h = hashlib.sha256(left + right).digest()
            nxt.append(h)
        layer = nxt

    root_hex = layer[0].hex()
    return root_hex, leaf_count


def format_op8(alias: str) -> str:
    """
    Format operator alias as 8-char CROVIA OP:8 code (uppercased, '-' padded).
    Example: 'hf' -> 'HF------', 'OPENAI' -> 'OPENAI--'.
    """
    a = (alias or "").strip().upper()
    if len(a) >= 8:
        return a[:8]
    return a.ljust(8, "-")


def make_crovia_id(period: str, operator_alias: str, payouts_path: str):
    """
    Build (crovia_id, crovia_id_line) for a given run.

    crovia_id:
        CTB-<PERIOD>-<OP:8><RUN:4>

    where RUN:4 is deterministically derived from the payouts NDJSON
    SHA-256 digest (no manual counter is required).

    crovia_id_line:
        CROVIA-ID: CTB-<PERIOD>-<OP:8><RUN:4> sha256=<SHA16>

    where SHA16 is the first 16 hex chars of SHA-256 over the payouts NDJSON bytes.
    """
    op8 = format_op8(operator_alias)

    h = hashlib.sha256()
    with open(payouts_path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            if not chunk:
                break
            h.update(chunk)
    sha_full = h.hexdigest()
    sha16 = sha_full[:16]

    # RUN:4 is a deterministic 4-digit code derived from the hash
    run_int = int(sha_full[:8], 16) % 10000
    run = f"{run_int:04d}"

    crovia_id = f"CTB-{period}-{op8}{run}"
    crovia_id_line = f"CROVIA-ID: {crovia_id} sha256={sha16}"
    return crovia_id, crovia_id_line


def main():
    parser = argparse.ArgumentParser(
        description="Build Merkle summary over payouts NDJSON and a CROVIA trust bundle."
    )
    parser.add_argument(
        "--source",
        required=True,
        help="Input payouts NDJSON file (payouts.v1).",
    )
    parser.add_argument(
        "--out",
        required=True,
        help="Output Merkle summary JSON path.",
    )
    parser.add_argument(
        "--period",
        default="2025-11",
        help="Settlement period string (e.g. 2025-11).",
    )
    parser.add_argument(
        "--operator",
        default="DEMO",
        help="Operator / tenant alias used in CROVIA-ID (OP:8).",
    )
    parser.add_argument(
        "--model-id",
        default="crovia-dpi-demo",
        help="Model identifier to include in the trust bundle.",
    )
    parser.add_argument(
        "--profile-id",
        default="CROVIA_DPI_FAISS_DEMO_v1",
        help="Profile identifier for the trust bundle.",
    )
    parser.add_argument(
        "--bundle-out",
        default="demo_dpi_2025-11/output/trust_bundle_2025-11.json",
        help="Output path for the CROVIA trust bundle JSON.",
    )

    args = parser.parse_args()

    payouts_path = args.source
    merkle_out = args.out
    period = args.period
    operator_alias = args.operator
    model_id = args.model_id
    profile_id = args.profile_id
    bundle_out = args.bundle_out

    print(f"[MERKLE] Reading payouts NDJSON: {payouts_path}")
    lines = read_ndjson_lines(payouts_path)
    root_hex, leaf_count = merkle_root_from_lines(lines)
    payouts_sha = file_sha256(payouts_path)
    print(f"[MERKLE] root={root_hex}  leaves={leaf_count}")
    print(f"[MERKLE] payouts.sha256={payouts_sha}")

    merkle_summary = {
        "schema": "merkle_payouts.v1",
        "period": period,
        "file": {
            "schema": "payouts.v1",
            "path": payouts_path,
            "sha256": payouts_sha
        },
        "root": root_hex,
        "leaf_count": leaf_count
    }

    os.makedirs(os.path.dirname(merkle_out), exist_ok=True)
    with open(merkle_out, "w", encoding="utf-8") as f:
        json.dump(merkle_summary, f, indent=2)
    print(f"[MERKLE] written {merkle_out}")

    # CROVIA-ID (deterministic)
    crovia_id, crovia_id_line = make_crovia_id(
        period=period,
        operator_alias=operator_alias,
        payouts_path=payouts_path,
    )
    print(f"[CROVIA-ID] {crovia_id_line}")

    # Trust bundle
    trust_summary_path = "docs/trust_summary.md"
    trust_providers_path = "data/trust_providers.csv"

    artifacts = {}

    artifacts["payouts_ndjson"] = {
        "schema": "payouts.v1",
        "path": payouts_path,
        "sha256": payouts_sha
    }

    artifacts["merkle_payouts"] = {
        "schema": "merkle_payouts.v1",
        "path": merkle_out,
        "sha256": file_sha256(merkle_out),
        "root": root_hex,
        "leaf_count": leaf_count
    }

    if os.path.exists(trust_summary_path):
        artifacts["trust_summary_md"] = {
            "schema": "text/markdown",
            "path": trust_summary_path,
            "sha256": file_sha256(trust_summary_path)
        }

    if os.path.exists(trust_providers_path):
        artifacts["trust_providers_csv"] = {
            "schema": "text/csv",
            "path": trust_providers_path,
            "sha256": file_sha256(trust_providers_path)
        }

    bundle = {
        "schema": "crovia_trust_bundle.v1",
        "profile_id": profile_id,
        "period": period,
        "crovia_id": crovia_id,
        "crovia_id_line": crovia_id_line,
        "model_id": model_id,
        "artifacts": artifacts
    }

    os.makedirs(os.path.dirname(bundle_out), exist_ok=True)
    with open(bundle_out, "w", encoding="utf-8") as f:
        json.dump(bundle, f, indent=2)
    print(f"[MERKLE & TRUST BUNDLE] written {bundle_out}")


if __name__ == "__main__":
    main()
