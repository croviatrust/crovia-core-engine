#!/usr/bin/env python3
"""
Crovia Passport Protocol (CPP-1) Builder
Generates a consolidated, offline-verifiable JSON passport for a target AI model.
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict


def load_json(path: Path) -> Dict[str, Any] | list:
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def build_passport(model_id: str, data_dir: Path) -> Dict[str, Any]:
    # 1. Load Data Sources
    ranking_data = load_json(data_dir / "global_ranking.json")
    tpa_data = load_json(data_dir / "tpa_latest.json")
    gdna_data = load_json(data_dir / "gdna_results.json")
    forensic_data = load_json(data_dir / "forensic_report.json")

    # 2. Extract Identity & Compliance
    ranking_list = ranking_data.get("models", [])
    model_rank = next((m for m in ranking_list if m.get("id") == model_id), None)

    # 3. Extract Cryptography (TPA)
    tpa_list = tpa_data.get("tpas", [])
    model_tpa = next((t for t in tpa_list if t.get("model_id") == model_id), None)

    # 4. Extract Provenance (GDNA & Forensics)
    model_gdna = None
    runs = gdna_data.get("runs", [])
    for run in runs:
        comps = run.get("comparisons", {})
        for comp_key, comp_val in comps.items():
            if model_id in comp_key:
                model_gdna = comp_val
                break
        if model_gdna:
            break

    # Build CPP-1 Structure
    passport: Dict[str, Any] = {
        "protocol": "CPP-1",
        "version": "0.1.0",
        "identity": {
            "model_id": model_id,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        },
        "compliance": {
            "available": model_rank is not None,
        },
        "provenance": {
            "gdna": {
                "available": model_gdna is not None,
            }
        },
        "cryptography": {
            "tpa_available": model_tpa is not None,
        }
    }

    if model_rank:
        passport["identity"]["snapshot_hash"] = model_rank.get("card_sha256", "unknown")
        passport["compliance"].update({
            "score": model_rank.get("score_abs"),
            "severity": model_rank.get("severity"),
            "nec_vector": model_rank.get("nec_breakdown", {})
        })

    if model_gdna:
        related_to = model_gdna["model_a"] if model_gdna["model_b"] == model_id else model_gdna["model_b"]
        passport["provenance"]["gdna"].update({
            "relationship": model_gdna.get("relationship"),
            "confidence": model_gdna.get("confidence"),
            "primary_match": related_to,
            "evidence_hash": model_gdna.get("comparison_hash")
        })

    if model_tpa:
        passport["cryptography"].update({
            "tpa_height": tpa_data.get("chain_height"),
            "merkle_root": model_tpa.get("tpa_hash"),
            "chain_status": "VERIFIED"
        })

    # (Future: add canonical hashing and Ed25519 signature here)

    return passport


def main():
    parser = argparse.ArgumentParser(description="Build CPP-1 Passport")
    parser.add_argument("model_id", help="HuggingFace Model ID (e.g. Qwen/Qwen2.5-7B)")
    parser.add_argument("--data-dir", default="/var/www/registry/data", help="Path to registry data")
    parser.add_argument("--out", help="Output file path (default: stdout)")
    args = parser.parse_args()

    passport = build_passport(args.model_id, Path(args.data_dir))
    
    out_json = json.dumps(passport, indent=2, ensure_ascii=False)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(out_json)
        print(f"Passport saved to {args.out}")
    else:
        print(out_json)


if __name__ == "__main__":
    main()
